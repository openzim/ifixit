import io
import pathlib
import re
import urllib.parse
import zlib
from http import HTTPStatus
from typing import Any, cast

import backoff
import bs4
import requests
from kiwixstorage import (  # pyright: ignore[reportMissingTypeStubs]
    AuthenticationError,
    KiwixStorage,
)
from requests.exceptions import HTTPError
from zimscraperlib.download import stream_file

from ifixit2zim.constants import API_PREFIX, Configuration
from ifixit2zim.shared import logger


def backoff_hdlr(details: Any):
    logger.warning(
        "Backing off {wait:0.1f} seconds after {tries} tries "
        "calling function {target} with args {args} and kwargs "
        "{kwargs}".format(**details)
    )


def fatal_code(e: Exception) -> bool:
    """Give up on errors codes 400-499 except 429"""
    e = cast(HTTPError, e)
    if e.response is None:
        raise ValueError("Unknown error response class")

    logger.warning(f"Fatal code {e.response.status_code}")
    return (
        HTTPStatus.BAD_REQUEST
        <= e.response.status_code
        < HTTPStatus.INTERNAL_SERVER_ERROR
        and e.response.status_code != HTTPStatus.TOO_MANY_REQUESTS
    )


def get_version_ident_for_url(url: str) -> str | None:
    """~version~ of the URL data to use for comparisons. Built from headers"""
    try:
        resp = requests.head(url, timeout=10)
        headers = resp.headers
    except Exception as exc:
        logger.warning(f"Unable to HEAD {url}", exc_info=exc)
        try:
            _, headers = stream_file(
                url=url,
                byte_stream=io.BytesIO(),
                block_size=1,
                only_first_block=True,
            )
        except Exception as exc:
            logger.warning(f"Unable to query image at {url}", exc_info=exc)
            return

    for header in ("ETag", "Last-Modified", "Content-Length"):
        if headers.get(header):
            return headers.get(header)

    return "-1"


def rebuild_uri(
    uri: urllib.parse.ParseResult, scheme: str | None = None
) -> urllib.parse.ParseResult:
    netloc = ""
    scheme = scheme or uri.scheme
    if uri.username:
        netloc += uri.username
    if uri.password:
        netloc += f":{uri.password}"
    if uri.username or uri.password:
        netloc += "@"
    if uri.hostname:
        netloc += uri.hostname
    if uri.port:
        netloc += f":{uri.port}"
    return urllib.parse.urlparse(
        urllib.parse.urlunparse(
            [scheme, netloc, uri.path, uri.fragment, uri.query, uri.fragment]
        )
    )


def get_kiwix_storage_client(uri: str) -> Any:
    try:
        upload_uri = urllib.parse.urlparse(uri)
        pathlib.Path(upload_uri.path)
    except Exception as exc:
        raise ValueError(f"invalid upload URI: `{uri}`") from exc

    def get_url_scheme(url: urllib.parse.ParseResult) -> str:
        if url.scheme.startswith("s3"):
            if url.scheme.startswith("s3+https"):
                return "https"
            elif url.scheme.startswith("s3+http"):
                return "http"
            return "https"
        else:
            raise ValueError(f"Unsupported URL scheme in: {url}")

    s3 = KiwixStorage(
        rebuild_uri(upload_uri, scheme=get_url_scheme(upload_uri)).geturl()
    )
    if not s3.check_credentials(  # pyright: ignore[reportUnknownMemberType]
        list_buckets=True, bucket=True, write=True, read=True, failsafe=True
    ):
        raise AuthenticationError("check_credentials failed")

    return s3


class IFixitRequestClient:
    def __init__(self, configuration: Configuration) -> None:
        self.configuration = configuration

    def to_path(self, url: str) -> str:
        """Path-part of an URL, without leading slash"""
        return re.sub(r"^/", "", urllib.parse.urlparse(url).path)

    def get_url(self, path: str, **params: Any) -> str:
        """url-encoded in-source website url for a path"""
        params_str = f"?{urllib.parse.urlencode(params)}" if params else ""
        return (
            f"{self.configuration.main_url.geturl()}"
            f"{urllib.parse.quote(path)}"
            f"{params_str}"
        )

    def get_url_raw(self, path: str) -> str:
        """in-source website url for a path, untainted"""
        return f"{self.configuration.main_url.geturl()}{path}"

    def to_url(self, value: str) -> str:
        """resolved potentially relative url from in-source link"""
        return value if value.startswith("http") else self.get_url_raw(value)

    def to_rel(self, url: str) -> str | None:
        """path from URL if on our main domain, else None"""
        uri = urllib.parse.urlparse(url)
        if uri.netloc != self.configuration.domain:
            return None
        return uri.path

    def no_leading_slash(self, text: str) -> str:
        """text with leading slash removed if present"""
        return re.sub(r"^/", "", text)

    def no_trailing_slash(self, text: str) -> str:
        """text with trailing slash removed if present"""
        return re.sub(r"/$", "", text)

    def only_path_of(self, url: str) -> str:
        """normalized path part of an url"""
        return self.normalize_ident(urllib.parse.urlparse(url).path)

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_time=16,
        on_backoff=backoff_hdlr,
        giveup=fatal_code,
    )
    def fetch(self, path: str, **params: Any) -> tuple[str, list[str]]:
        """(source text, actual_paths) of a path from source website

        actual_paths is an ordered list of paths that were traversed to get to content.
        Without redirection, it should be a single path, equal to request
        Final, target path is always last"""
        resp = requests.get(
            self.get_url(path, **params),
            params=params,
            timeout=self.configuration.request_timeout,
        )
        resp.raise_for_status()

        # we have params meaning we requested a page (?pg=xxx)
        # assumption: this must be a category page (so on same domain)
        # we thus need to use redirection target (which lost param) with params
        if params and resp.history:
            return self.fetch(self.only_path_of(resp.url), **params)
        return resp.text, [
            self.no_leading_slash(self.only_path_of(r.url))
            for r in [*resp.history, resp]
        ]

    def get_soup_of(self, text: str, *, unwrap: bool = False) -> bs4.BeautifulSoup:
        """an lxml soup of an HTML string"""
        soup = bs4.BeautifulSoup(text, "lxml")
        if unwrap:
            for elem in ("body", "html"):
                getattr(soup, elem).unwrap()
        return soup

    def get_soup(self, path: str, **params: Any) -> tuple[bs4.BeautifulSoup, list[str]]:
        """an lxml soup of a path on source website"""
        content, paths = self.fetch(path, **params)
        return self.get_soup_of(content), paths

    def get_digest(self, url: str) -> str:
        """simple digest of an url for mapping purpose"""
        return str(zlib.adler32(url.encode("UTF-8")))

    def normalize_ident(self, ident: str) -> str:
        """URL-decoded category identifier"""
        return urllib.parse.unquote(ident)

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_time=16,
        on_backoff=backoff_hdlr,
        giveup=fatal_code,
    )
    def get_api_content(self, path: str, **params: Any) -> Any:
        full_path = self.get_url(API_PREFIX + path, **params)
        logger.debug(f"Retrieving {full_path}")
        response = requests.get(full_path, timeout=self.configuration.request_timeout)
        json_data = (
            response.json()
            if response and response.status_code == HTTPStatus.OK
            else None
        )
        return json_data

import io
import re
import urllib.parse
import zlib
from http import HTTPStatus

import backoff
import bs4
import requests
from kiwixstorage import KiwixStorage
from pif import get_public_ip
from zimscraperlib.download import _get_retry_adapter, stream_file

from ifixit2zim.constants import API_PREFIX, Configuration
from ifixit2zim.shared import logger


def backoff_hdlr(details):
    logger.warning(
        "Backing off {wait:0.1f} seconds after {tries} tries "
        "calling function {target} with args {args} and kwargs "
        "{kwargs}".format(**details)
    )


class Utils:
    def __init__(self, configuration: Configuration) -> None:
        self.configuration = configuration

    def to_path(self, url: str) -> str:
        """Path-part of an URL, without leading slash"""
        return re.sub(r"^/", "", urllib.parse.urlparse(url).path)

    def get_url(self, path: str, **params) -> str:
        """url-encoded in-source website url for a path"""
        params_str = f"?{urllib.parse.urlencode(params)}" if params else ""
        return (
            f"{self.configuration.main_url.geturl()}"
            f"{urllib.parse.quote(path)}"
            f"{params_str}"
        )

    def get_url_raw(self, path: str):
        """in-source website url for a path, untainted"""
        return f"{self.configuration.main_url.geturl()}{path}"

    def to_url(self, value: str) -> str:
        """resolved potentially relative url from in-source link"""
        return value if value.startswith("http") else self.get_url_raw(value)

    def to_rel(self, url: str) -> None | str:
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

    def only_path_of(self, url: str):
        """normalized path part of an url"""
        return self.normalize_ident(urllib.parse.urlparse(url).path)

    def fetch(self, path: str, **params) -> tuple[str, list[str]]:
        """(source text, actual_paths) of a path from source website

        actual_paths is amn ordered list of paths that were traversed to get to content.
        Without redirection, it should be a single path, equal to request
        Final, target path is always last"""
        session = requests.Session()
        session.mount("http", _get_retry_adapter(10))  # tied to http and https
        resp = session.get(self.get_url(path, **params), params=params)
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

    def get_soup_of(self, text: str, *, unwrap: bool = False):
        """an lxml soup of an HTML string"""
        soup = bs4.BeautifulSoup(text, "lxml")
        if unwrap:
            for elem in ("body", "html"):
                getattr(soup, elem).unwrap()
        return soup

    def get_soup(self, path: str, **params) -> tuple[bs4.BeautifulSoup, list[str]]:
        """an lxml soup of a path on source website"""
        content, paths = self.fetch(path, **params)
        return self.get_soup_of(content), paths

    def get_digest(self, url: str) -> str:
        """simple digest of an url for mapping purpose"""
        return str(zlib.adler32(url.encode("UTF-8")))

    def normalize_ident(self, ident: str) -> str:
        """URL-decoded category identifier"""
        return urllib.parse.unquote(ident)

    def get_version_ident_for(self, url: str) -> str | None:
        """~version~ of the URL data to use for comparisons. Built from headers"""
        try:
            resp = requests.head(url, timeout=10)
            headers = resp.headers
        except Exception as exc:
            logger.warning(f"Unable to HEAD {url}")
            logger.exception(exc)
            try:
                _, headers = stream_file(
                    url=url,
                    byte_stream=io.BytesIO(),
                    block_size=1,
                    only_first_block=True,
                )
            except Exception as exc2:
                logger.warning(f"Unable to query image at {url}")
                logger.exception(exc2)
                return

        for header in ("ETag", "Last-Modified", "Content-Length"):
            if headers.get(header):
                return headers.get(header)

        return "-1"

    def setup_s3_and_check_credentials(self, s3_url_with_credentials):
        logger.info("testing S3 Optimization Cache credentials")
        s3_storage = KiwixStorage(s3_url_with_credentials)
        if not s3_storage.check_credentials(
            list_buckets=True, bucket=True, write=True, read=True, failsafe=True
        ):
            logger.error("S3 cache connection error testing permissions.")
            logger.error(f"  Server: {s3_storage.url.netloc}")
            logger.error(f"  Bucket: {s3_storage.bucket_name}")
            logger.error(f"  Key ID: {s3_storage.params.get('keyid')}")
            logger.error(f"  Public IP: {get_public_ip()}")
            raise ValueError("Unable to connect to Optimization Cache. Check its URL.")
        return s3_storage

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_time=16,
        on_backoff=backoff_hdlr,
    )
    def get_api_content(self, path, **params):
        full_path = self.get_url(API_PREFIX + path, **params)
        logger.debug(f"Retrieving {full_path}")
        response = requests.get(full_path, timeout=10)
        json_data = (
            response.json()
            if response and response.status_code == HTTPStatus.OK
            else None
        )
        return json_data

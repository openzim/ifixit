#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

# import collections
import io
import locale
import re
import threading
import urllib.parse
import zlib
from contextlib import contextmanager
from typing import Union  # , Iterable, List, Tuple

import backoff
import bs4

# import cssbeautifier
import requests
from kiwixstorage import KiwixStorage
from pif import get_public_ip

# from tld import get_fld
from zimscraperlib.download import _get_retry_adapter, stream_file

from .constants import API_PREFIX, DEFAULT_GUIDE_IMAGE_URL
from .shared import Global, logger

# nlink = collections.namedtuple("Link", ("path", "name", "title"))

LOCALE_LOCK = threading.Lock()


class ImageUrlNotFound(Exception):
    pass


def to_path(url: str) -> str:
    """Path-part of an URL, without leading slash"""
    return re.sub(r"^/", "", urllib.parse.urlparse(url).path)


def get_url(path: str, **params) -> str:
    """url-encoded in-source website url for a path"""
    params_str = f"?{urllib.parse.urlencode(params)}" if params else ""
    return f"{Global.conf.main_url.geturl()}{urllib.parse.quote(path)}{params_str}"


def get_url_raw(path: str):
    """in-source website url for a path, untainted"""
    return f"{Global.conf.main_url.geturl()}{path}"


def to_url(value: str) -> str:
    """resolved potentially relative url from in-source link"""
    return value if value.startswith("http") else get_url_raw(value)


def to_rel(url: str) -> Union[None, str]:
    """path from URL if on our main domain, else None"""
    uri = urllib.parse.urlparse(url)
    if uri.netloc != Global.conf.domain:
        return None
    return uri.path


def no_leading_slash(text: str) -> str:
    """text with leading slash removed if present"""
    return re.sub(r"^/", "", text)


def no_trailing_slash(text: str) -> str:
    """text with trailing slash removed if present"""
    return re.sub(r"/$", "", text)


def only_path_of(url: str):
    """normalized path part of an url"""
    return normalize_ident(urllib.parse.urlparse(url).path)


def fetch(path: str, **params) -> str:
    """(source text, actual_paths) of a path from source website

    actual_paths is amn ordered list of paths that were traversed to get to content.
    Without redirection, it should be a single path, equal to request
    Final, target path is always last"""
    session = requests.Session()
    session.mount("http", _get_retry_adapter(10))  # tied to http and https
    resp = session.get(get_url(path, **params), params=params)
    resp.raise_for_status()

    # we have params meaning we requested a page (?pg=xxx)
    # assumption: this must be a category page (so on same domain)
    # we thus need to use redirection target (which lost param) with params
    if params and resp.history:
        return fetch(only_path_of(resp.url), **params)
    return resp.text, [
        no_leading_slash(only_path_of(r.url)) for r in resp.history + [resp]
    ]


def get_soup_of(text: str, unwrap: bool = False):
    """an lxml soup of an HTML string"""
    soup = bs4.BeautifulSoup(text, "lxml")
    if unwrap:
        for elem in ("body", "html"):
            getattr(soup, elem).unwrap()
    return soup


# def get_footer_crumbs_from(soup: bs4.element.Tag) -> List[Tuple[str, str, str]]:
#     """List of (url, name and title) of footer breadcrumbs"""

#     crumbs = []
#     for link in soup.select("#footer_crumbs ul li a[href]"):
#         if not link.attrs.get("href"):
#             continue
#         # might or might not be a Category link
#         try:
#             cat_ident = cat_ident_for(link.attrs["href"])
#         except Exception:
#             cat_ident = None
#         if cat_ident is None or cat_ident in Global.expected_categories:
#             crumbs.append(
#                 nlink(link.attrs["href"][1:], link.string, link.attrs.get("title"))
#             )
#     return crumbs


# def get_footer_links_from(soup: bs4.element.Tag) -> List[Tuple[str, str, str]]:
#     """list of namedtuple(path, name, title) of footer links"""
#     links = []

#     fld = get_fld(Global.conf.main_url.geturl())

#     # Skip some links with no offline value
#     for link in soup.select("#footer_links ul li a"):
#         if link.attrs.get("href") in (
#             "#",
#             "https://blog.wikihow.com/",
#             "/wikiHow:Jobs",
#             "https://www.wikihow.com/wikiHow:Contribute",
#         ):
#             continue

#         path = None
#         if link.attrs.get("href"):
#             url = urllib.parse.urlparse(to_url(link.attrs["href"]))

#             # skip external URLs (if any)
#             if get_fld(url.geturl()) != fld:
#                 continue
#             path = normalize_ident(url.path)[1:]

#         links.append(nlink(path, link.string, link.attrs.get("title")))
#     return links


def get_soup(path: str, **params) -> bs4.BeautifulSoup:
    """an lxml soup of a path on source website"""
    content, paths = fetch(path, **params)
    return get_soup_of(content), paths


# def soup_link_finder(elem: bs4.element.Tag) -> bool:
#     """bs4's find_all-friendly selector for linked styles in wikiHow"""
#     return (
#         elem.name == "link"
#         and elem.attrs.get("href")
#         and (elem.attrs.get("as") == "style" or elem.attrs.get("rel") == "stylesheet")
#     )


def get_digest(url: str) -> str:
    """simple digest of an url for mapping purpose"""
    return str(zlib.adler32(url.encode("UTF-8")))


# def cat_ident_for(href: str) -> str:
#     """decoded name of a category from a link target"""
#     return normalize_ident(href).split(":", 1)[1]


# def fix_pagination_links(soup: bs4.element.Tag):
#     """Replace ?pg= to _pg= in pagination links"""
#     for a in soup.select("#large_pagination a[href]"):
#         a["href"] = a["href"].replace("?pg=", "_pg=")


# def get_categorylisting_url():
#     return normalize_ident(
#         urllib.parse.urlparse(requests.get(to_url("/Special:CategoryListing")).url).path
#     )[1:]


# def get_youtube_id_from(url: str) -> str:
#     """Youtube video Id from a youtube URL"""
#     uri = urllib.parse.urlparse(url)
#     if uri.path.startswith("/embed/"):
#         m = re.match(r"^/embed/(?P<id>[^/]+)", uri.path)
#         if m:
#             return m.groupdict().get("id")
#     if uri.path.startswith("/watch"):
#         return urllib.parse.parse_qs(uri.query).get("v", [None]).pop()


# def normalize_youtube_url(url: str) -> str:
#     """harmonize youtube-URL to use a single (public viewing) format

#     format: https://www.youtube.com/watch?v=C1vI8k-JEsQ"""

#     yid = get_youtube_id_from(url)
#     if yid:
#         return f"https://www.youtube.com/watch?v={yid}"
#     return url


def normalize_ident(ident: str) -> str:
    """URL-decoded category identifier"""
    return urllib.parse.unquote(ident)


# def article_ident_for(href: str) -> str:
#     """decoded name of an article from a link target"""
#     return normalize_ident(to_rel(href))[1:]


# def parse_css(style: str) -> Tuple[str, List[Tuple[str, str]]]:
#     """(css, resources) of transformed CSS string and resources list

#     reads a CSS string and returns it transformed
#     with url() replaced by offlinable path.

#     resources list is list of tuples, each containing the URL to get data from
#     and the path to store it at.
#     ex: ("http://goto.img/hello.png", "img/hello.png")"""

#     output = ""
#     resources = []

#     def write(line):
#         nonlocal output
#         output += line + "\n"

#     pattern = "url("
#     for line in cssbeautifier.beautify(style).split("\n"):
#         if pattern not in line:
#             write(line)
#             continue

#         start = line.index(pattern) + len(pattern)
#         end = line.index(")")

#         # check whether it's quoted or not
#         if line[start + 1] in ("'", '"'):
#             start += 1
#             end -= 1

#         url = line[start:end]

#         if url.startswith("data:"):
#             write(line)
#             continue

#         path = f"assets/{get_digest(url)}"
#         resources.append((url, path))
#         # resources are added on same level (assets/xxx) as css itself
#         write(line[0:start] + "../" + path + line[end:])

#     return output, resources


# def first(*args: Iterable[object]) -> object:
#     """first non-None value from *args ; fallback to empty string"""
#     return next((item for item in args if item is not None), "")


# def rebuild_uri(
#     uri: urllib.parse.ParseResult,
#     scheme: str = None,
#     username: str = None,
#     password: str = None,
#     hostname: str = None,
#     port: Union[str, int] = None,
#     path: str = None,
#     params: str = None,
#     query: str = None,
#     fragment: str = None,
#     failsafe: bool = False,
# ) -> urllib.parse.ParseResult:
#     """new named tuple from uri with requested part updated"""
#     try:
#         username = first(username, uri.username, "")
#         password = first(password, uri.password, "")
#         hostname = first(hostname, uri.hostname, "")
#         port = first(port, uri.port, "")
#         netloc = (
#             f"{username}{':' if password else ''}{password}"
#             f"{'@' if username or password else ''}{hostname}"
#             f"{':' if port else ''}{port}"
#         )
#         return urllib.parse.urlparse(
#             urllib.parse.urlunparse(
#                 (
#                     first(scheme, uri.scheme),
#                     netloc,
#                     first(path, uri.path),
#                     first(params, uri.params),
#                     first(query, uri.query),
#                     first(fragment, uri.fragment),
#                 )
#             )
#         )
#     except Exception as exc:
#         if failsafe:
#             logger.error(
#                 f"Failed to rebuild "  # lgtm [py/clear-text-logging-sensitive-data]
#                 f"URI {uri} with {scheme=} {username=} {password=} "
#                 f"{hostname=} {port=} {path=} "
#                 f"{params=} {query=} {fragment=} - {exc}"
#             )
#             return uri
#         raise exc


def get_version_ident_for(url: str) -> str:
    """~version~ of the URL data to use for comparisons. Built from headers"""
    try:
        resp = requests.head(url)
        headers = resp.headers
    except Exception:
        logger.warning(f"Unable to HEAD {url}")
        try:
            _, headers = stream_file(
                url=url,
                byte_stream=io.BytesIO(),
                block_size=1,
                only_first_block=True,
            )
        except Exception:
            logger.warning(f"Unable to query image at {url}")
            return

    for header in ("ETag", "Last-Modified", "Content-Length"):
        if headers.get(header):
            return headers.get(header)

    return "-1"


def setup_s3_and_check_credentials(s3_url_with_credentials):
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


# #!/usr/bin/env python

# import requests
# import urllib.request

# import backoff

# from os.path import exists, join
# from os import getcwd, mkdir

# from ifixittozim import logger, LANGS


@contextmanager
def setlocale(name):
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, saved)


def backoff_hdlr(details):
    logger.warning(
        "Backing off {wait:0.1f} seconds after {tries} tries "
        "calling function {target} with args {args} and kwargs "
        "{kwargs}".format(**details)
    )


@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_time=16,
    on_backoff=backoff_hdlr,
)
def get_api_content(path, **params):
    full_path = get_url(API_PREFIX + path, **params)
    logger.debug(f"Retrieving {full_path}")
    response = requests.get(full_path)
    json_data = response.json() if response and response.status_code == 200 else None
    return json_data


# @backoff.on_exception(backoff.expo,
#                       urllib.error.URLError,
#                       max_time=16,
#                       on_backoff=backoff_hdlr)
# def get_file_content(url, filename):
#     urllib.request.urlretrieve(url, filename)

# def get_cache_path():
#     cwd = getcwd()
#     cachePath = join(cwd, 'cache');
#     while not exists(cachePath):
#         mkdir(cachePath)
#     for asset_kind in ['categories', 'guides', 'images']:
#         subCachePath = join(cwd, 'cache', asset_kind)
#         while not exists(subCachePath):
#             mkdir(subCachePath)
#         if asset_kind not in ['images']:
#             for lang in LANGS:
#                 subCachePath = join(cwd, 'cache', asset_kind, lang);
#                 while not exists(subCachePath):
#                     mkdir(subCachePath)
#     return cachePath

# def get_assets_path():
#     cwd = getcwd()
#     assetPath = join(cwd, 'assets')
#     return assetPath

# def get_dist_path():
#     cwd = getcwd()
#     dist_path = join(cwd, 'dist');
#     while not exists(dist_path):
#         mkdir(dist_path)
#     for asset_kind in ['categories', 'guides', 'images', 'home']:
#         subCachePath = join(cwd, 'dist', asset_kind)
#         while not exists(subCachePath):
#             mkdir(subCachePath)
#         if asset_kind not in ['images']:
#             for lang in LANGS:
#                 subCachePath = join(cwd, 'dist', asset_kind, lang);
#                 while not exists(subCachePath):
#                     mkdir(subCachePath)
#     return dist_path


def guides_in_progress(guides, in_progress=True):
    if in_progress:
        return [guide for guide in guides if "GUIDE_IN_PROGRESS" in guide["flags"]]
    else:
        return [guide for guide in guides if "GUIDE_IN_PROGRESS" not in guide["flags"]]


def get_image_path(image_url):
    return f"../{Global.imager.defer(url=image_url)}"


def _get_image_url_search(obj, for_guide=False):
    if "standard" in obj:
        return obj["standard"]
    elif "medium" in obj:
        return obj["medium"]
    elif "large" in obj:
        return obj["large"]
    elif "original" in obj:
        return obj["original"]
    elif for_guide:
        return DEFAULT_GUIDE_IMAGE_URL
    else:
        raise ImageUrlNotFound(f"Unable to find image URL in object {obj}")


def get_image_url(obj, for_guide=False):
    if "image" in obj and obj["image"]:
        return _get_image_url_search(obj["image"], for_guide)
    else:
        return _get_image_url_search(obj, for_guide)

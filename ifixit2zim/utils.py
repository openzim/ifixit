#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import io
import re
import urllib.parse
import zlib
from typing import Union

import backoff
import bs4
import requests
from kiwixstorage import KiwixStorage
from pif import get_public_ip
from zimscraperlib.download import _get_retry_adapter, stream_file

from .constants import API_PREFIX
from .shared import Global, logger


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


def get_soup(path: str, **params) -> bs4.BeautifulSoup:
    """an lxml soup of a path on source website"""
    content, paths = fetch(path, **params)
    return get_soup_of(content), paths


def get_digest(url: str) -> str:
    """simple digest of an url for mapping purpose"""
    return str(zlib.adler32(url.encode("UTF-8")))


def normalize_ident(ident: str) -> str:
    """URL-decoded category identifier"""
    return urllib.parse.unquote(ident)


def get_version_ident_for(url: str) -> str:
    """~version~ of the URL data to use for comparisons. Built from headers"""
    try:
        resp = requests.head(url)
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

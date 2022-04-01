#!/usr/bin/env python

import requests
import urllib.request 

from contextlib import contextmanager
import locale
import threading
import backoff

from os.path import exists, join
from os import getcwd, mkdir

from ifixittozim import logger, LANGS

LOCALE_LOCK = threading.Lock()

@contextmanager
def setlocale(name):
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, saved)


def backoff_hdlr(details):
    logger.WARN("Backing off {wait:0.1f} seconds after {tries} tries "
           "calling function {target} with args {args} and kwargs "
           "{kwargs}".format(**details))
           
@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_time=16,
                      on_backoff=backoff_hdlr)
def get_api_content(api_base_url, path):
    response = requests.get(api_base_url + path)
    json_data = response.json() if response and response.status_code == 200 else None
    return json_data


@backoff.on_exception(backoff.expo,
                      urllib.error.URLError,
                      max_time=16,
                      on_backoff=backoff_hdlr)
def get_file_content(url, filename):
    urllib.request.urlretrieve(url, filename)

def get_cache_path():
    cwd = getcwd()
    cachePath = join(cwd, 'cache');
    while not exists(cachePath):
        mkdir(cachePath)
    for asset_kind in ['categories', 'guides', 'images']:
        subCachePath = join(cwd, 'cache', asset_kind)
        while not exists(subCachePath):
            mkdir(subCachePath)
        if asset_kind not in ['images']:
            for lang in LANGS:
                subCachePath = join(cwd, 'cache', asset_kind, lang);
                while not exists(subCachePath):
                    mkdir(subCachePath)
    return cachePath

def get_assets_path():
    cwd = getcwd()
    assetPath = join(cwd, 'assets')
    return assetPath

def get_dist_path():
    cwd = getcwd()
    dist_path = join(cwd, 'dist');
    while not exists(dist_path):
        mkdir(dist_path)
    for asset_kind in ['categories', 'guides', 'images', 'home']:
        subCachePath = join(cwd, 'dist', asset_kind)
        while not exists(subCachePath):
            mkdir(subCachePath)
        if asset_kind not in ['images']:
            for lang in LANGS:
                subCachePath = join(cwd, 'dist', asset_kind, lang);
                while not exists(subCachePath):
                    mkdir(subCachePath)
    return dist_path
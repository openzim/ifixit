#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
# pylint: disable=cyclic-import

import locale
import logging
import re
import threading
import urllib
from contextlib import contextmanager
from datetime import date, datetime

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape
from zimscraperlib.logging import getLogger as lib_getLogger
from zimscraperlib.zim.creator import Creator

from .constants import (
    DEFAULT_DEVICE_IMAGE_URL,
    DEFAULT_GUIDE_IMAGE_URL,
    DEFAULT_HOMEPAGE,
    DEFAULT_USER_IMAGE_URLS,
    DEFAULT_WIKI_IMAGE_URL,
    NAME,
    NOT_YET_AVAILABLE,
    ROOT_DIR,
    UNAVAILABLE_OFFLINE,
)

LOCALE_LOCK = threading.Lock()


class ImageUrlNotFound(Exception):
    pass


@contextmanager
def setlocale(name):
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, saved)


class Global:
    """Shared context accross all scraper components"""

    debug = False
    logger = lib_getLogger(
        NAME,
        level=logging.INFO,
        log_format="[%(threadName)s::%(asctime)s] %(levelname)s:%(message)s",
    )
    conf = None

    metadata = {}

    creator = None
    imager = None
    env = None
    lock = threading.Lock()

    null_categories = set()
    ifixit_external_content = set()
    final_hrefs = dict()

    @staticmethod
    def set_debug(value):
        Global.debug = value
        level = logging.DEBUG if value else logging.INFO
        Global.logger.setLevel(level)
        for handler in Global.logger.handlers:
            handler.setLevel(level)

    @staticmethod
    def setup():
        # order matters are there are references between them

        # images handled on a different queue.
        # mostly network I/O to retrieve and/or upload image.
        # if not in S3 bucket, convert/optimize webp image
        # svg images, stored but not optimized
        from .executor import Executor

        Global.img_executor = Executor(
            queue_size=100,
            nb_workers=50,
            prefix="IMG-T-",
        )

        from .imager import Imager

        Global.imager = Imager()

        Global.creator = Creator(
            filename=Global.conf.output_dir.joinpath(Global.conf.fname),
            main_path=DEFAULT_HOMEPAGE,
            favicon_path="illustration",
            language=Global.conf.language["iso-639-3"],
            workaround_nocancel=False,
            title=Global.conf.title,
            description=Global.conf.description,
            creator=Global.conf.author,
            publisher=Global.conf.publisher,
            name=Global.conf.name,
            tags=";".join(Global.conf.tags),
            date=date.today(),
        ).config_verbose(True)

        # jinja2 environment setup
        Global.env = Environment(
            loader=FileSystemLoader(ROOT_DIR.joinpath("templates")),
            autoescape=select_autoescape(),
        )
        Global.env.globals["raise"] = Global._raise_helper
        Global.env.globals["str"] = lambda x: str(x)
        Global.env.filters["guides_in_progress"] = Global.guides_in_progress
        Global.env.filters["category_count_parts"] = Global.category_count_parts
        Global.env.filters["category_count_tools"] = Global.category_count_tools
        Global.env.filters["get_image_path"] = Global.get_image_path
        Global.env.filters["get_image_url"] = Global.get_image_url
        Global.env.filters["cleanup_rendered_content"] = Global.cleanup_rendered_content
        Global.env.filters[
            "get_timestamp_day_rendered"
        ] = Global.get_timestamp_day_rendered
        Global.env.filters["get_item_comments_count"] = Global.get_item_comments_count
        Global.env.filters[
            "get_guide_total_comments_count"
        ] = Global.get_guide_total_comments_count
        Global.env.filters["get_user_display_name"] = Global.get_user_display_name

    @staticmethod
    def _raise_helper(msg):
        raise Exception(msg)

    @staticmethod
    def guides_in_progress(guides, in_progress=True):
        if in_progress:
            return [guide for guide in guides if "GUIDE_IN_PROGRESS" in guide["flags"]]
        return [guide for guide in guides if "GUIDE_IN_PROGRESS" not in guide["flags"]]

    @staticmethod
    def category_count_parts(category):
        if "parts" not in category:
            return 0
        if "total" not in category["parts"]:
            return 0
        return category["parts"]["total"]

    @staticmethod
    def category_count_tools(category):
        if "tools" not in category:
            return 0
        return len(category["tools"])

    @staticmethod
    def get_image_path(image_url):
        return Global.imager.defer(url=image_url)

    @staticmethod
    def _get_image_url_search(obj, for_guide, for_device, for_wiki, for_user):
        if "standard" in obj:
            return obj["standard"]
        if "medium" in obj:
            return obj["medium"]
        if "large" in obj:
            return obj["large"]
        if "original" in obj:
            return obj["original"]
        if for_guide:
            return DEFAULT_GUIDE_IMAGE_URL
        if for_device:
            return DEFAULT_DEVICE_IMAGE_URL
        if for_wiki:
            return DEFAULT_WIKI_IMAGE_URL
        if for_user and "userid" in obj:
            idx = obj["userid"] % len(DEFAULT_USER_IMAGE_URLS)
            return DEFAULT_USER_IMAGE_URLS[idx]
        raise ImageUrlNotFound(f"Unable to find image URL in object {obj}")

    @staticmethod
    def get_image_url(
        obj, for_guide=False, for_device=False, for_wiki=False, for_user=False
    ):
        if "image" in obj and obj["image"]:
            return Global._get_image_url_search(
                obj["image"], for_guide, for_device, for_wiki, for_user
            )
        return Global._get_image_url_search(
            obj, for_guide, for_device, for_wiki, for_user
        )

    guide_regex_full = re.compile(
        r"href=\"https://\w*\.ifixit\.\w*/Guide/.*/(?P<guide_id>\d*)\""
    )
    guide_regex_rel = re.compile(r"href=\"/Guide/.*/(?P<guide_id>\d*).*?\"")

    gbl_image_regex = r"<img(?P<image_before>.*?)src\s*=\s*\"(?P<image_url>.*?)\""
    gbl_href_regex = r"href\s*=\s*\"(?P<href_url>.*?)\""
    gbl_youtube_regex = (
        r"<div(?P<part1>(?!.*<div.*).+?)youtube-player"
        r"(?P<part2>.+?)src=[\\\"']+(?P<youtubesrc>.+?)\"(?P<part3>.+?)</div>"
    )
    gbl_bgd_image_regex = (
        r"background-image:url\((?P<quote1>&quot;|\"|')"
        r"(?P<bgdimgurl>.*?)(?P<quote2>&quot;|\"|')\)"
    )
    gbl_video_regex = r"<video(?P<videostuff>.*)</video>"
    gbl_iframe_regex = r"<iframe.*?src\s*=\s*\"(?P<iframe_url>.*?)\".*?</iframe>"
    gbl_regex = re.compile(
        f"{gbl_image_regex}|{gbl_href_regex}|{gbl_youtube_regex}|{gbl_bgd_image_regex}"
        f"|{gbl_video_regex}|{gbl_iframe_regex}"
    )

    href_anchor_regex = r"^(?P<anchor>#.*)$"
    href_object_kind_regex = (
        r"^(?:https*://[\w\.]*(?:ifixit)[\w\.]*)*/"
        r"((?:(?P<kind>"
        + "|".join(NOT_YET_AVAILABLE + UNAVAILABLE_OFFLINE)
        + r")(?:/.+)?)"
        r"|(?:(?P<guide>Guide|Anleitung|Guía|Guida|Tutoriel|Teardown)/"
        r"(?P<guidetitle>.+)/(?P<guideid>\d+)(?P<guideafter>#.*)?.*)"
        r"|(?:(?P<device>Device|Topic)/(?P<devicetitle>[\w%_\.-]+)"
        r"(?P<deviceafter>#.*)?.*)"
        r"|(?P<user>User)/(?P<userid>\d*)/(?P<usertitle>[\w%_\.+'-]+)"
        r"(?P<userafter>#.*)?.*"
        r"|(?:(?P<info>Info)/(?P<infotitle>[\w%_\.-]+)(?P<infoafter>#.*)?.*))$"
    )
    href_regex = re.compile(
        f"{href_anchor_regex}|{href_object_kind_regex}", flags=re.IGNORECASE
    )

    @staticmethod
    def _process_external_url(url, rel_prefix):
        if "ifixit" in url:
            Global.ifixit_external_content.add(url)
        return f"{rel_prefix}home/external_content?url={urllib.parse.quote(url)}"

    @staticmethod
    def _process_unrecognized_href(url, rel_prefix):
        return Global._process_external_url(url, rel_prefix)

    def _process_href_regex_dynamics(href, rel_prefix):
        if "Guide/login/register" in href or "Guide/new" in href:
            return (
                f"{rel_prefix}home/unavailable_offline"
                f"?url={urllib.parse.quote(href)}"
            )
        return None

    def _process_href_regex_nomatch(href, rel_prefix, match):
        if match:
            return None
        return Global._process_unrecognized_href(href, rel_prefix)

    def _process_href_regex_anchor(href, rel_prefix, match):
        if not match.group("anchor"):
            return None
        return f"{match.group('anchor')}"

    def _process_href_regex_guide(href, rel_prefix, match):
        if not match.group("guide"):
            return None
        link = Global.get_guide_link_from_props(
            guideid=match.group("guideid"),
            guidetitle=urllib.parse.unquote_plus(match.group("guidetitle")),
        )
        return f"{rel_prefix}{link}{match.group('guideafter') or ''}"

    def _process_href_regex_device(href, rel_prefix, match):
        if not match.group("device"):
            return None
        link = Global.get_category_link_from_props(
            category_title=urllib.parse.unquote_plus(match.group("devicetitle"))
        )
        return f"{rel_prefix}{link}{match.group('deviceafter') or ''}"

    def _process_href_regex_info(href, rel_prefix, match):
        if not match.group("info"):
            return None
        link = Global.get_info_link_from_props(
            info_title=urllib.parse.unquote_plus(match.group("infotitle"))
        )
        return f"{rel_prefix}{link}" f"{match.group('infoafter') or ''}"

    def _process_href_regex_user(href, rel_prefix, match):
        if not match.group("user"):
            return None
        link = Global.get_user_link_from_props(
            userid=match.group("userid"),
            usertitle=urllib.parse.unquote_plus(match.group("usertitle")),
        )
        return f"{rel_prefix}{link}" f"{match.group('userafter') or ''}"

    def _process_href_regex_kind(href, rel_prefix, match):
        if not match.group("kind"):
            return None
        if match.group("kind").lower() in NOT_YET_AVAILABLE:
            return (
                f"{rel_prefix}home/not_yet_available" f"?url={urllib.parse.quote(href)}"
            )
        if match.group("kind").lower() in UNAVAILABLE_OFFLINE:
            return (
                f"{rel_prefix}home/unavailable_offline"
                f"?url={urllib.parse.quote(href)}"
            )
        raise Exception(
            f"Unsupported kind '{match.group('kind')}' in _process_href_regex"
        )

    @staticmethod
    def normalize_href(href):
        if href in Global.final_hrefs:
            return Global.final_hrefs[href]
        try:
            logger.debug(f"Normalizing href {href}")
            # final_href = requests.head(href).headers.get("Location")
            # if final_href is None:
            #     logger.debug(f"Failed to HEAD {href}, falling back to GET")
            final_href = requests.get(href, stream=True).url
            # parse final href and remove scheme + netloc + slash
            parsed_final_href = urllib.parse.urlparse(final_href)
            parsed_href = urllib.parse.urlparse(href)
            chars_to_remove = len(parsed_final_href.scheme + "://")

            # remove domain if redirect is on same domain (almost always)
            if parsed_final_href.netloc == parsed_href.netloc:
                chars_to_remove += len(parsed_final_href.netloc)

            final_href = final_href[chars_to_remove:]
            final_href = urllib.parse.unquote(final_href)
        except Exception:
            # this is quite expected for some missing items ; this will be taken care
            # of at retrieval, no way to do something better
            final_href = href
        Global.final_hrefs[href] = final_href
        logger.debug(f"Result is {final_href}")
        return final_href

    @staticmethod
    def _process_href_regex(href, rel_prefix):
        if href.startswith("/"):
            href = Global.conf.main_url.geturl() + href
        if href.startswith("http") and "ifixit.com/" in href:
            href = Global.normalize_href(href)
            href = urllib.parse.quote(href)
        match = Global.href_regex.search(href)
        res = (
            Global._process_href_regex_dynamics(href, rel_prefix)
            or Global._process_href_regex_nomatch(href, rel_prefix, match)
            or Global._process_href_regex_anchor(href, rel_prefix, match)
            or Global._process_href_regex_guide(href, rel_prefix, match)
            or Global._process_href_regex_device(href, rel_prefix, match)
            or Global._process_href_regex_info(href, rel_prefix, match)
            or Global._process_href_regex_user(href, rel_prefix, match)
            or Global._process_href_regex_kind(href, rel_prefix, match)
        )
        if res is None:
            raise Exception("Unsupported match in _process_href_regex")
        return res

    @staticmethod
    def _process_youtube(match, rel_prefix):
        return (
            f'<a href="'
            f"{Global._process_external_url(match.group('youtubesrc'), rel_prefix)}\">"
            f"<div{Global.cleanup_rendered_content(match.group('part1'), rel_prefix)}"
            "youtube-player"
            f"{Global.cleanup_rendered_content(match.group('part2'), rel_prefix)}"
            f"{Global.cleanup_rendered_content(match.group('part3'), rel_prefix)}"
            "</div></a>"
        )

    @staticmethod
    def _process_bgdimgurl(match, rel_prefix):
        return (
            f"background-image:url({match.group('quote1')}{rel_prefix}"
            f"{Global.get_image_path(match.group('bgdimgurl'))}"
            f"{match.group('quote2')})"
        )

    @staticmethod
    def _process_video(match, rel_prefix):
        return "<p>Video not scrapped</p>"

    @staticmethod
    def _process_iframe(match, rel_prefix):
        return (
            f'<a href="'
            f"{Global._process_external_url(match.group('iframe_url'), rel_prefix)}"
            f'">External content</a>'
        )

    @staticmethod
    def _process_gbl_regex(match, rel_prefix):
        if match.group("image_url"):
            return (
                f"<img{match.group('image_before')}src=\"{rel_prefix}"
                f"{Global.get_image_path(match.group('image_url'))}\""
            )
        if match.group("href_url"):
            href = Global._process_href_regex(match.group("href_url"), rel_prefix)
            return f'href="{href}"'
        if match.group("youtubesrc"):
            return Global._process_youtube(match, rel_prefix)
        if match.group("bgdimgurl"):
            return Global._process_bgdimgurl(match, rel_prefix)
        if match.group("videostuff"):
            return Global._process_video(match, rel_prefix)
        if match.group("iframe_url"):
            return Global._process_iframe(match, rel_prefix)
        raise Exception("Unsupported match in cleanup_rendered_content")

    @staticmethod
    def cleanup_rendered_content(content, rel_prefix="../"):
        if Global.conf.no_cleanup:
            return content
        return re.sub(
            Global.gbl_regex,
            lambda match: Global._process_gbl_regex(match, rel_prefix),
            content,
        )

    @staticmethod
    def convert_title_to_filename(title):
        return re.sub(r"\s", "_", title)

    @staticmethod
    def add_html_item(path, title, content):
        with Global.lock:
            logger.debug(f"Adding item in ZIM at path '{path}'")
            Global.creator.add_item_for(
                path=path,
                title=title,
                content=content,
                mimetype="text/html",
                is_front=True,
            )

    @staticmethod
    def add_redirect(path, target_path):
        with Global.lock:
            logger.debug(f"Adding redirect in ZIM from '{path}' to '{target_path}'")
            Global.creator.add_redirect(
                path=path,
                target_path=target_path,
            )

    @staticmethod
    def get_item_comments_count(item):
        if "comments" not in item:
            return 0
        total = 0
        for comment in item["comments"]:
            total += 1
            if "replies" in comment:
                total += len(comment["replies"])
        return total

    @staticmethod
    def get_guide_total_comments_count(guide):
        total = Global.get_item_comments_count(guide)
        for step in guide["steps"]:
            total += Global.get_item_comments_count(step)
        return total

    @staticmethod
    def get_timestamp_day_rendered(timestamp):
        with setlocale("en_GB"):
            if timestamp:
                return datetime.strftime(datetime.fromtimestamp(timestamp), "%x")
            return ""

    @staticmethod
    def get_user_display_name(user):
        if user["username"] and len(user["username"]) > 0:
            return user["username"]
        if user["unique_username"] and len(user["unique_username"]) > 0:
            return f"@{user['unique_username']}"
        return "Anonymous"


class GlobalMixin:
    @property
    def conf(self):
        return Global.conf

    @property
    def metadata(self):
        return Global.metadata

    @property
    def creator(self):
        return Global.creator

    @property
    def lock(self):
        return Global.lock

    @property
    def imager(self):
        return Global.imager

    @property
    def executor(self):
        return Global.executor

    @property
    def env(self):
        return Global.env

    @property
    def info_wiki_template(self):
        return Global.info_wiki_template

    @property
    def ifixit_external_content(self):
        return Global.ifixit_external_content


logger = Global.logger

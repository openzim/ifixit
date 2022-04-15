#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
# pylint: disable=cyclic-import

import datetime
import logging
import re
import threading
import urllib

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
    ROOT_DIR,
)


class ImageUrlNotFound(Exception):
    pass


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
            queue_size=20,
            nb_workers=10,
            prefix="IMG-T-",
        )

        from .imager import Imager

        Global.imager = Imager()

        Global.creator = Creator(
            filename=Global.conf.output_dir.joinpath(Global.conf.fname),
            main_path=DEFAULT_HOMEPAGE,
            favicon_path="illustration",
            language=Global.conf.language["iso-639-3"],
            title=Global.conf.title,
            description=Global.conf.description,
            creator=Global.conf.author,
            publisher=Global.conf.publisher,
            name=Global.conf.name,
            tags=";".join(Global.conf.tags),
            date=datetime.date.today(),
        ).config_verbose(True)

        # jinja2 environment setup
        Global.env = Environment(
            loader=FileSystemLoader(ROOT_DIR.joinpath("templates")),
            autoescape=select_autoescape(),
        )
        Global.env.globals["raise"] = Global._raise_helper
        Global.env.filters["guides_in_progress"] = Global.guides_in_progress
        Global.env.filters["get_image_path"] = Global.get_image_path
        Global.env.filters["get_image_url"] = Global.get_image_url
        Global.env.filters["cleanup_rendered_content"] = Global.cleanup_rendered_content

    @staticmethod
    def _raise_helper(msg):
        raise Exception(msg)

    @staticmethod
    def guides_in_progress(guides, in_progress=True):
        if in_progress:
            return [guide for guide in guides if "GUIDE_IN_PROGRESS" in guide["flags"]]
        return [guide for guide in guides if "GUIDE_IN_PROGRESS" not in guide["flags"]]

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
            idx = obj["userid"] % len(DEFAULT_USER_IMAGE_URLS) + 1
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
    gbl_regex = re.compile(
        f"{gbl_image_regex}|{gbl_href_regex}|{gbl_youtube_regex}|{gbl_bgd_image_regex}"
    )

    href_anchor_regex = r"^(?P<anchor>#.*)$"
    href_object_kind_regex = (
        r"^(?:https*://[\w\.]*(?:ifixit)[\w\.]*)*/"
        r"((?:(?P<kind>Team|Wiki|Store|Boutique|Tienda).*/(?P<object>[\w%_\.-]+)"
        r"(?P<after>#.*)?.*)"
        r"|(?:(?P<guide>Guide|Anleitung|Guía|Guida|Tutoriel|Teardown)/"
        r"(?P<guidetitle>.+)/(?P<guideid>\d+)(?P<guideafter>#.*)?.*)"
        r"|(?:(?P<device>Device|Topic)/(?P<devicetitle>[\w%_\.-]+)"
        r"(?P<deviceafter>#.*)?.*)"
        r"|(?P<user>User)/(?P<userid>\d*)/(?P<usertitle>[\w%_\.+-]+)"
        r"(?P<userafter>#.*)?.*"
        r"|(?:(?P<info>Info)/(?P<infotitle>[\w%_\.-]+)(?P<infoafter>#.*)?.*))$"
    )
    href_regex = re.compile(
        f"{href_anchor_regex}|{href_object_kind_regex}", flags=re.IGNORECASE
    )

    @staticmethod
    def _process_external_url(url, rel_prefix):
        return f"{rel_prefix}home/external_content?url={urllib.parse.quote(url)}"

    @staticmethod
    def _process_unrecognized_href(url, rel_prefix):
        try:
            resp = requests.head(url)
            headers = resp.headers
        except Exception as exc:
            logger.warning(f"Unable to HEAD unrecognized href: {url}")
            logger.exception(exc)
            return Global._process_external_url(url, rel_prefix)

        if headers.get("Content-Type").startswith("image/"):
            return f"{rel_prefix}{Global.get_image_path(url)}"

        return Global._process_external_url(url, rel_prefix)

    @staticmethod
    def _process_href_regex(href, rel_prefix):
        if "Guide/login/register" in href:
            return (
                f"{rel_prefix}home/unavailable_offline"
                f"?url={urllib.parse.quote(href)}"
            )
        if "Guide/new" in href:
            return (
                f"{rel_prefix}home/unavailable_offline"
                f"?url={urllib.parse.quote(href)}"
            )

        match = Global.href_regex.search(href)

        if not match:
            return Global._process_unrecognized_href(href, rel_prefix)

        if match.group("anchor"):
            return f"{match.group('anchor')}"
        if match.group("guide"):
            link = Global.get_guide_link_from_props(
                guideid=match.group("guideid"), guidetitle=match.group("guidetitle")
            )
            return f"{rel_prefix}{link}{match.group('guideafter') or ''}"
        if match.group("device"):
            link = Global.get_category_link_from_props(
                category_title=match.group("devicetitle")
            )
            return f"{rel_prefix}{link}{match.group('deviceafter') or ''}"
        if match.group("info"):
            link = Global.get_info_link_from_props(info_title=match.group("infotitle"))
            return f"{rel_prefix}{link}" f"{match.group('infoafter') or ''}"
        if match.group("user"):
            link = Global.get_user_link_from_props(
                userid=match.group("userid"), usertitle=match.group("usertitle")
            )
            return f"{rel_prefix}{link}" f"{match.group('userafter') or ''}"
        if match.group("kind"):
            if match.group("kind").lower() in ["user", "team", "wiki"]:
                return (
                    f"{rel_prefix}home/not_yet_available"
                    f"?url={urllib.parse.quote(href)}"
                )
            if match.group("kind").lower() in ["store", "boutique", "tienda"]:
                return (
                    f"{rel_prefix}home/unavailable_offline"
                    f"?url={urllib.parse.quote(href)}"
                )
            raise Exception(
                f"Unsupported kind '{match.group('kind')}' in _process_href_regex"
            )
        raise Exception("Unsupported match in _process_href_regex")

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
        raise Exception("Unsupported match in cleanup_rendered_content")

    @staticmethod
    def cleanup_rendered_content(content, rel_prefix="../"):
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
            Global.creator.add_item_for(
                path=path,
                title=title,
                content=content,
                mimetype="text/html",
                is_front=True,
            )
            alternate_path = path.replace("+", "_")
            if alternate_path != path:
                Global.creator.add_redirect(
                    path=alternate_path,
                    target_path=path,
                )


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


logger = Global.logger

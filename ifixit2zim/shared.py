#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
# pylint: disable=cyclic-import

import datetime
import logging
import re
import threading

from jinja2 import Environment, FileSystemLoader, select_autoescape
from zimscraperlib.logging import getLogger as lib_getLogger
from zimscraperlib.zim.creator import Creator

from .constants import (
    DEFAULT_DEVICE_IMAGE_URL,
    DEFAULT_GUIDE_IMAGE_URL,
    DEFAULT_HOMEPAGE,
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
        Global.env.filters["guides_in_progress"] = Global.guides_in_progress
        Global.env.filters["get_image_path"] = Global.get_image_path
        Global.env.filters["get_image_url"] = Global.get_image_url
        Global.env.filters["cleanup_rendered_content"] = Global.cleanup_rendered_content

    @staticmethod
    def guides_in_progress(guides, in_progress=True):
        if in_progress:
            return [guide for guide in guides if "GUIDE_IN_PROGRESS" in guide["flags"]]
        return [guide for guide in guides if "GUIDE_IN_PROGRESS" not in guide["flags"]]

    @staticmethod
    def get_image_path(image_url):
        return f"../{Global.imager.defer(url=image_url)}"

    @staticmethod
    def _get_image_url_search(obj, for_guide, for_device, for_wiki):
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
        raise ImageUrlNotFound(f"Unable to find image URL in object {obj}")

    @staticmethod
    def get_image_url(obj, for_guide=False, for_device=False, for_wiki=False):
        if "image" in obj and obj["image"]:
            return Global._get_image_url_search(
                obj["image"], for_guide, for_device, for_wiki
            )
        return Global._get_image_url_search(obj, for_guide, for_device, for_wiki)

    guide_regex_full = re.compile(
        r"href=\"https://\w*\.ifixit\.\w*/Guide/.*/(?P<guide_id>\d*)\""
    )
    guide_regex_rel = re.compile(r"href=\"/Guide/.*/(?P<guide_id>\d*).*?\"")

    gbl_image_regex = r"<img(?P<image_before>.*?)src\s*=\s*\"(?P<image_url>.*?)\""
    gbl_href_regex = r"href\s*=\s*\"(?P<href_url>.*?)\""
    gbl_regex = re.compile(f"{gbl_image_regex}|{gbl_href_regex}")

    href_anchor_regex = r"^(?P<anchor>#.*)$"
    href_object_kind_regex = (
        r"^(?:https*://[\w\.]*(?:ifixit)[\w\.]*)*/"
        r"(?P<kind>Device|Topic|User|Team|Info|Wiki|Store|Boutique|Tienda|Guide|"
        r"Anleitung|Guía|Guida|Tutoriel).*/(?P<object>[\w%_-]*)(?P<after>.*)$"
    )
    href_regex = re.compile(
        f"{href_anchor_regex}|{href_object_kind_regex}", flags=re.IGNORECASE
    )

    @staticmethod
    def _process_href_regex(href):
        if "Guide/login/register" in href:
            return "../home/placeholder.html"
        if "Guide/new" in href:
            return "../home/placeholder.html"

        found_none = True
        found_one = False
        for match in Global.href_regex.finditer(href):
            if found_one:
                logger.warn(f"Too many matches in _process_href_regex for '{href}'")
                return href
            found_one = True
            found_none = False
            if match.group("anchor"):
                return f"ANCHOR_{match.group('anchor')}"
            if match.group("kind"):
                if match.group("kind").lower() in ["device", "topic"]:
                    return (
                        f"{Global.get_category_link(match.group('object'))}"
                        f"{match.group('after')}"
                    )
                if match.group("kind").lower() in ["info"]:
                    return (
                        f"{Global.get_info_link(match.group('object'))}"
                        f"{match.group('after')}"
                    )
                if match.group("kind").lower() in ["user", "team", "info", "wiki"]:
                    return "../home/placeholder.html"
                if match.group("kind").lower() in ["store", "boutique", "tienda"]:
                    return "../home/placeholder.html"
                if match.group("kind").lower() in [
                    "guide",
                    "anleitung",
                    "guía",
                    "guida",
                    "tutoriel",
                ]:
                    return (
                        f"{Global.get_guide_link(match.group('object'))}"
                        f"{match.group('after')}"
                    )
                raise Exception(
                    f"Unsupported kind '{match.group('kind')}'"
                    " in _process_href_regex"
                )
            raise Exception("Unsupported match in _process_href_regex")
        if found_none:
            return href

    @staticmethod
    def _process_gbl_regex(match):
        if match.group("image_url"):
            return (
                f"<img{match.group('image_before')}"
                f"src=\"{Global.get_image_path(match.group('image_url'))}\""
            )
        if match.group("href_url"):
            return f"href=\"{Global._process_href_regex(match.group('href_url'))}\""
        raise Exception("Unsupported match in cleanup_rendered_content")

    @staticmethod
    def cleanup_rendered_content(content):
        return re.sub(Global.gbl_regex, Global._process_gbl_regex, content)

    @staticmethod
    def convert_title_to_filename(title):
        return re.sub(r"\s", "_", title)


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

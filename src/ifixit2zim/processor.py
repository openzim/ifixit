import datetime
import re
import threading
import urllib.parse

import requests
from zimscraperlib.zim.creator import Creator

from ifixit2zim.constants import (
    DEFAULT_DEVICE_IMAGE_URL,
    DEFAULT_GUIDE_IMAGE_URL,
    DEFAULT_USER_IMAGE_URLS,
    DEFAULT_WIKI_IMAGE_URL,
    NOT_YET_AVAILABLE,
    UNAVAILABLE_OFFLINE,
)
from ifixit2zim.exceptions import ImageUrlNotFoundError
from ifixit2zim.imager import Imager
from ifixit2zim.scraper import Configuration
from ifixit2zim.shared import logger, setlocale


class Processor:
    def __init__(
        self,
        lock: threading.Lock,
        configuration: Configuration,
        creator: Creator,
        imager: Imager,
    ) -> None:
        self.null_categories = set()
        self.ifixit_external_content = set()
        self.final_hrefs = {}
        self.lock = lock
        self.configuration = configuration
        self.creator = creator
        self.imager = imager

    @property
    def get_guide_link_from_props(self):
        return self._get_guide_link_from_props

    @get_guide_link_from_props.setter
    def get_guide_link_from_props(self, get_guide_link_from_props):
        self._get_guide_link_from_props = get_guide_link_from_props

    @property
    def get_category_link_from_props(self):
        return self._get_category_link_from_props

    @get_category_link_from_props.setter
    def get_category_link_from_props(self, get_category_link_from_props):
        self._get_category_link_from_props = get_category_link_from_props

    @property
    def get_info_link_from_props(self):
        return self._get_info_link_from_props

    @get_info_link_from_props.setter
    def get_info_link_from_props(self, get_info_link_from_props):
        self._get_info_link_from_props = get_info_link_from_props

    @property
    def get_user_link_from_props(self):
        return self._get_user_link_from_props

    @get_user_link_from_props.setter
    def get_user_link_from_props(self, get_user_link_from_props):
        self._get_user_link_from_props = get_user_link_from_props

    # no-qa flag is mandatory because this is used in a Jinja filter and arg names are
    # never passed by Jinja
    def guides_in_progress(self, guides, in_progress=True):  # noqa: FBT002
        if in_progress:
            return [guide for guide in guides if "GUIDE_IN_PROGRESS" in guide["flags"]]
        return [guide for guide in guides if "GUIDE_IN_PROGRESS" not in guide["flags"]]

    def category_count_parts(self, category):
        if "parts" not in category:
            return 0
        if "total" not in category["parts"]:
            return 0
        return category["parts"]["total"]

    def category_count_tools(self, category):
        if "tools" not in category:
            return 0
        return len(category["tools"])

    def get_image_path(self, image_url):
        return self.imager.defer(url=image_url)

    def _get_image_url_search(
        self, obj, *, for_guide: bool, for_device: bool, for_wiki: bool, for_user: bool
    ) -> str:
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
        raise ImageUrlNotFoundError(f"Unable to find image URL in object {obj}")

    def get_image_url(
        self, obj, *, for_guide=False, for_device=False, for_wiki=False, for_user=False
    ) -> str:
        if obj.get("image"):
            return self._get_image_url_search(
                obj["image"],
                for_guide=for_guide,
                for_device=for_device,
                for_wiki=for_wiki,
                for_user=for_user,
            )
        return self._get_image_url_search(
            obj,
            for_guide=for_guide,
            for_device=for_device,
            for_wiki=for_wiki,
            for_user=for_user,
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

    def _process_external_url(self, url, rel_prefix):
        if "ifixit" in url:
            self.ifixit_external_content.add(url)
        return f"{rel_prefix}home/external_content?url={urllib.parse.quote(url)}"

    def _process_unrecognized_href(self, url, rel_prefix):
        return self._process_external_url(url, rel_prefix)

    def _process_href_regex_dynamics(self, href, rel_prefix):
        if "Guide/login/register" in href or "Guide/new" in href:
            return (
                f"{rel_prefix}home/unavailable_offline"
                f"?url={urllib.parse.quote(href)}"
            )
        return None

    def _process_href_regex_nomatch(self, href, rel_prefix, match):
        if match:
            return None
        return self._process_unrecognized_href(href, rel_prefix)

    def _process_href_regex_anchor(self, match):
        if not match.group("anchor"):
            return None
        return f"{match.group('anchor')}"

    def _process_href_regex_guide(self, rel_prefix, match):
        if not match.group("guide"):
            return None
        link = self.get_guide_link_from_props(
            guideid=match.group("guideid"),
            guidetitle=urllib.parse.unquote_plus(match.group("guidetitle")),
        )
        return f"{rel_prefix}{link}{match.group('guideafter') or ''}"

    def _process_href_regex_device(self, rel_prefix, match):
        if not match.group("device"):
            return None
        link = self.get_category_link_from_props(
            category_title=urllib.parse.unquote_plus(match.group("devicetitle"))
        )
        return f"{rel_prefix}{link}{match.group('deviceafter') or ''}"

    def _process_href_regex_info(self, rel_prefix, match):
        if not match.group("info"):
            return None
        link = self.get_info_link_from_props(
            info_title=urllib.parse.unquote_plus(match.group("infotitle"))
        )
        return f"{rel_prefix}{link}{match.group('infoafter') or ''}"

    def _process_href_regex_user(self, rel_prefix, match):
        if not match.group("user"):
            return None
        link = self.get_user_link_from_props(
            userid=match.group("userid"),
            usertitle=urllib.parse.unquote_plus(match.group("usertitle")),
        )
        return f"{rel_prefix}{link}{match.group('userafter') or ''}"

    def _process_href_regex_kind(self, href, rel_prefix, match):
        if not match.group("kind"):
            return None
        if match.group("kind").lower() in NOT_YET_AVAILABLE:
            return f"{rel_prefix}home/not_yet_available?url={urllib.parse.quote(href)}"
        if match.group("kind").lower() in UNAVAILABLE_OFFLINE:
            return (
                f"{rel_prefix}home/unavailable_offline"
                f"?url={urllib.parse.quote(href)}"
            )
        raise Exception(
            f"Unsupported kind '{match.group('kind')}' in _process_href_regex"
        )

    def normalize_href(self, href):
        if href in self.final_hrefs:
            return self.final_hrefs[href]
        try:
            logger.debug(f"Normalizing href {href}")
            # final_href = requests.head(href).headers.get("Location")
            # if final_href is None:
            #     logger.debug(f"Failed to HEAD {href}, falling back to GET")
            final_href = requests.get(href, stream=True, timeout=10).url
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
        self.final_hrefs[href] = final_href
        logger.debug(f"Result is {final_href}")
        return final_href

    def _process_href_regex(self, href, rel_prefix):
        if href.startswith("/"):
            href = self.configuration.main_url.geturl() + href
        if href.startswith("http") and "ifixit.com/" in href:
            href = self.normalize_href(href)
            href = urllib.parse.quote(href)
        match = self.href_regex.search(href)
        res = (
            self._process_href_regex_dynamics(href=href, rel_prefix=rel_prefix)
            or self._process_href_regex_nomatch(
                href=href, rel_prefix=rel_prefix, match=match
            )
            or self._process_href_regex_anchor(match=match)
            or self._process_href_regex_guide(rel_prefix=rel_prefix, match=match)
            or self._process_href_regex_device(rel_prefix=rel_prefix, match=match)
            or self._process_href_regex_info(rel_prefix=rel_prefix, match=match)
            or self._process_href_regex_user(rel_prefix=rel_prefix, match=match)
            or self._process_href_regex_kind(
                href=href, rel_prefix=rel_prefix, match=match
            )
        )
        if res is None:
            raise Exception("Unsupported match in _process_href_regex")
        return res

    def _process_youtube(self, match, rel_prefix):
        return (
            f'<a href="'
            f"{self._process_external_url(match.group('youtubesrc'), rel_prefix)}"
            f'">'
            f"<div{self.cleanup_rendered_content(match.group('part1'), rel_prefix)}"
            "youtube-player"
            f"{self.cleanup_rendered_content(match.group('part2'), rel_prefix)}"
            f"{self.cleanup_rendered_content(match.group('part3'), rel_prefix)}"
            "</div></a>"
        )

    def _process_bgdimgurl(self, match, rel_prefix):
        return (
            f"background-image:url({match.group('quote1')}{rel_prefix}"
            f"{self.get_image_path(match.group('bgdimgurl'))}"
            f"{match.group('quote2')})"
        )

    def _process_video(self):
        return "<p>Video not scrapped</p>"

    def _process_iframe(self, match, rel_prefix):
        return (
            f'<a href="'
            f"{self._process_external_url(match.group('iframe_url'), rel_prefix)}"
            f'">External content</a>'
        )

    def _process_gbl_regex(self, match, rel_prefix):
        if match.group("image_url"):
            return (
                f"<img{match.group('image_before')}"
                f'src="{rel_prefix}'
                f"{self.get_image_path(match.group('image_url'))}"
                '"'
            )
        if match.group("href_url"):
            href = self._process_href_regex(match.group("href_url"), rel_prefix)
            return f'href="{href}"'
        if match.group("youtubesrc"):
            return self._process_youtube(match=match, rel_prefix=rel_prefix)
        if match.group("bgdimgurl"):
            return self._process_bgdimgurl(match=match, rel_prefix=rel_prefix)
        if match.group("videostuff"):
            return self._process_video()
        if match.group("iframe_url"):
            return self._process_iframe(match=match, rel_prefix=rel_prefix)
        raise Exception("Unsupported match in cleanup_rendered_content")

    def cleanup_rendered_content(self, content, rel_prefix="../"):
        if self.configuration.no_cleanup:
            return content
        return re.sub(
            self.gbl_regex,
            lambda match: self._process_gbl_regex(match=match, rel_prefix=rel_prefix),
            content,
        )

    def convert_title_to_filename(self, title):
        return re.sub(r"\s", "_", title)

    def add_html_item(self, path, title, content, *, is_front=True):
        with self.lock:
            logger.debug(f"Adding item in ZIM at path '{path}'")
            self.creator.add_item_for(
                path=path,
                title=title,
                content=content,
                mimetype="text/html",
                is_front=is_front,
            )

    def add_redirect(self, path, target_path):
        with self.lock:
            logger.debug(f"Adding redirect in ZIM from '{path}' to '{target_path}'")
            self.creator.add_redirect(
                path=path,
                target_path=target_path,
            )

    def get_item_comments_count(self, item):
        if "comments" not in item:
            return 0
        total = 0
        for comment in item["comments"]:
            total += 1
            if "replies" in comment:
                total += len(comment["replies"])
        return total

    def get_guide_total_comments_count(self, guide):
        total = self.get_item_comments_count(guide)
        for step in guide["steps"]:
            total += self.get_item_comments_count(step)
        return total

    def get_timestamp_day_rendered(self, timestamp):
        with setlocale("en_GB"):
            if timestamp:
                return datetime.datetime.strftime(
                    datetime.datetime.fromtimestamp(timestamp, tz=datetime.UTC),
                    "%x",
                )
            return ""

    def get_user_display_name(self, user):
        if user["username"] and len(user["username"]) > 0:
            return user["username"]
        if user["unique_username"] and len(user["unique_username"]) > 0:
            return f"@{user['unique_username']}"
        return "Anonymous"

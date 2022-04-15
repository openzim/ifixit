from datetime import datetime

from .constants import (
    DIFFICULTY_EASY,
    DIFFICULTY_HARD,
    DIFFICULTY_MODERATE,
    DIFFICULTY_VERY_EASY,
    DIFFICULTY_VERY_HARD,
    GUIDE_LABELS,
    UNKNOWN_LOCALE,
)
from .exceptions import UnexpectedDataKindException
from .scraper_generic import ScraperGeneric
from .shared import Global, logger
from .utils import get_api_content, setlocale


class ScraperGuide(ScraperGeneric):
    def __init__(self):
        super().__init__()

    def setup(self):
        self.guide_template = Global.env.get_template("guide.html")

    def get_items_name(self):
        return "guide"

    def _add_guide_to_scrape(self, guideid, locale, is_expected):
        self.add_item_to_scrape(
            guideid,
            {
                "guideid": guideid,
                "locale": locale,
            },
            is_expected,
        )

    def _get_guide_path_from_key(self, guide_key):
        return f"guides/guide_{guide_key}.html"

    def get_guide_link(self, guide):
        guideid = None
        locale = Global.conf.lang_code
        if isinstance(guide, str):
            guideid = guide
        else:
            if "guideid" not in guide or not guide["guideid"]:
                raise UnexpectedDataKindException(
                    f"Impossible to extract guide id from {guide}"
                )
            if "locale" not in guide or not guide["locale"]:
                raise UnexpectedDataKindException(
                    f"Impossible to extract guide locale from {guide}"
                )
            guideid = guide["guideid"]
            locale = guide["locale"]
            # override unknown locale if needed
            if (
                guideid in self.expected_items_keys
                and self.expected_items_keys[guideid]["locale"] == UNKNOWN_LOCALE
            ):
                self.expected_items_keys[guideid]["locale"] = locale
        if not Global.conf.guides and not Global.conf.no_guide:
            self._add_guide_to_scrape(guideid, locale, False)
        return f"../{self._get_guide_path_from_key(guideid)}"

    def build_expected_items(self):
        if Global.conf.no_guide:
            logger.info("No guide required")
            return
        if Global.conf.guides:
            logger.info("Adding required guides as expected")
            for guide in Global.conf.guides:
                self._add_guide_to_scrape(guide, UNKNOWN_LOCALE, True)
            return
        logger.info("Downloading list of guides")
        limit = 200
        offset = 0
        while True:
            guides = get_api_content("/guides", limit=limit, offset=offset)
            if len(guides) == 0:
                break
            for guide in guides:
                guideid = guide["guideid"]
                # Unfortunately for now iFixit API always returns "en" as language on
                # this endpoint, so we consider it as unknown
                self._add_guide_to_scrape(guideid, UNKNOWN_LOCALE, True)
            offset += limit
        logger.info("{} guides found".format(len(self.expected_items_keys)))

    def get_one_item_content(self, item_key, item_data):
        guideid = item_key
        guide = item_data
        locale = guide["locale"]
        if locale == UNKNOWN_LOCALE:
            locale = Global.conf.lang_code  # fallback value
        if locale == "ja":
            locale = "jp"  # Unusual iFixit convention

        guide_content = get_api_content(f"/guides/{guideid}", langid=locale)
        if guide_content is None and locale != "en":
            # guide is most probably available in English anyway
            guide_content = get_api_content(f"/guides/{guideid}", langid="en")

        return guide_content

    def process_one_item(self, item_key, item_data, item_content):
        guide_content = item_content

        if guide_content["type"] != "teardown":
            if guide_content["difficulty"] in DIFFICULTY_VERY_EASY:
                guide_content["difficulty_class"] = "difficulty-1"
            elif guide_content["difficulty"] in DIFFICULTY_EASY:
                guide_content["difficulty_class"] = "difficulty-2"
            elif guide_content["difficulty"] in DIFFICULTY_MODERATE:
                guide_content["difficulty_class"] = "difficulty-3"
            elif guide_content["difficulty"] in DIFFICULTY_HARD:
                guide_content["difficulty_class"] = "difficulty-4"
            elif guide_content["difficulty"] in DIFFICULTY_VERY_HARD:
                guide_content["difficulty_class"] = "difficulty-5"
            else:
                raise UnexpectedDataKindException(
                    "Unknown guide difficulty: '{}' in guide {}".format(
                        guide_content["difficulty"],
                        guide_content["guideid"],
                    )
                )
        with setlocale("en_GB"):
            if guide_content["author"]["join_date"]:
                guide_content["author"]["join_date_rendered"] = datetime.strftime(
                    datetime.fromtimestamp(guide_content["author"]["join_date"]),
                    "%x",
                )
            # TODO: format published date as June 10, 2014 instead of 11/06/2014
            if guide_content["published_date"]:
                guide_content["published_date_rendered"] = datetime.strftime(
                    datetime.fromtimestamp(guide_content["published_date"]),
                    "%x",
                )

        for step in guide_content["steps"]:
            if not step["media"]:
                raise UnexpectedDataKindException(
                    "Missing media attribute in step {} of guide {}".format(
                        step["stepid"], guide_content["guideid"]
                    )
                )
            if step["media"]["type"] not in [
                "image",
                "video",
                "embed",
            ]:
                raise UnexpectedDataKindException(
                    "Unrecognized media type in step {} of guide {}".format(
                        step["stepid"], guide_content["guideid"]
                    )
                )
            if step["media"]["type"] == "video":
                if "data" not in step["media"] or not step["media"]["data"]:
                    raise UnexpectedDataKindException(
                        "Missing 'data' in step {} of guide {}".format(
                            step["stepid"], guide_content["guideid"]
                        )
                    )
                if (
                    "image" not in step["media"]["data"]
                    or not step["media"]["data"]["image"]
                ):
                    raise UnexpectedDataKindException(
                        "Missing outer 'image' in step {} of guide {}".format(
                            step["stepid"], guide_content["guideid"]
                        )
                    )
                if (
                    "image" not in step["media"]["data"]["image"]
                    or not step["media"]["data"]["image"]["image"]
                ):
                    raise UnexpectedDataKindException(
                        "Missing inner 'image' in step {} of guide {}".format(
                            step["stepid"], guide_content["guideid"]
                        )
                    )
            if step["media"]["type"] == "embed":
                if "data" not in step["media"] or not step["media"]["data"]:
                    raise UnexpectedDataKindException(
                        "Missing 'data' in step {} of guide {}".format(
                            step["stepid"], guide_content["guideid"]
                        )
                    )
                if (
                    "html" not in step["media"]["data"]
                    or not step["media"]["data"]["html"]
                ):
                    raise UnexpectedDataKindException(
                        "Missing 'html' in step {} of guide {}".format(
                            step["stepid"], guide_content["guideid"]
                        )
                    )
            for line in step["lines"]:
                if not line["bullet"] in [
                    "black",
                    "red",
                    "orange",
                    "yellow",
                    "green",
                    "blue",
                    "light_blue",
                    "violet",
                    "icon_note",
                    "icon_caution",
                    "icon_caution",
                    "icon_reminder",
                ]:
                    raise UnexpectedDataKindException(
                        "Unrecognized bullet '{}' in step {} of guide {}".format(
                            line["bullet"],
                            step["stepid"],
                            guide_content["guideid"],
                        )
                    )
        guide_rendered = self.guide_template.render(
            guide=guide_content,
            label=GUIDE_LABELS[Global.conf.lang_code],
            metadata=Global.metadata,
        )
        with Global.lock:
            Global.creator.add_item_for(
                path=self._get_guide_path_from_key(item_key),
                title=guide_content["title"],
                content=guide_rendered,
                mimetype="text/html",
                is_front=True,
            )

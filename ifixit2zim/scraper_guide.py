from datetime import datetime

from .constants import (
    DIFFICULTY_EASY,
    DIFFICULTY_HARD,
    DIFFICULTY_MODERATE,
    DIFFICULTY_VERY_EASY,
    DIFFICULTY_VERY_HARD,
    GUIDE_LABELS,
)
from .exceptions import UnexpectedDataKindException
from .scraper_generic import ScraperGeneric
from .shared import Global
from .utils import get_api_content, setlocale


class ScraperGuide(ScraperGeneric):
    def __init__(self):
        super().__init__()

    def setup(self):
        self.guide_template = Global.env.get_template("guide.html")

    def get_items_name(self):
        return "guide"

    def _add_guide_to_scrape(self, guideid, locale, force=False):
        if force or not Global.conf.categories:
            self.add_item_to_scrape(
                guideid,
                {
                    "guideid": guideid,
                    "locale": locale,
                },
            )
        return guideid

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
        guide_key = self._add_guide_to_scrape(guideid, locale)
        return f"../{self._get_guide_path_from_key(guide_key)}"

    def build_expected_items(self):
        # expected guides are added by the category processing
        pass

    def get_one_item_content(self, item_key, item_data):
        guideid = item_key
        guide = item_data

        guide_content = get_api_content(f"/guides/{guideid}", langid=guide["locale"])

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

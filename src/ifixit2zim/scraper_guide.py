import urllib.parse

from ifixit2zim.constants import (
    DIFFICULTY_EASY,
    DIFFICULTY_HARD,
    DIFFICULTY_MODERATE,
    DIFFICULTY_VERY_EASY,
    DIFFICULTY_VERY_HARD,
    GUIDE_LABELS,
    UNKNOWN_LOCALE,
    UNKNOWN_TITLE,
)
from ifixit2zim.context import Context
from ifixit2zim.exceptions import UnexpectedDataKindExceptionError
from ifixit2zim.scraper_generic import ScraperGeneric
from ifixit2zim.shared import logger


class ScraperGuide(ScraperGeneric):
    def __init__(self, context: Context):
        super().__init__(context)

    def setup(self):
        self.guide_template = self.env.get_template("guide.html")

    def get_items_name(self):
        return "guide"

    def _add_guide_to_scrape(self, guideid, guidetitle, locale, is_expected):
        self.add_item_to_scrape(
            guideid,
            {
                "guideid": guideid,
                "guidetitle": guidetitle,
                "locale": locale,
            },
            is_expected,
        )

    def _build_guide_path(self, guideid, guidetitle):  # noqa ARG002
        href = self.configuration.main_url.geturl() + f"/Guide/-/{guideid}"
        final_href = self.processor.normalize_href(href)
        return final_href[1:]

    def get_guide_link_from_obj(self, guide):
        if "guideid" not in guide or not guide["guideid"]:
            raise UnexpectedDataKindExceptionError(
                f"Impossible to extract guide id from {guide}"
            )
        if "locale" not in guide or not guide["locale"]:
            raise UnexpectedDataKindExceptionError(
                f"Impossible to extract guide locale from {guide}"
            )
        if "title" not in guide or not guide["title"]:
            raise UnexpectedDataKindExceptionError(
                f"Impossible to extract guide title from {guide}"
            )
        guideid = guide["guideid"]
        locale = guide["locale"]
        title = guide["title"]
        # override unknown locale if needed
        if (
            guideid in self.expected_items_keys
            and self.expected_items_keys[guideid]["locale"] == UNKNOWN_LOCALE
        ):
            self.expected_items_keys[guideid]["locale"] = locale
        # override unknown title if needed
        if (
            guideid in self.expected_items_keys
            and self.expected_items_keys[guideid]["guidetitle"] == UNKNOWN_TITLE
        ):
            self.expected_items_keys[guideid]["guidetitle"] = title
        return self.get_guide_link_from_props(
            guideid=guideid, guidetitle=title, guidelocale=locale
        )

    def get_guide_link_from_props(
        self, guideid, guidetitle, guidelocale=UNKNOWN_LOCALE
    ):
        guide_path = urllib.parse.quote(
            self._build_guide_path(guideid=guideid, guidetitle=guidetitle)
        )
        if self.configuration.no_guide:
            return f"home/not_scrapped?url={guide_path}"
        if self.configuration.guides and str(guideid) not in self.configuration.guides:
            return f"home/not_scrapped?url={guide_path}"
        self._add_guide_to_scrape(guideid, guidetitle, guidelocale, False)
        return guide_path

    def build_expected_items(self):
        if self.configuration.no_guide:
            logger.info("No guide required")
            return
        if self.configuration.guides:
            logger.info("Adding required guides as expected")
            for guide in self.configuration.guides:
                self._add_guide_to_scrape(guide, UNKNOWN_TITLE, UNKNOWN_LOCALE, True)
            return
        logger.info("Downloading list of guides")
        limit = 200
        offset = 0
        while True:
            guides = self.utils.get_api_content("/guides", limit=limit, offset=offset)
            if not guides or len(guides) == 0:
                break
            for guide in guides:
                # we ignore archived guides since they are not accessible anywayß
                if "GUIDE_ARCHIVED" in guide["flags"]:
                    continue
                if guide["revisionid"] == 0:
                    logger.warning("Found one guide with revisionid=0")
                guideid = guide["guideid"]
                # Unfortunately for now iFixit API always returns "en" as language
                # on this endpoint, so we consider it as unknown for now
                self._add_guide_to_scrape(guideid, UNKNOWN_TITLE, UNKNOWN_LOCALE, True)
            offset += limit
            if self.configuration.scrape_only_first_items:
                logger.warning(
                    "Aborting the retrieval of all guides since only first items"
                    " will be scraped anyway"
                )
                break
        logger.info(f"{len(self.expected_items_keys)} guides found")

    def get_one_item_content(self, item_key, item_data):
        guideid = item_key
        guide = item_data
        locale = guide["locale"]
        if locale == UNKNOWN_LOCALE:
            locale = self.configuration.lang_code  # fallback value
        if locale == "ja":
            locale = "jp"  # Unusual iFixit convention

        guide_content = self.utils.get_api_content(f"/guides/{guideid}", langid=locale)
        if guide_content is None and locale != "en":
            # guide is most probably available in English anyway
            guide_content = self.utils.get_api_content(
                f"/guides/{guideid}", langid="en"
            )

        return guide_content

    def add_item_redirect(self, item_key, item_data, redirect_kind):
        guideid = item_key
        guide = item_data
        guidetitle = guide["guidetitle"]
        if guidetitle == UNKNOWN_TITLE:
            logger.warning(f"Cannot add redirect for guide {guideid} in error")
            return
        path = self._build_guide_path(guideid, guidetitle)
        self.processor.add_redirect(
            path=path,
            target_path=f"home/{redirect_kind}?{urllib.parse.urlencode({'url':path})}",
        )

    def process_one_item(self, item_key, item_data, item_content):  # noqa ARG002
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
                raise UnexpectedDataKindExceptionError(
                    "Unknown guide difficulty: '{}' in guide {}".format(
                        guide_content["difficulty"],
                        guide_content["guideid"],
                    )
                )

        for step in guide_content["steps"]:
            if not step["media"]:
                raise UnexpectedDataKindExceptionError(
                    "Missing media attribute in step {} of guide {}".format(
                        step["stepid"], guide_content["guideid"]
                    )
                )
            if step["media"]["type"] not in [
                "image",
                "video",
                "embed",
            ]:
                raise UnexpectedDataKindExceptionError(
                    "Unrecognized media type in step {} of guide {}".format(
                        step["stepid"], guide_content["guideid"]
                    )
                )
            if step["media"]["type"] == "video":
                if "data" not in step["media"] or not step["media"]["data"]:
                    raise UnexpectedDataKindExceptionError(
                        "Missing 'data' in step {} of guide {}".format(
                            step["stepid"], guide_content["guideid"]
                        )
                    )
                if (
                    "image" not in step["media"]["data"]
                    or not step["media"]["data"]["image"]
                ):
                    raise UnexpectedDataKindExceptionError(
                        "Missing outer 'image' in step {} of guide {}".format(
                            step["stepid"], guide_content["guideid"]
                        )
                    )
                if (
                    "image" not in step["media"]["data"]["image"]
                    or not step["media"]["data"]["image"]["image"]
                ):
                    raise UnexpectedDataKindExceptionError(
                        "Missing inner 'image' in step {} of guide {}".format(
                            step["stepid"], guide_content["guideid"]
                        )
                    )
            if step["media"]["type"] == "embed":
                if "data" not in step["media"] or not step["media"]["data"]:
                    raise UnexpectedDataKindExceptionError(
                        "Missing 'data' in step {} of guide {}".format(
                            step["stepid"], guide_content["guideid"]
                        )
                    )
                if (
                    "html" not in step["media"]["data"]
                    or not step["media"]["data"]["html"]
                ):
                    raise UnexpectedDataKindExceptionError(
                        "Missing 'html' in step {} of guide {}".format(
                            step["stepid"], guide_content["guideid"]
                        )
                    )
            for line in step["lines"]:
                if line["bullet"] not in [
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
                    raise UnexpectedDataKindExceptionError(
                        "Unrecognized bullet '{}' in step {} of guide {}".format(
                            line["bullet"],
                            step["stepid"],
                            guide_content["guideid"],
                        )
                    )
        guide_rendered = self.guide_template.render(
            guide=guide_content,
            label=GUIDE_LABELS[self.configuration.lang_code],
            metadata=self.metadata,
        )

        self.processor.add_html_item(
            path=self._build_guide_path(
                guideid=guide_content["guideid"], guidetitle=guide_content["title"]
            ),
            title=guide_content["title"],
            content=guide_rendered,
        )

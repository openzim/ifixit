import urllib.parse
from collections.abc import Callable
from typing import Any, cast

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
from ifixit2zim.utils import build_dynamic_page_link


class ScraperGuide(ScraperGeneric):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        # Injected by IFixit2Zim; optional so the scraper stays standalone.
        self.item_reference_recorder: (
            Callable[[str, str | None, str, str], None] | None
        ) = None

    def setup(self) -> None:
        self.guide_template = self.env.get_template("guide.html")

    def get_items_name(self) -> str:
        return "guide"

    def _add_guide_to_scrape(
        self,
        guideid: str,
        guidetitle: str,
        locale: str,
        is_expected: bool,  # noqa: FBT001
    ) -> None:
        self.add_item_to_scrape(
            guideid,
            {
                "guideid": guideid,
                "guidetitle": guidetitle,
                "locale": locale,
            },
            is_expected,
        )

    def _build_guide_path(self, guideid: str, guidetitle: str) -> str:  # noqa: ARG002
        href = self.configuration.main_url.geturl() + f"/Guide/-/{guideid}"
        final_href = self.processor.normalize_href(href)
        return final_href[1:]

    def get_guide_link_from_obj(self, guide: dict[str, Any]) -> str:
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
        self, guideid: str, guidetitle: str, guidelocale: str = UNKNOWN_LOCALE
    ) -> str:
        raw_guide_path = self._build_guide_path(guideid=guideid, guidetitle=guidetitle)
        guide_path = urllib.parse.quote(raw_guide_path)
        if self.configuration.no_guide:
            return build_dynamic_page_link("not_scrapped", raw_guide_path)
        if self.configuration.guides and str(guideid) not in self.configuration.guides:
            return build_dynamic_page_link("not_scrapped", raw_guide_path)
        self.record_item_link(guideid, raw_guide_path)
        self._add_guide_to_scrape(guideid, guidetitle, guidelocale, False)
        return guide_path

    def build_expected_items(self) -> None:
        if self.configuration.no_guide:
            logger.info("No guide required")
            return
        if self.configuration.guides:
            logger.info("Adding required guides as expected")
            for guide in self.configuration.guides:
                self._add_guide_to_scrape(guide, UNKNOWN_TITLE, UNKNOWN_LOCALE, True)
            return
        logger.info("Downloading list of guides")
        max_items = self.configuration.max_items_per_type
        limit = 200
        offset = 0
        while True:
            if max_items > 0:
                remaining = max_items - len(self.expected_items_keys)
                if remaining <= 0:
                    logger.warning(
                        "Aborting the retrieval of all guides since at most "
                        f"{max_items} items will be scraped"
                    )
                    break
                limit = min(limit, remaining)
            guides = self.client.get_api_content("/guides", limit=limit, offset=offset)
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
        logger.info(f"{len(self.expected_items_keys)} guides found")

    def get_one_item_content(self, item_key: str, item_data: dict[str, Any]) -> Any:
        guideid = item_key
        guide = item_data
        locale = guide["locale"]
        if locale == UNKNOWN_LOCALE:
            locale = self.configuration.lang_code  # fallback value
        if locale == "ja":
            locale = "jp"  # Unusual iFixit convention

        guide_content = self.client.get_api_content(f"/guides/{guideid}", langid=locale)
        if guide_content is None and locale != "en":
            # guide is most probably available in English anyway
            guide_content = self.client.get_api_content(
                f"/guides/{guideid}", langid="en"
            )

        return guide_content

    def add_item_redirect(
        self, item_key: str, item_data: dict[str, Any], redirect_kind: str
    ) -> None:
        guideid = item_key
        guide = item_data
        guidetitle = guide["guidetitle"]
        if guidetitle == UNKNOWN_TITLE:
            logger.warning(f"Cannot add redirect for guide {guideid} in error")
            return
        path = self._build_guide_path(guideid, guidetitle)
        self.processor.add_redirect(
            path=path,
            target_path=f"home/{redirect_kind}",
        )

    def _record_item_references(
        self, guide_content: dict[str, Any], guide_path: str
    ) -> None:
        recorder = self.item_reference_recorder
        if recorder is None:
            return
        guide_title = str(
            guide_content.get("title") or guide_content.get("subject") or ""
        )
        if not guide_title or not guide_path:
            return
        guide_url = urllib.parse.quote(guide_path)
        for field_name in ("parts", "tools"):
            items = cast(list[dict[str, Any]], guide_content.get(field_name) or [])
            for item in items:
                item_url = item.get("wiki_url")
                if not isinstance(item_url, str) or not item_url:
                    continue
                product_url = item.get("url")
                if not isinstance(product_url, str) or not product_url:
                    product_url = None
                recorder(item_url, product_url, guide_title, guide_url)

    def process_one_item(
        self,
        item_key: str,  # noqa: ARG002
        item_data: dict[str, Any],  # noqa: ARG002
        item_content: Any,
    ) -> None:
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

        guide_path = self._build_guide_path(
            guideid=guide_content["guideid"], guidetitle=guide_content["title"]
        )
        self.processor.add_html_item(
            path=guide_path,
            title=guide_content["title"],
            content=guide_rendered,
        )
        self._record_item_references(guide_content, guide_path)

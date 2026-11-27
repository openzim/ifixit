import urllib.parse
from typing import Any

from ifixit2zim.constants import UNAVAILABLE_OFFLINE_INFOS
from ifixit2zim.context import Context
from ifixit2zim.exceptions import UnexpectedDataKindExceptionError
from ifixit2zim.scraper_generic import ScraperGeneric
from ifixit2zim.shared import logger
from ifixit2zim.utils import build_dynamic_page_link


class ScraperInfo(ScraperGeneric):
    def __init__(self, context: Context) -> None:
        super().__init__(context)

    def setup(self) -> None:
        self.info_template = self.env.get_template("info.html")

    def get_items_name(self) -> str:
        return "info"

    def _add_info_to_scrape(
        self,
        info_key: str,
        info_title: str,
        is_expected: bool,  # noqa: FBT001
    ) -> None:
        self.add_item_to_scrape(
            info_key,
            {
                "info_title": info_title,
            },
            is_expected,
        )

    def _get_info_key_from_title(self, info_title: str) -> str:
        return self.processor.convert_title_to_filename(info_title.lower())

    def _build_info_path(self, info_title: str) -> str:
        href = (
            self.configuration.main_url.geturl()
            + f"/Info/{info_title.replace('/', ' ')}"
        )
        final_href = self.processor.normalize_href(href)
        return final_href[1:]

    def get_info_link_from_obj(self, info: dict[str, Any]) -> str:
        if "title" not in info or not info["title"]:
            raise UnexpectedDataKindExceptionError(
                f"Impossible to extract info title from {info}"
            )
        info_title = info["title"]
        return self.get_info_link_from_props(info_title=info_title)

    def get_info_link_from_props(self, info_title: str) -> str:
        raw_info_path = self._build_info_path(info_title)
        info_path = urllib.parse.quote(raw_info_path)
        if self.configuration.no_info:
            return build_dynamic_page_link("not_scrapped", raw_info_path)
        if info_title in UNAVAILABLE_OFFLINE_INFOS:
            return build_dynamic_page_link("unavailable_offline", raw_info_path)
        info_key = self._get_info_key_from_title(info_title)
        if self.configuration.infos:
            is_not_included = True
            for other_info in self.configuration.infos:
                other_info_key = self._get_info_key_from_title(other_info)
                if other_info_key == info_key:
                    is_not_included = False
            if is_not_included:
                return build_dynamic_page_link("not_scrapped", raw_info_path)
        self._add_info_to_scrape(info_key, info_title, False)
        return info_path

    def build_expected_items(self) -> None:
        if self.configuration.no_info:
            logger.info("No info required")
            return
        if self.configuration.infos:
            logger.info("Adding required infos as expected")
            for info_title in self.configuration.infos:
                info_key = self._get_info_key_from_title(info_title)
                self._add_info_to_scrape(info_key, info_title, True)
            return
        logger.info("Downloading list of info")
        max_items = self.configuration.max_items_per_type
        limit = 200
        offset = 0
        while True:
            if max_items > 0:
                remaining = max_items - len(self.expected_items_keys)
                if remaining <= 0:
                    logger.warning(
                        "Aborting the retrieval of all infos since at most "
                        f"{max_items} items will be scraped"
                    )
                    break
                limit = min(limit, remaining)
            info_wikis = self.client.get_api_content(
                "/wikis/INFO", limit=limit, offset=offset
            )
            if not info_wikis or len(info_wikis) == 0:
                break
            for info_wiki in info_wikis:
                info_title = info_wiki["title"]
                info_key = self._get_info_key_from_title(info_title)
                self._add_info_to_scrape(info_key, info_title, True)
            offset += limit
        logger.info(f"{len(self.expected_items_keys)} info found")

    def get_one_item_content(
        self,
        item_key: str,
        item_data: dict[str, Any],  # noqa: ARG002
    ) -> Any:
        info_wiki_title = item_key
        info_wiki_content = self.client.get_api_content(
            f"/wikis/INFO/{info_wiki_title}"
        )
        return info_wiki_content

    def add_item_redirect(
        self,
        item_key: str,  # noqa: ARG002
        item_data: dict[str, Any],
        redirect_kind: str,
    ) -> None:
        path = self._build_info_path(item_data["info_title"])
        self.processor.add_redirect(
            path=path,
            target_path=f"home/{redirect_kind}",
        )

    def process_one_item(
        self,
        item_key: str,  # noqa: ARG002
        item_data: dict[str, Any],  # noqa: ARG002
        item_content: Any,
    ) -> None:
        info_wiki_content = item_content

        info_wiki_rendered = self.info_template.render(
            info_wiki=info_wiki_content,
            # label=INFO_WIKI_LABELS[self.conf.lang_code],
            metadata=self.metadata,
            lang=self.configuration.lang_code,
        )

        self.processor.add_html_item(
            path=self._build_info_path(info_wiki_content["title"]),
            title=info_wiki_content["display_title"],
            content=info_wiki_rendered,
        )

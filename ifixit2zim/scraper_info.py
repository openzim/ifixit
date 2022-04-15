from .exceptions import UnexpectedDataKindException
from .scraper_generic import ScraperGeneric
from .shared import Global, logger
from .utils import get_api_content


class ScraperInfo(ScraperGeneric):
    def __init__(self):
        super().__init__()

    def setup(self):
        self.info_template = Global.env.get_template("info.html")

    def get_items_name(self):
        return "info"

    def _add_info_to_scrape(self, info_key, info_title, is_expected):
        self.add_item_to_scrape(
            info_key,
            {
                "info_title": info_title,
            },
            is_expected,
        )

    def _get_info_key_from_title(self, info_title):
        return Global.convert_title_to_filename(info_title.lower())

    def _get_info_path_from_key(self, info_key):
        return f"infos/info_{info_key}.html"

    def get_info_link(self, info):
        info_title = None
        if isinstance(info, str):
            info_title = info
        elif "title" in info and info["title"]:
            info_title = info["title"]
        else:
            raise UnexpectedDataKindException(
                f"Impossible to extract info title from {info}"
            )
        info_key = self._get_info_key_from_title(info_title)
        if not Global.conf.infos and not Global.conf.no_info:
            self._add_info_to_scrape(info_key, info_title, False)
        return f"../{self._get_info_path_from_key(info_key)}"

    def build_expected_items(self):
        if Global.conf.no_info:
            logger.info("No info required")
            return
        if Global.conf.infos:
            logger.info("Adding required infos as expected")
            for info_title in Global.conf.infos:
                info_key = self._get_info_key_from_title(info_title)
                self._add_info_to_scrape(info_key, info_title, True)
            return
        logger.info("Downloading list of info")
        limit = 200
        offset = 0
        while True:
            info_wikis = get_api_content("/wikis/INFO", limit=limit, offset=offset)
            if len(info_wikis) == 0:
                break
            for info_wiki in info_wikis:
                info_title = info_wiki["title"]
                info_key = self._get_info_key_from_title(info_title)
                self._add_info_to_scrape(info_key, info_title, True)
            offset += limit
        logger.info("{} info found".format(len(self.expected_items_keys)))

    def get_one_item_content(self, item_key, item_data):
        info_wiki_title = item_key
        info_wiki_content = get_api_content(f"/wikis/INFO/{info_wiki_title}")
        return info_wiki_content

    def process_one_item(self, item_key, item_data, item_content):
        info_wiki_content = item_content

        info_wiki_rendered = self.info_template.render(
            info_wiki=info_wiki_content,
            # label=INFO_WIKI_LABELS[self.conf.lang_code],
            metadata=Global.metadata,
            lang=Global.conf.lang_code,
        )
        with Global.lock:
            Global.creator.add_item_for(
                path=self._get_info_path_from_key(item_key),
                title=info_wiki_content["display_title"],
                content=info_wiki_rendered,
                mimetype="text/html",
                is_front=True,
            )

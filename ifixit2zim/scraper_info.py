from .scraper_generic import ScraperGeneric
from .shared import Global, logger
from .utils import get_api_content


class ScraperInfo(ScraperGeneric):
    def __init__(self, add_item_methods):
        super().__init__(add_item_methods=add_item_methods)

    def setup(self):
        self.info_template = Global.env.get_template("info.html")

    def get_items_name(self):
        return "info"

    def build_expected_items(self):
        logger.info("Downloading list of info")
        limit = 200
        offset = 0
        while True:
            info_wikis = get_api_content("/wikis/INFO", limit=limit, offset=offset)
            if len(info_wikis) == 0:
                break
            for info_wiki in info_wikis:
                self.add_item_methods["info"](info_wiki["title"], info_wiki)
            offset += limit
        logger.info("{} info found".format(len(self.expected_items)))

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
                path=f"infos/info_"
                f"{Global.convert_title_to_filename(info_wiki_content['title'])}.html",
                title=info_wiki_content["display_title"],
                content=info_wiki_rendered,
                mimetype="text/html",
                is_front=True,
            )

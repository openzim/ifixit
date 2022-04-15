from .constants import CATEGORY_LABELS
from .exceptions import UnexpectedDataKindException
from .scraper_generic import ScraperGeneric
from .shared import Global, logger
from .utils import get_api_content


class ScraperCategory(ScraperGeneric):
    def __init__(self):
        super().__init__()

    def setup(self):
        self.category_template = Global.env.get_template("category.html")

    def get_items_name(self):
        return "category"

    def _add_category_to_scrape(self, category_key, category_title, is_expected):
        self.add_item_to_scrape(
            category_key,
            {
                "category_title": category_title,
            },
            is_expected,
        )

    def _get_category_key_from_title(self, category_title):
        return Global.convert_title_to_filename(category_title.lower())

    def _get_category_path_from_key(self, category_key):
        return f"categories/category_{category_key}.html"

    def get_category_link(self, category):
        category_title = None
        if isinstance(category, str):
            category_title = category
        elif "title" in category and category["title"]:
            category_title = category["title"]
        else:
            raise UnexpectedDataKindException(
                f"Impossible to extract category title from {category}"
            )
        category_key = self._get_category_key_from_title(category_title)
        if not Global.conf.categories and not Global.conf.no_category:
            self._add_category_to_scrape(category_key, category_title, False)
        return f"../{self._get_category_path_from_key(category_key)}"

    def _process_categories(self, categories):
        for category in categories:
            category_key = self._get_category_key_from_title(category)
            self._add_category_to_scrape(category_key, category, True)
            self._process_categories(categories[category])

    def build_expected_items(self):
        if Global.conf.no_category:
            logger.info("No category required")
            return
        if Global.conf.categories:
            logger.info("Adding required categories as expected")
            for category in Global.conf.categories:
                category_key = self._get_category_key_from_title(category)
                self._add_category_to_scrape(category_key, category, True)
            return
        logger.info("Downloading list of categories")
        categories = get_api_content("/categories", includeStubs=True)
        self._process_categories(categories)
        logger.info("{} categories found".format(len(self.expected_items_keys)))

    def get_one_item_content(self, item_key, item_data):
        categoryid = item_key

        category_content = get_api_content(
            f"/wikis/CATEGORY/{categoryid}", langid=Global.conf.lang_code
        )

        return category_content

    def process_one_item(self, item_key, item_data, item_content):
        category_key = item_key
        category_content = item_content

        category_rendered = self.category_template.render(
            category=category_content,
            label=CATEGORY_LABELS[Global.conf.lang_code],
            metadata=Global.metadata,
            lang=Global.conf.lang_code,
        )

        with Global.lock:
            Global.creator.add_item_for(
                path=self._get_category_path_from_key(category_key),
                title=category_content["display_title"],
                content=category_rendered,
                mimetype="text/html",
                is_front=True,
            )

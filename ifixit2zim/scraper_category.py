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

    def _add_category_to_scrape(self, category_title, force=False):
        category_key = Global.convert_title_to_filename(category_title.lower())
        if force or not Global.conf.categories:
            self.add_item_to_scrape(
                category_key,
                {
                    "category_title": category_title,
                },
            )
        return category_key

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
        category_key = self._add_category_to_scrape(category_title)
        return f"../{self._get_category_path_from_key(category_key)}"

    def _process_categories(self, categories, force_include=False):
        include_parents = False
        for category in categories:
            include_me = False
            include_childs = False
            if (
                force_include
                or category in Global.conf.categories
                or Global.convert_title_to_filename(category) in Global.conf.categories
            ):
                include_me = True
                include_childs = (
                    Global.conf.categories_include_children or force_include
                )

            include_due_to_child = self._process_categories(
                categories[category], include_childs
            )

            if include_me or include_due_to_child:
                self._add_category_to_scrape(category, force=True)
                include_parents = True

        return include_parents

    def build_expected_items(self):
        logger.info("Building list of expected category")
        categories = get_api_content("/categories", includeStubs=True)
        self._process_categories(
            categories,
            (not Global.conf.categories) or (len(Global.conf.categories) == 0),
        )
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

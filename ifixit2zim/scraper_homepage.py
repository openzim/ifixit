# -*- coding: utf-8 -*-

import datetime
import json
import re

from .constants import DEFAULT_HOMEPAGE, HOME_LABELS
from .exceptions import CategoryHomePageContentError
from .scraper_generic import ScraperGeneric
from .shared import Global, logger
from .utils import get_soup


class ScraperHomepage(ScraperGeneric):
    def __init__(self):
        super().__init__()

    def setup(self):
        self.homepage_template = Global.env.get_template("home.html")
        self.not_here_template = Global.env.get_template("not_here.html")

    def get_items_name(self):
        return "home"

    def build_expected_items(self):
        self.add_item_to_scrape(1, 1, True)

    def get_one_item_content(self, item_key, item_data):
        soup, _ = get_soup("/Guide")
        return soup

    def add_item_redirect(self, item_key, item_data, redirect_kind):
        logger.warning("Not supposed to add a redirect for a home item")
        return

    def process_one_item(self, item_key, item_data, item_content):
        soup = item_content

        # extract and clean main content
        home_content = {
            "main_title": soup.find("title").string,
            "page_title": self._extract_page_title_from_page(soup),
            "primary_title": self._extract_primary_title_from_page(soup),
            "secondary_title": self._extract_secondary_title_from_page(soup),
            "callout": self._extract_callout_from_page(soup),
            "featured_categories": self._extract_featured_categories_from_page(soup),
            "sub_categories": self._extract_sub_categories_from_page(soup),
        }

        logger.debug(
            "Content extracted from /Guide:\n" f"{json.dumps(home_content,indent=2)}"
        )

        homepage = self.homepage_template.render(
            home_content=home_content,
            metadata=Global.metadata,
            label=HOME_LABELS[Global.conf.lang_code],
        )

        not_scrapped = self.not_here_template.render(
            metadata=Global.metadata,
            kind="not_scrapped",
        )

        external_content = self.not_here_template.render(
            metadata=Global.metadata,
            kind="external_content",
        )

        unavailable_offline = self.not_here_template.render(
            metadata=Global.metadata,
            kind="unavailable_offline",
        )

        not_yet_available = self.not_here_template.render(
            metadata=Global.metadata,
            kind="not_yet_available",
        )

        missing = self.not_here_template.render(
            metadata=Global.metadata,
            kind="missing",
        )

        error_content = self.not_here_template.render(
            metadata=Global.metadata,
            kind="error",
        )

        with Global.lock:
            Global.creator.add_item_for(
                path="home/home",
                title=Global.conf.title,
                content=homepage,
                mimetype="text/html",
                is_front=True,
            )

            Global.creator.add_redirect(path=DEFAULT_HOMEPAGE, target_path="home/home")

            Global.creator.add_item_for(
                path="home/not_scrapped",
                title=Global.conf.title,
                content=not_scrapped,
                mimetype="text/html",
                is_front=False,
            )

            Global.creator.add_item_for(
                path="home/external_content",
                title=Global.conf.title,
                content=external_content,
                mimetype="text/html",
                is_front=False,
            )

            Global.creator.add_item_for(
                path="home/unavailable_offline",
                title=Global.conf.title,
                content=unavailable_offline,
                mimetype="text/html",
                is_front=False,
            )

            Global.creator.add_item_for(
                path="home/not_yet_available",
                title=Global.conf.title,
                content=not_yet_available,
                mimetype="text/html",
                is_front=False,
            )

            Global.creator.add_item_for(
                path="home/missing",
                title=Global.conf.title,
                content=missing,
                mimetype="text/html",
                is_front=False,
            )

            Global.creator.add_item_for(
                path="home/error",
                title=Global.conf.title,
                content=error_content,
                mimetype="text/html",
                is_front=False,
            )

    _device_link_regex_without_href = re.compile(r"/Device/(?P<device>.*)")

    def _extract_page_title_from_page(self, soup):
        page_title_selector = "h1.page-title span"
        p = soup.select(page_title_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No text found in page with selector " f"'{page_title_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too many text found in page with selector " f"'{page_title_selector}'"
            )
        text = p[0].text
        if len(text) == 0:
            raise CategoryHomePageContentError(
                "Empty text found in page with selector " f"'{page_title_selector}'"
            )
        return text

    def _extract_primary_title_from_page(self, soup):
        primary_title_selector = "div.primary-divider p"
        p = soup.select(primary_title_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No text found in page with selector " f"'{primary_title_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too many text found in page with selector "
                f"'{primary_title_selector}'"
            )
        text = p[0].text
        if len(text) == 0:
            raise CategoryHomePageContentError(
                "Empty text found in page with selector " f"'{primary_title_selector}'"
            )
        return text

    def _extract_secondary_title_from_page(self, soup):
        secondary_title_selector = "div.secondary-divider p"
        p = soup.select(secondary_title_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No text found in page with selector " f"'{secondary_title_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too many text found in page with selector "
                f"'{secondary_title_selector}'"
            )
        text = p[0].text
        if len(text) == 0:
            raise CategoryHomePageContentError(
                "Empty text found in page with selector "
                f"'{secondary_title_selector}'"
            )
        return text

    def _extract_callout_from_page(self, soup):
        return {
            "content": self._extract_callout_content_from_page(soup),
            "img_url": self._extract_callout_img_src_from_page(soup),
        }

    def _extract_callout_content_from_page(self, soup):
        page_callout_selector = "div.page-callout-content"
        p = soup.select(page_callout_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No callout content found in page with selector "
                f"'{page_callout_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too many callout content found in page with selector "
                f"'{page_callout_selector}'"
            )
        return f"{p[0]}"

    def _extract_callout_img_src_from_page(self, soup):
        page_callout_selector = "div.page-callout-inner img"
        p = soup.select(page_callout_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No callout img found in page with selector "
                f"'{page_callout_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too many callout img found in page with selector "
                f"'{page_callout_selector}'"
            )
        src = p[0].attrs.get("src")
        if len(src) == 0:
            raise CategoryHomePageContentError(
                "Empty img src found in featured callout with selector "
                f"'{page_callout_selector}'"
            )
        return src

    def _extract_featured_categories_from_page(self, soup):
        featured_categories_css_selector = "a.featured-category-item"
        featured_categories = [
            {
                "text": self._extract_text_from_featured_category(fc),
                "img_url": self._extract_img_src_from_featured_category(fc),
                "name": self._extract_name_from_featured_category(fc),
                "title": self._extract_title_from_featured_category(fc),
            }
            for fc in soup.select(featured_categories_css_selector)
        ]

        if len(featured_categories) == 0:
            raise CategoryHomePageContentError(
                "No featured categories found with selector "
                f"'{featured_categories_css_selector}'"
            )
        return featured_categories

    def _extract_text_from_featured_category(self, fc):
        featured_category_text_css_selector = "p.featured-category-title"
        p = fc.select(featured_category_text_css_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No text found in featured category with selector "
                f"'{featured_category_text_css_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too many text found in featured category with selector "
                f"'{featured_category_text_css_selector}'"
            )
        text = p[0].text
        if len(text) == 0:
            raise CategoryHomePageContentError(
                "Empty text found in featured category with selector "
                f"'{featured_category_text_css_selector}'"
            )
        return text

    def _extract_img_src_from_featured_category(self, fc):
        featured_category_img_css_selector = "img"
        p = fc.select(featured_category_img_css_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No img found in featured category with selector "
                f"'{featured_category_img_css_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too many img found in featured category with selector "
                f"'{featured_category_img_css_selector}'"
            )
        src = p[0].attrs.get("src")
        if len(src) == 0:
            raise CategoryHomePageContentError(
                "Empty img src found in featured category with selector "
                f"'{featured_category_img_css_selector}'"
            )
        return src

    def _extract_name_from_featured_category(self, fc):
        href = fc.attrs.get("href")
        if len(href) == 0:
            raise CategoryHomePageContentError("Empty href found in featured category")
        name = self._device_link_regex_without_href.sub("\\g<device>", href)
        if name == href:
            raise CategoryHomePageContentError(
                f"Extracting name from featured category failed ; href:'{href}'"
            )
        return name

    def _extract_title_from_featured_category(self, fc):
        title = fc.attrs.get("title")
        if len(title) == 0:
            raise CategoryHomePageContentError("Empty title found in featured category")
        return title

    def _extract_sub_categories_from_page(self, soup):
        sub_categories_css_selector = "a.sub-category"
        sub_categories = [
            {
                "text": self._extract_text_from_sub_category(fc),
                "name": self._extract_name_from_sub_category(fc),
                "count": self._extract_count_from_sub_category(fc),
                "title": self._extract_title_from_sub_category(fc),
            }
            for fc in soup.select(sub_categories_css_selector)
        ]
        if len(sub_categories) == 0:
            raise CategoryHomePageContentError(
                "No sub-categories found with selector "
                f"'{sub_categories_css_selector}'"
            )
        return sub_categories

    def _extract_text_from_sub_category(self, sc):
        sub_category_text_css_selector = "span.sub-category-title-text"
        p = sc.select(sub_category_text_css_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No text found in sub-category with selector "
                f"'{sub_category_text_css_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too many text found in sub-category with selector "
                f"'{sub_category_text_css_selector}'"
            )
        text = p[0].text
        if len(text) == 0:
            raise CategoryHomePageContentError(
                "Empty text found in sub-category with selector "
                f"'{sub_category_text_css_selector}'"
            )
        return text

    def _extract_name_from_sub_category(self, sc):
        href = sc.attrs.get("href")
        if len(href) == 0:
            raise CategoryHomePageContentError("Empty href found in sub-category")
        name = self._device_link_regex_without_href.sub("\\g<device>", href)
        if name == href:
            raise CategoryHomePageContentError(
                f"Extracting name from sub-category failed ; href:'{href}'"
            )
        return name

    def _extract_count_from_sub_category(self, sc):
        sub_category_img_css_selector = "span.overflow-slide-in"
        p = sc.select(sub_category_img_css_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No span found in sub-category with selector "
                f"'{sub_category_img_css_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too many span found in sub-category with selector "
                f"'{sub_category_img_css_selector}'"
            )
        text = p[0].text
        if len(text) == 0:
            raise CategoryHomePageContentError(
                "Empty span text found in sub-category with selector "
                f"'{sub_category_img_css_selector}'"
            )
        try:
            return int(text)
        except ValueError:
            raise CategoryHomePageContentError(
                f"Failed to convert span text '{text}' to integer for " "sub-category"
            )

    def _extract_title_from_sub_category(self, sc):
        sub_category_img_css_selector = "span.overflow-slide-in"
        p = sc.select(sub_category_img_css_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No span found in sub-category with selector "
                f"'{sub_category_img_css_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too many span found in sub-category with selector "
                f"'{sub_category_img_css_selector}'"
            )
        title = p[0].attrs.get("title")
        if len(title) == 0:
            raise CategoryHomePageContentError(
                "Empty span title found in sub-category with selector "
                f"'{sub_category_img_css_selector}'"
            )
        return title

    def _extract_stats_from_page(self, soup):
        results = soup.findAll("div", {"data-name": "KPIDisplay"})
        if len(results) == 0:
            raise CategoryHomePageContentError("No KPIs found")
        if len(results) > 1:
            raise CategoryHomePageContentError("Too many KPIs found")
        kpi = results[0].get("data-props")
        if kpi is None:
            raise CategoryHomePageContentError("KPIs not found in data-props")

        try:
            kpi_d = json.loads(kpi)
        except json.decoder.JSONDecodeError as e:
            raise CategoryHomePageContentError(
                "Failed to decode stats from '{}' to integer for stat {}".format(kpi, e)
            )

        if "stats" not in kpi_d:
            raise CategoryHomePageContentError(
                "Stats not found in KPIs '{}'".format(kpi)
            )

        stats = kpi_d["stats"]

        if len(stats) == 0:
            raise CategoryHomePageContentError("Stats array is empty")
        for stat in stats:
            if "value" not in stat:
                raise CategoryHomePageContentError(
                    "No value found in stat '{}'".format(json.dump(stat))
                )
            if "label" not in stat:
                raise CategoryHomePageContentError(
                    "No label found in stat '{}'".format(json.dump(stat))
                )

        return stats

    def _extract_details_from_single_stat(self, fs):
        stat_text_css_selector = "chakra-stat__help-text"
        p = fs.select(stat_text_css_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No text found in stat with selector " f"'{stat_text_css_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too much text found in stat with selector "
                f"'{stat_text_css_selector}'"
            )
        stat_text = p[0].text
        if len(stat_text) == 0:
            raise CategoryHomePageContentError(
                "Empty text found in stat with selector " f"'{stat_text_css_selector}'"
            )

        stat_number_css_selector = "chakra-stat__number"
        p = fs.select(stat_number_css_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No number found in stat with selector " f"'{stat_number_css_selector}'"
            )
        if len(p) > 1:
            raise CategoryHomePageContentError(
                "Too much number found in stat with selector "
                f"'{stat_number_css_selector}'"
            )
        stat_number_str = p[0].text
        if len(stat_number_str) == 0:
            raise CategoryHomePageContentError(
                "Empty text found in stat with selector "
                f"'{stat_number_css_selector}'"
            )
        stat_number = re.sub("[^0-9]", "", stat_number_str)
        if len(stat_number) == 0:
            raise CategoryHomePageContentError(
                f"No digits found in number '{stat_number_str}' of stat"
            )
        try:
            return {
                "value": int(stat_number),
                "text": stat_text,
            }
        except ValueError:
            raise CategoryHomePageContentError(
                f"Failed to convert text '{stat_number}' to integer for stat"
            )

    def get_online_metadata(self):
        """metadata from online website, looking at homepage source code"""
        logger.info("Fetching website metadata")

        soup, _ = get_soup("/")

        return {
            "title": soup.find("title").string,
            "description": soup.find("meta", attrs={"name": "description"}).attrs.get(
                "content"
            ),
            "stats": self._extract_stats_from_page(soup),
            "current_year": datetime.date.today().year,
        }

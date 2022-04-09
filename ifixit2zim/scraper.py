# -*- coding: utf-8 -*-

import json
import pathlib
import re
import shutil
import traceback
from datetime import datetime

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape
from zimscraperlib.image.transformation import resize_image

from .constants import (
    CATEGORY_LABELS,
    DEFAULT_HOMEPAGE,
    DIFFICULTY_EASY,
    DIFFICULTY_HARD,
    DIFFICULTY_MODERATE,
    DIFFICULTY_VERY_EASY,
    DIFFICULTY_VERY_HARD,
    GUIDE_LABELS,
    ROOT_DIR,
    Conf,
)
from .shared import Global, GlobalMixin, logger
from .utils import (
    convert_category_title_to_filename,
    get_api_content,
    get_image_path,
    get_image_url,
    get_soup,
    guides_in_progress,
    setlocale,
    setup_s3_and_check_credentials,
)


class CategoryHomePageContentError(Exception):
    pass


class UnexpectedDataKindException(Exception):
    pass


class FinalScrapingFailure(Exception):
    pass


class ifixit2zim(GlobalMixin):
    def __init__(self, **kwargs):

        Global.conf = Conf(**kwargs)
        for option in Global.conf.required:
            if getattr(Global.conf, option) is None:
                raise ValueError(f"Missing parameter `{option}`")

        # jinja2 environment setup
        self.env = Environment(
            loader=FileSystemLoader(ROOT_DIR.joinpath("templates")),
            autoescape=select_autoescape(),
        )
        # self.env.filters["digest"] = get_digest
        self.env.filters["guides_in_progress"] = guides_in_progress
        self.env.filters["get_image_path"] = get_image_path
        self.env.filters["get_image_url"] = get_image_url

        # jinja context that we'll pass to all templates
        self.env_context = {"conf": Global.conf}

        self.category_template = self.env.get_template("category.html")
        self.guide_template = self.env.get_template("guide.html")

        # List of categories / guides which returned request errors, even after backoff.
        # We track them for reporting.
        self.missing_guides = set()
        self.missing_categories = set()
        # List of categories / guides which returned other errors.
        # We track them for reporting
        self.error_guides = set()
        self.error_categories = set()

    @property
    def build_dir(self):
        return self.conf.build_dir

    def cleanup(self):
        """Remove temp files and release resources before exiting"""
        if not self.conf.keep_build_dir:
            logger.debug(f"Removing {self.build_dir}")
            shutil.rmtree(self.build_dir, ignore_errors=True)

    def get_online_metadata(self):
        """metadata from online website, looking at homepage source code"""
        logger.info("Fetching website metadata")

        soup, _ = get_soup("/")

        return {
            "title": soup.find("title").string,
            "description": soup.find("meta", attrs={"name": "description"}).attrs.get(
                "content"
            ),
            "footer_stats": self._extract_footer_stats_from_page(soup),
            "footer_copyright": self._extract_footer_copyright_from_page(soup),
        }

    def sanitize_inputs(self):
        """input & metadata sanitation"""
        logger.debug("Checking user-provided metadata")

        if not self.conf.name:
            self.conf.name = "ifixit_{lang}_{selection}".format(
                lang=self.conf.language["iso-639-1"],
                selection="selection" if self.conf.categories else "all",
            )

        period = datetime.now().strftime("%Y-%m")
        if self.conf.fname:
            # make sure we were given a filename and not a path
            self.conf.fname = pathlib.Path(self.conf.fname.format(period=period))
            if pathlib.Path(self.conf.fname.name) != self.conf.fname:
                raise ValueError(f"filename is not a filename: {self.conf.fname}")
        else:
            self.conf.fname = f"{self.conf.name}_{period}.zim"

        if not self.conf.title:
            self.conf.title = self.metadata["title"]
        self.conf.title = self.conf.title.strip()

        if not self.conf.description:
            self.conf.description = self.metadata["description"]
        self.conf.description = self.conf.description.strip()

        if not self.conf.author:
            self.conf.author = "iFixit"
        self.conf.author = self.conf.author.strip()

        if not self.conf.publisher:
            self.conf.publisher = "openZIM"
        self.conf.publisher = self.conf.publisher.strip()

        self.conf.tags = list(
            set(
                self.conf.tag
                + ["_category:iFixit", "iFixit", "_videos:yes", "_pictures:yes"]
            )
        )

        logger.debug(
            "Configuration after sanitization:\n"
            f"name: {self.conf.name}\n"
            f"fname: {self.conf.fname}\n"
            f"name: {self.conf.author}\n"
            f"fname: {self.conf.publisher}"
        )

    def add_assets(self):
        """download and add site-wide assets, identified in metadata step"""
        logger.info("Adding assets")

        # recursively add our assets, at a path identical to position in repo
        assets_root = pathlib.Path(ROOT_DIR.joinpath("assets"))
        for fpath in assets_root.glob("**/*"):
            if not fpath.is_file():
                continue
            path = str(fpath.relative_to(ROOT_DIR))

            logger.debug(f"> {path}")
            with self.lock:
                self.creator.add_item_for(path=path, fpath=fpath)

    def add_illustrations(self):
        logger.info("Adding illustrations")

        src_illus_fpath = pathlib.Path(ROOT_DIR.joinpath("assets", "illustration.png"))
        tmp_illus_fpath = pathlib.Path(self.build_dir, "illustration.png")

        shutil.copy(src_illus_fpath, tmp_illus_fpath)

        # resize to appropriate size (ZIM uses 48x48 so we double for retina)
        for size in (96, 48):
            resize_image(tmp_illus_fpath, width=size, height=size, method="thumbnail")
            with open(tmp_illus_fpath, "rb") as fh:
                with self.lock:
                    self.creator.add_illustration(size, fh.read())

    def _process_categories(self, categories, force_include=False):
        include_parents = False
        for category in categories:
            include_me = False
            include_childs = False
            if (
                force_include
                or category in self.conf.categories
                or convert_category_title_to_filename(category) in self.conf.categories
            ):
                include_me = True
                include_childs = self.conf.categories_include_children or force_include

            include_due_to_child = self._process_categories(
                categories[category], include_childs
            )

            if include_me or include_due_to_child:
                self.expected_categories.add(category)
                include_parents = True

        return include_parents

    def build_expected_categories(self):
        logger.info("Downloading categories")
        categories = get_api_content("/categories", includeStubs=True)
        self._process_categories(
            categories, (not self.conf.categories) or (len(self.conf.categories) == 0)
        )
        logger.info("{} categories found".format(len(self.expected_categories)))

    guide_regex_full = re.compile(
        r"href=\"https://\w*\.ifixit\.\w*/Guide/.*/(?P<guide_id>\d*)\""
    )
    guide_regex_rel = re.compile(r"href=\"/Guide/.*/(?P<guide_id>\d*).*?\"")
    content_image_regex = re.compile(
        r"(?P<prefix>https://guide-images\.cdn\.ifixit\.com/igi/)"
        r"(?P<image_filename>\w*)\.\w*"
    )
    image_regex = re.compile(r"<img(?P<before>.*?)src=\"(?P<url>.*?)\"")
    device_link_regex_without_href = re.compile(r"/Device/(?P<device>.*)")
    device_link_regex_with_href = re.compile(r"href=\"/Device/(?P<device>.*)\"")

    def _get_image_guid_from_src(self, src):
        # return src
        return self.content_image_regex.sub("\\g<image_filename>", src)

    def _get_category_from_href(self, href):
        return self.device_link_regex_without_href.sub('\\g<device>"', href)

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
        name = self.device_link_regex_without_href.sub("\\g<device>", href)
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
        name = self.device_link_regex_without_href.sub("\\g<device>", href)
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

    def _extract_footer_stats_from_page(self, soup):
        footer_stats_css_selector = "div.footer-stats div"
        footer_stats = [
            self._extract_details_from_footer_stats(fc)
            for fc in soup.select(footer_stats_css_selector)
        ]
        if len(footer_stats) == 0:
            raise CategoryHomePageContentError(
                "No footer stats found with selector " f"'{footer_stats_css_selector}'"
            )
        return footer_stats

    def _extract_details_from_footer_stats(self, fs):
        footer_stats_text_css_selector = "p"
        p = fs.select(footer_stats_text_css_selector)
        if len(p) == 0:
            raise CategoryHomePageContentError(
                "No text found in footer stat with selector "
                f"'{footer_stats_text_css_selector}'"
            )
        if len(p) == 1:
            raise CategoryHomePageContentError(
                "Insufficient text found in footer stat with selector "
                f"'{footer_stats_text_css_selector}'"
            )
        if len(p) > 2:
            raise CategoryHomePageContentError(
                "Too many text found in footer stat with selector "
                f"'{footer_stats_text_css_selector}'"
            )
        text0 = p[0].text
        if len(text0) == 0:
            raise CategoryHomePageContentError(
                "Empty text found first paragraph of footer stat "
                f"'{footer_stats_text_css_selector}'"
            )
        text0digits = re.sub("[^0-9]", "", text0)
        if len(text0digits) == 0:
            raise CategoryHomePageContentError(
                f"No digits found in text '{text0}' of footer stat"
            )
        text1 = p[1].text
        if len(text1) == 0:
            raise CategoryHomePageContentError(
                "Empty text found second paragraph of footer stat "
                f"'{footer_stats_text_css_selector}'"
            )
        try:
            return {
                "value": int(text0digits),
                "text": text1,
            }
        except ValueError:
            raise CategoryHomePageContentError(
                f"Failed to convert text '{text0digits}' to integer for footer " "stat"
            )

    def _extract_footer_copyright_from_page(self, soup):
        footer_copyright_css_selector = "div.footer-container div.copyright"
        footer_copyright = soup.select(footer_copyright_css_selector)
        if len(footer_copyright) == 0:
            raise CategoryHomePageContentError(
                "No footer copyright found with selector "
                f"'{footer_copyright_css_selector}'"
            )
        main_footer_copyright = None
        for fc in footer_copyright:
            if len(fc.text.strip()) > 0:
                if main_footer_copyright is None:
                    main_footer_copyright = fc
                else:
                    raise CategoryHomePageContentError(
                        "Too many footer copyright with selector "
                        f"'{footer_copyright_css_selector}'"
                    )
        if main_footer_copyright is None:
            raise CategoryHomePageContentError(
                "Empty footer copyright found with selector "
                f"'{footer_copyright_css_selector}'"
            )

        return f"{main_footer_copyright}"

    def scrape_homepage(self):

        logger.info("Scraping homepage")

        soup, _ = get_soup("/Guide")

        logger.debug("Processing homepage")

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

        for fc in home_content["featured_categories"]:
            image_path = Global.imager.defer(url=fc["img_url"])
            fc["img_path"] = image_path

        home_content["callout"]["img_path"] = Global.imager.defer(
            url=home_content["callout"]["img_url"]
        )

        logger.debug(
            "Content extracted from /Guide:\n" f"{json.dumps(home_content,indent=2)}"
        )

        page = self.env.get_template("home.html").render(
            home_content=home_content, metadata=self.metadata
        )

        with self.lock:
            self.creator.add_item_for(
                path="home/home.html",
                title=self.conf.title,
                content=page,
                mimetype="text/html",
                is_front=True,
            )

            self.creator.add_redirect(
                path=DEFAULT_HOMEPAGE, target_path="home/home.html"
            )

    def scrape_one_category(self, category):
        category_content = get_api_content(
            f"/wikis/CATEGORY/{category}", langid=self.conf.lang_code
        )

        if category_content is None:
            self.missing_categories.add(category)
            return

        logger.debug(f"Processing category {category}")

        for guide in category_content["featured_guides"]:
            if guide["type"] not in [
                "replacement",
                "technique",
                "teardown",
                "disassembly",
            ]:
                raise UnexpectedDataKindException(
                    "Unsupported type of guide: {} for featured_guide {}".format(
                        guide["type"], guide["guideid"]
                    )
                )
            else:
                self.expected_guides[guide["guideid"]] = {
                    "guideid": guide["guideid"],
                    "locale": guide["locale"],
                }
        for guide in category_content["guides"]:
            if guide["type"] not in [
                "replacement",
                "technique",
                "teardown",
                "disassembly",
            ]:
                raise UnexpectedDataKindException(
                    "Unsupported type of guide: {} for guide {}".format(
                        guide["type"], guide["guideid"]
                    )
                )
            else:
                self.expected_guides[guide["guideid"]] = {
                    "guideid": guide["guideid"],
                    "locale": guide["locale"],
                }

        def _replace_image(m):
            orig_url = m.group("url")
            new_url = get_image_path(orig_url)
            return f"<img{m.group('before')}src=\"{new_url}\""

        category_content["contents_rendered"] = re.sub(
            self.image_regex, _replace_image, category_content["contents_rendered"]
        )
        category_content["contents_rendered"] = self.device_link_regex_with_href.sub(
            'href="./category_\\g<device>.html"',
            category_content["contents_rendered"],
        )
        category_content["filename"] = convert_category_title_to_filename(
            category_content["title"]
        )
        for idx, child in enumerate(category_content["children"]):
            category_content["children"][idx]["filename"] = re.sub(
                r"\s",
                "_",
                category_content["children"][idx]["title"],
            )
        category_rendered = self.category_template.render(
            category=category_content,
            label=CATEGORY_LABELS[self.conf.lang_code],
            metadata=self.metadata,
            lang=self.conf.lang_code,
        )
        with self.lock:
            self.creator.add_item_for(
                path=f"categories/category_{category_content['filename']}.html",
                title=category_content["display_title"],
                content=category_rendered,
                mimetype="text/html",
                is_front=True,
            )

    def scrape_categories(self):

        logger.info(f"Scraping {len(self.expected_categories)} categories")

        num_category = 1
        for category in self.expected_categories:
            try:
                logger.info(
                    f"Scraping category {category} ({num_category}/"
                    f"{len(self.expected_categories)})"
                )
                self.scrape_one_category(category)
            except Exception as ex:
                self.error_categories.add(category)
                logger.warning(f"Error while processing category '{category}': {ex}")
                traceback.print_exc()
            finally:
                if len(self.missing_categories) > self.conf.max_missing_categories:
                    raise FinalScrapingFailure(
                        "Too many categories found missing: "
                        f"{len(self.missing_categories)}"
                    )
                if len(self.error_categories) > self.conf.max_error_categories:
                    raise FinalScrapingFailure(
                        "Too many categories failed to be processed: "
                        f"{len(self.error_categories)}"
                    )
                num_category += 1

    def scrape_one_guide(self, guide):
        guide_content = get_api_content(
            f"/guides/{guide['guideid']}", langid=guide["locale"]
        )

        if guide_content is None:
            logger.warning(f"Missing guide {guide['guideid']}")
            self.missing_guides.add(guide)
            return

        logger.debug(f"Processing guide {guide['guideid']}")

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
        guide_content["introduction_rendered"] = self.guide_regex_full.sub(
            'href="./guide_\\g<guide_id>.html"',
            guide_content["introduction_rendered"],
        )
        guide_content["introduction_rendered"] = self.guide_regex_rel.sub(
            'href="./guide_\\g<guide_id>.html"',
            guide_content["introduction_rendered"],
        )
        guide_content["conclusion_rendered"] = self.guide_regex_full.sub(
            'href="./guide_\\g<guide_id>.html"',
            guide_content["conclusion_rendered"],
        )
        guide_content["conclusion_rendered"] = self.guide_regex_rel.sub(
            'href="./guide_\\g<guide_id>.html"',
            guide_content["conclusion_rendered"],
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
                line["text_rendered"] = self.guide_regex_full.sub(
                    'href="./guide_\\g<guide_id>.html"',
                    line["text_rendered"],
                )
                line["text_rendered"] = self.guide_regex_rel.sub(
                    'href="./guide_\\g<guide_id>.html"',
                    line["text_rendered"],
                )
        guide_rendered = self.guide_template.render(
            guide=guide_content,
            label=GUIDE_LABELS[self.conf.lang_code],
            metadata=self.metadata,
        )
        with self.lock:
            self.creator.add_item_for(
                path=f"guides/guide_{guide_content['guideid']}.html",
                title=guide_content["title"],
                content=guide_rendered,
                mimetype="text/html",
                is_front=True,
            )

    def scrape_guides(self):

        logger.info(f"Scraping {len(self.expected_guides)} guides")

        num_guide = 1
        for guideid, guide in self.expected_guides.items():
            try:
                logger.info(
                    f"Scraping guide {guideid} "
                    f"({num_guide}/{len(self.expected_guides)})"
                )
                self.scrape_one_guide(guide)
            except Exception as ex:
                self.error_guides.add(guideid)
                logger.warning(f"Error while processing guide {guideid}: {ex}")
                traceback.print_exc()
            finally:
                if len(self.missing_guides) > self.conf.max_missing_guides:
                    raise FinalScrapingFailure(
                        "Too many guides found missing: " f"{len(self.missing_guides)}"
                    )
                if len(self.error_guides) > self.conf.max_error_guides:
                    raise FinalScrapingFailure(
                        "Too many guides failed to be processed: "
                        f"{len(self.error_guides)}"
                    )
                num_guide += 1

    def run(self):
        s3_storage = (
            setup_s3_and_check_credentials(self.conf.s3_url_with_credentials)
            if self.conf.s3_url_with_credentials
            else None
        )
        s3_msg = (
            f"\n"
            f"  using cache: {s3_storage.url.netloc} "
            f"with bucket: {s3_storage.bucket_name}"
            if s3_storage
            else ""
        )
        del s3_storage

        logger.info(
            f"Starting scraper with:\n"
            f"  language: {self.conf.language['english']}"
            f" ({self.conf.domain})\n"
            f"  output_dir: {self.conf.output_dir}\n"
            f"  build_dir: {self.build_dir}\n"
            f"{s3_msg}"
        )

        Global.metadata = self.get_online_metadata()
        logger.debug(
            f"Additional metadata scrapped online:\n"
            f"title: {self.metadata['title']}\n"
            f"description: {self.metadata['description']}\n"
            f"footer_stats: {self.metadata['footer_stats']}\n"
            f"footer_copyright: {self.metadata['footer_copyright']}\n"
        )
        self.sanitize_inputs()

        logger.debug("Starting Zim creation")
        Global.setup()
        self.creator.start()

        try:
            self.build_expected_categories()

            self.add_assets()
            self.add_illustrations()
            self.scrape_homepage()
            self.scrape_categories()
            self.scrape_guides()

            logger.info("Awaiting images")
            Global.img_executor.shutdown()

            logger.info(
                f"Stats: {len(self.expected_categories)} categories, "
                f"{len(self.expected_guides)} guides, "
                f"{len(self.missing_categories)} missing categories, "
                f"{len(self.missing_guides)} missing guides, "
                f"{len(self.error_categories)} categories in error, "
                f"{len(self.error_guides)} guides in error, "
                f"{self.imager.nb_requested} images"
            )

        except Exception as exc:
            # request Creator not to create a ZIM file on finish
            self.creator.can_finish = False
            if isinstance(exc, KeyboardInterrupt):
                logger.error("KeyboardInterrupt, exiting.")
            else:
                logger.error(f"Interrupting process due to error: {exc}")
                logger.exception(exc)
            self.imager.abort()
            Global.img_executor.shutdown(wait=False)
            return 1
        else:
            logger.info("Finishing ZIM file")
            # we need to release libzim's resources.
            # currently does nothing but crash if can_finish=False
            # but that's awaiting impl. at libkiwix level
            with self.lock:
                self.creator.finish()
            logger.info(
                f"Finished Zim {self.creator.filename.name} "
                f"in {self.creator.filename.parent}"
            )
        finally:
            self.cleanup()

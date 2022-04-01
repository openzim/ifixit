# -*- coding: utf-8 -*-

import datetime
import json
import pathlib
import re
import shutil

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .constants import DEFAULT_HOMEPAGE, ROOT_DIR, Conf
from .shared import Global, GlobalMixin, logger
from .utils import get_api_content, get_soup, setup_s3_and_check_credentials


class CategoryHomePageContentError(Exception):
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

        # jinja context that we'll pass to all templates
        self.env_context = {"conf": Global.conf}
        # used to prevent twice processing the resources of CSS
        # that we are going to download as they link to each other
        # Source HTML references a dynamic CSS that is built using a varietyof
        # features so it's very common different CSS urls references the same
        # resources (imgs)
        self.resources_digests = set()
        # List of URLs which returned HTTP 404.
        # There are legit scenarios for 404 on wikiHow: login pages
        # we need to track them for later use
        self.missing_articles = set()
        self.missing_categories = set()

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
        logger.debug("Fecthing website metdata")

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

        period = datetime.datetime.now().strftime("%Y-%m")
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
                + ["_category:ifixit", "ifixit", "_videos:yes", "_pictures:yes"]
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

    def _process_categories(self, categories):
        for category in categories:
            self.expected_categories.append(category)
            self._process_categories(categories[category])

    def build_expected_categories(self):
        logger.info("Downloading categories")
        categories = get_api_content("/categories", includeStubs=True)
        self._process_categories(categories)
        logger.info("{} categories found".format(len(self.expected_categories)))

    guide_regex_full = re.compile(
        r"href=\"https://\w*\.ifixit\.\w*/Guide/.*/(?P<guide_id>\d*)\""
    )
    guide_regex_rel = re.compile(r"href=\"/Guide/.*/(?P<guide_id>\d*).*?\"")
    content_image_regex = re.compile(
        r"(?P<prefix>https://guide-images\.cdn\.ifixit\.com/igi/)"
        r"(?P<image_filename>\w*)\.\w*"
    )
    device_link_regex = re.compile(r"/Device/(?P<device>.*)")

    def _get_image_guid_from_src(self, src):
        # return src
        return self.content_image_regex.sub("\\g<image_filename>", src)

    def _get_category_from_href(self, href):
        return self.device_link_regex.sub('\\g<device>"', href)

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
        name = self.device_link_regex.sub("\\g<device>", href)
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
        name = self.device_link_regex.sub("\\g<device>", href)
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

    def add_homepage(self):

        logger.info("Building homepage")

        soup, _ = get_soup("/Guide")

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
            self.add_homepage()

            logger.info("Awaiting images")
            Global.img_executor.shutdown()

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

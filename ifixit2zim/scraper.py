# -*- coding: utf-8 -*-

import pathlib
import shutil
import traceback
from datetime import datetime

from zimscraperlib.image.transformation import resize_image

from .constants import (
    CATEGORY_LABELS,
    DIFFICULTY_EASY,
    DIFFICULTY_HARD,
    DIFFICULTY_MODERATE,
    DIFFICULTY_VERY_EASY,
    DIFFICULTY_VERY_HARD,
    GUIDE_LABELS,
    ROOT_DIR,
    Conf,
)
from .scraper_homepage import ScraperHomepage
from .shared import Global, GlobalMixin, logger
from .utils import get_api_content, setlocale, setup_s3_and_check_credentials


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

        # List of categories / guides which returned request errors, even after backoff.
        # We track them for reporting.
        self.missing_guides = set()
        self.missing_categories = set()
        self.missing_info_wikis = set()
        # List of categories / guides which returned other errors.
        # We track them for reporting
        self.error_guides = set()
        self.error_categories = set()
        self.error_info_wikis = set()

        self.scraper_homepage = ScraperHomepage()

    @property
    def build_dir(self):
        return self.conf.build_dir

    def cleanup(self):
        """Remove temp files and release resources before exiting"""
        if not self.conf.keep_build_dir:
            logger.debug(f"Removing {self.build_dir}")
            shutil.rmtree(self.build_dir, ignore_errors=True)

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
                or Global.convert_title_to_filename(category) in self.conf.categories
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

        category_rendered = self.category_template.render(
            category=category_content,
            label=CATEGORY_LABELS[self.conf.lang_code],
            metadata=self.metadata,
            lang=self.conf.lang_code,
        )
        with self.lock:
            self.creator.add_item_for(
                path=f"categories/category_"
                f"{Global.convert_title_to_filename(category_content['title'])}.html",
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

    def build_expected_info_wikis(self):
        logger.info("Downloading list of INFO wikis")
        limit = 200
        offset = 0
        while True:
            info_wikis = get_api_content("/wikis/INFO", limit=limit, offset=offset)
            if len(info_wikis) == 0:
                break
            for info_wiki in info_wikis:
                self.expected_info_wikis.add(info_wiki["title"])
            offset += limit
        logger.info("{} INFO wikis found".format(len(self.expected_info_wikis)))

    def scrape_info_wikis(self):

        logger.info(f"Scraping {len(self.expected_info_wikis)} INFO wikis")

        num_info_wiki = 1
        for info_wiki_title in self.expected_info_wikis:
            try:
                logger.info(
                    f"Scraping INFO wiki {info_wiki_title} "
                    f"({num_info_wiki}/{len(self.expected_info_wikis)})"
                )
                self.scrape_one_info_wiki(info_wiki_title)
            except Exception as ex:
                self.error_info_wikis.add(info_wiki_title)
                logger.warning(
                    f"Error while processing INFO wiki {info_wiki_title}: {ex}"
                )
                traceback.print_exc()
            finally:
                if len(self.missing_info_wikis) > self.conf.max_missing_info_wikis:
                    raise FinalScrapingFailure(
                        "Too many INFO wikis found missing: "
                        f"{len(self.missing_info_wikis)}"
                    )
                if len(self.error_info_wikis) > self.conf.max_error_info_wikis:
                    raise FinalScrapingFailure(
                        "Too many INFO wikis failed to be processed: "
                        f"{len(self.error_info_wikis)}"
                    )
                num_info_wiki += 1

    def scrape_one_info_wiki(self, info_wiki_title):
        info_wiki_content = get_api_content(f"/wikis/INFO/{info_wiki_title}")

        if info_wiki_content is None:
            self.missing_info_wikis.add(info_wiki_title)
            return

        logger.debug(f"Processing INFO wiki {info_wiki_title}")

        info_wiki_rendered = self.info_wiki_template.render(
            info_wiki=info_wiki_content,
            # label=INFO_WIKI_LABELS[self.conf.lang_code],
            metadata=self.metadata,
            lang=self.conf.lang_code,
        )
        with self.lock:
            self.creator.add_item_for(
                path=f"info_wikis/info_"
                f"{Global.convert_title_to_filename(info_wiki_content['title'])}.html",
                title=info_wiki_content["display_title"],
                content=info_wiki_rendered,
                mimetype="text/html",
                is_front=True,
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

        Global.metadata = self.scraper_homepage.get_online_metadata()
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
            self.build_expected_info_wikis()

            self.add_assets()
            self.add_illustrations()
            self.scraper_homepage.scrape_homepage()
            self.scrape_categories()
            self.scrape_guides()
            self.scrape_info_wikis()

            logger.info("Awaiting images")
            Global.img_executor.shutdown()

            logger.info(
                f"Stats: {len(self.expected_categories)} categories, "
                f"{len(self.expected_guides)} guides, "
                f"{len(self.expected_info_wikis)} INFO wikis, "
                f"{len(self.missing_categories)} missing categories, "
                f"{len(self.missing_guides)} missing guides, "
                f"{len(self.missing_info_wikis)} INFO wikis, "
                f"{len(self.error_categories)} categories in error, "
                f"{len(self.error_guides)} guides in error, "
                f"{len(self.error_info_wikis)} INFO wikis in error, "
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

# -*- coding: utf-8 -*-

import json
import pathlib
import shutil
from datetime import datetime

from schedule import every
from zimscraperlib.image.transformation import resize_image

from .constants import ROOT_DIR, Conf
from .scraper_category import ScraperCategory
from .scraper_guide import ScraperGuide
from .scraper_homepage import ScraperHomepage
from .scraper_info import ScraperInfo
from .scraper_user import ScraperUser
from .shared import Global, GlobalMixin, logger
from .utils import setup_s3_and_check_credentials


class ifixit2zim(GlobalMixin):
    def __init__(self, **kwargs):

        Global.conf = Conf(**kwargs)
        for option in Global.conf.required:
            if getattr(Global.conf, option) is None:
                raise ValueError(f"Missing parameter `{option}`")

        self.scraper_homepage = ScraperHomepage()
        self.scraper_guide = ScraperGuide()
        self.scraper_category = ScraperCategory()
        self.scraper_info = ScraperInfo()
        self.scraper_user = ScraperUser()
        self.scrapers = [
            self.scraper_homepage,
            self.scraper_category,
            self.scraper_guide,
            self.scraper_info,
            self.scraper_user,
        ]

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
            is_selection = (
                self.conf.categories
                or self.conf.guides
                or self.conf.infos
                or self.conf.no_category
                or self.conf.no_guide
                or self.conf.no_info
            )
            self.conf.name = "ifixit_{lang}_{selection}".format(
                lang=self.conf.language["iso-639-1"],
                selection="selection" if is_selection else "all",
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

    def run(self):
        # first report => creates a file with appropriate structure
        self.report_progress()

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
            f"stats: {self.metadata['stats']}\n"
        )
        self.sanitize_inputs()

        logger.debug("Starting Zim creation")
        Global.setup()
        Global.env.filters[
            "get_category_link_from_obj"
        ] = self.scraper_category.get_category_link_from_obj
        Global.env.filters[
            "get_category_link_from_props"
        ] = self.scraper_category.get_category_link_from_props
        Global.env.filters[
            "get_guide_link_from_obj"
        ] = self.scraper_guide.get_guide_link_from_obj
        Global.env.filters[
            "get_guide_link_from_props"
        ] = self.scraper_guide.get_guide_link_from_props
        Global.env.filters[
            "get_info_link_from_obj"
        ] = self.scraper_info.get_info_link_from_obj
        Global.env.filters[
            "get_info_link_from_props"
        ] = self.scraper_info.get_info_link_from_props
        Global.env.filters[
            "get_user_link_from_obj"
        ] = self.scraper_user.get_user_link_from_obj
        Global.env.filters[
            "get_user_link_from_props"
        ] = self.scraper_user.get_user_link_from_props
        Global.get_category_link_from_props = (
            self.scraper_category.get_category_link_from_props
        )
        Global.get_guide_link_from_props = self.scraper_guide.get_guide_link_from_props
        Global.get_info_link_from_props = self.scraper_info.get_info_link_from_props
        Global.get_user_link_from_props = self.scraper_user.get_user_link_from_props
        for scraper in self.scrapers:
            scraper.setup()
        self.creator.start()

        try:

            self.add_assets()
            self.add_illustrations()

            for scraper in self.scrapers:
                scraper.build_expected_items()
                self.report_progress()

            # set a timer to report progress only every 10 seconds, not need to do it
            # after every item scrapped
            every(10).seconds.do(self.report_progress)

            while True:
                for scraper in self.scrapers:
                    scraper.scrape_items()
                needs_rerun = False
                if not Global.conf.scrape_only_first_items:
                    for scraper in self.scrapers:
                        if not scraper.items_queue.empty():
                            needs_rerun = True
                if not needs_rerun:
                    break

            logger.info("Awaiting images")
            Global.img_executor.shutdown()

            self.report_progress()

            stats = "Stats: "
            for scraper in self.scrapers:
                stats += (
                    f"{len(scraper.expected_items_keys)} {scraper.get_items_name()}, "
                )
            for scraper in self.scrapers:
                stats += (
                    f"{len(scraper.missing_items_keys)} missing"
                    f" {scraper.get_items_name()}, "
                )
            for scraper in self.scrapers:
                stats += (
                    f"{len(scraper.error_items_keys)} {scraper.get_items_name()}"
                    " in error, "
                )
            stats += f"{len(self.imager.handled)} images"

            logger.info(stats)

            logger.info("Null categories:")
            for key in Global.null_categories:
                logger.info(f"\t{key}")

            logger.info("IFIXIT_EXTERNAL URLS:")
            for exturl in sorted(Global.ifixit_external_content):
                logger.info(f"\t{exturl}")

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
            if self.creator.can_finish:
                logger.info("Finishing ZIM file")
                with self.lock:
                    self.creator.finish()
                logger.info(
                    f"Finished Zim {self.creator.filename.name} "
                    f"in {self.creator.filename.parent}"
                )
        finally:
            logger.info("Cleaning up")
            with self.lock:
                self.cleanup()

        logger.info("Scraper has finished normally")

    def report_progress(self):
        if not Global.conf.stats_filename:
            return
        done = 0
        total = 0
        for scraper in self.scrapers:
            scraper_total = len(scraper.expected_items_keys) + len(
                scraper.unexpected_items_keys
            )
            scraper_remains = scraper.items_queue.qsize()
            scraper_done = scraper_total - scraper_remains
            total += scraper_total
            done += scraper_done
        progress = {
            "done": done,
            "total": total,
        }
        with open(Global.conf.stats_filename, "w") as outfile:
            json.dump(progress, outfile, indent=2)

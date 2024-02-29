import datetime
import json
import pathlib
import shutil
import threading

from jinja2 import Environment, FileSystemLoader, select_autoescape
from schedule import every
from zimscraperlib.image.transformation import resize_image
from zimscraperlib.inputs import compute_descriptions
from zimscraperlib.zim.creator import Creator

from ifixit2zim.constants import (
    DEFAULT_HOMEPAGE,
    ROOT_DIR,
    Configuration,
)
from ifixit2zim.executor import Executor
from ifixit2zim.imager import Imager
from ifixit2zim.processor import Processor
from ifixit2zim.scraper_category import ScraperCategory
from ifixit2zim.scraper_guide import ScraperGuide
from ifixit2zim.scraper_homepage import ScraperHomepage
from ifixit2zim.scraper_info import ScraperInfo
from ifixit2zim.scraper_user import ScraperUser
from ifixit2zim.shared import logger
from ifixit2zim.utils import Utils

LOCALE_LOCK = threading.Lock()


class IFixit2Zim:
    def __init__(self, **kwargs):
        self.configuration = Configuration(**kwargs)
        for option in self.configuration.required:
            if getattr(self.configuration, option) is None:
                raise ValueError(f"Missing parameter `{option}`")

        self.scraper_homepage = ScraperHomepage(scraper=self)
        self.scraper_guide = ScraperGuide(scraper=self)
        self.scraper_category = ScraperCategory(scraper=self)
        self.scraper_info = ScraperInfo(scraper=self)
        self.scraper_user = ScraperUser(scraper=self)
        self.scrapers = [
            self.scraper_homepage,
            self.scraper_category,
            self.scraper_guide,
            self.scraper_info,
            self.scraper_user,
        ]
        self.lock = threading.Lock()
        self.processor = Processor(scraper=self)
        self.utils = Utils(configuration=self.configuration)

    @property
    def build_dir(self):
        return self.configuration.build_dir

    def cleanup(self):
        """Remove temp files and release resources before exiting"""
        if not self.configuration.keep_build_dir:
            logger.debug(f"Removing {self.build_dir}")
            shutil.rmtree(self.build_dir, ignore_errors=True)

    def sanitize_inputs(self):
        """input & metadata sanitation"""
        logger.debug("Checking user-provided metadata")

        if not self.configuration.name:
            is_selection = (
                self.configuration.categories
                or self.configuration.guides
                or self.configuration.infos
                or self.configuration.no_category
                or self.configuration.no_guide
                or self.configuration.no_info
            )
            self.configuration.name = "ifixit_{lang}_{selection}".format(
                lang=self.configuration.language["iso-639-1"],
                selection="selection" if is_selection else "all",
            )

        period = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m")
        if self.configuration.fname:
            # make sure we were given a filename and not a path
            self.configuration.fpath = pathlib.Path(
                self.configuration.fname.format(period=period)
            )
            if pathlib.Path(self.configuration.fpath.name) != self.configuration.fpath:
                raise ValueError(
                    f"filename is not a filename: {self.configuration.fname}"
                )
        else:
            self.configuration.fpath = pathlib.Path(
                f"{self.configuration.name}_{period}.zim"
            )

        # TODO: fixed title based on defined convention (30 chars only)
        if not self.configuration.title:
            self.configuration.title = self.metadata["title"]
        self.configuration.title = self.configuration.title.strip()

        (
            self.configuration.description,
            self.configuration.long_description,
        ) = compute_descriptions(
            self.metadata["description"],
            self.configuration.description,
            self.configuration.long_description,
        )

        self.configuration.author = self.configuration.author.strip()

        self.configuration.publisher = self.configuration.publisher.strip()

        self.configuration.tag = list(
            {
                *self.configuration.tag,
                "_category:iFixit",
                "iFixit",
                "_videos:yes",
                "_pictures:yes",
            }
        )

        logger.debug(
            "Configuration after sanitization:\n"
            f"name: {self.configuration.name}\n"
            f"fname: {self.configuration.fname}\n"
            f"author: {self.configuration.author}\n"
            f"publisher: {self.configuration.publisher}"
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

    def setup(self):
        # order matters are there are references between them

        # images handled on a different queue.
        # mostly network I/O to retrieve and/or upload image.
        # if not in S3 bucket, convert/optimize webp image
        # svg images, stored but not optimized

        self.img_executor = Executor(
            queue_size=100,
            nb_workers=50,
            prefix="IMG-T-",
        )

        self.imager = Imager(scraper=self)

        self.creator = Creator(
            filename=self.configuration.output_dir / self.configuration.fpath,
            main_path=DEFAULT_HOMEPAGE,
            workaround_nocancel=False,
        ).config_metadata(
            Illustration_48x48_at_1=b"illustration",
            Language=self.configuration.language["iso-639-3"],
            Title=self.configuration.title,
            Description=self.configuration.description,
            Creator=self.configuration.author,
            Publisher=self.configuration.publisher,
            Name=self.configuration.name,
            Tags=";".join(self.configuration.tag),
            Date=datetime.datetime.now(tz=datetime.UTC).date(),
        )

        # jinja2 environment setup
        self.env = Environment(
            loader=FileSystemLoader(ROOT_DIR.joinpath("templates")),
            autoescape=select_autoescape(),
        )

        def _raise_helper(msg):
            raise Exception(msg)

        self.env.globals["raise"] = _raise_helper
        self.env.globals["str"] = lambda x: str(x)
        self.env.filters["guides_in_progress"] = self.processor.guides_in_progress
        self.env.filters["category_count_parts"] = self.processor.category_count_parts
        self.env.filters["category_count_tools"] = self.processor.category_count_tools
        self.env.filters["get_image_path"] = self.processor.get_image_path
        self.env.filters["get_image_url"] = self.processor.get_image_url
        self.env.filters["cleanup_rendered_content"] = (
            self.processor.cleanup_rendered_content
        )
        self.env.filters["get_timestamp_day_rendered"] = (
            self.processor.get_timestamp_day_rendered
        )
        self.env.filters["get_item_comments_count"] = (
            self.processor.get_item_comments_count
        )
        self.env.filters["get_guide_total_comments_count"] = (
            self.processor.get_guide_total_comments_count
        )
        self.env.filters["get_user_display_name"] = self.processor.get_user_display_name

    def run(self):
        # first report => creates a file with appropriate structure
        self.report_progress()

        s3_storage = (
            self.utils.setup_s3_and_check_credentials(
                self.configuration.s3_url_with_credentials
            )
            if self.configuration.s3_url_with_credentials
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
            f"  language: {self.configuration.language['english']}"
            f" ({self.configuration.domain})\n"
            f"  output_dir: {self.configuration.output_dir}\n"
            f"  build_dir: {self.build_dir}\n"
            f"{s3_msg}"
        )

        self.metadata = self.scraper_homepage.get_online_metadata()
        logger.debug(
            f"Additional metadata scrapped online:\n"
            f"title: {self.metadata['title']}\n"
            f"description: {self.metadata['description']}\n"
            f"stats: {self.metadata['stats']}\n"
        )
        self.sanitize_inputs()

        logger.debug("Starting Zim creation")
        self.setup()
        self.env.filters["get_category_link_from_obj"] = (
            self.scraper_category.get_category_link_from_obj
        )
        self.env.filters["get_category_link_from_props"] = (
            self.scraper_category.get_category_link_from_props
        )
        self.env.filters["get_guide_link_from_obj"] = (
            self.scraper_guide.get_guide_link_from_obj
        )
        self.env.filters["get_guide_link_from_props"] = (
            self.scraper_guide.get_guide_link_from_props
        )
        self.env.filters["get_info_link_from_obj"] = (
            self.scraper_info.get_info_link_from_obj
        )
        self.env.filters["get_info_link_from_props"] = (
            self.scraper_info.get_info_link_from_props
        )
        self.env.filters["get_user_link_from_obj"] = (
            self.scraper_user.get_user_link_from_obj
        )
        self.env.filters["get_user_link_from_props"] = (
            self.scraper_user.get_user_link_from_props
        )
        self.get_category_link_from_props = (
            self.scraper_category.get_category_link_from_props
        )
        self.get_guide_link_from_props = self.scraper_guide.get_guide_link_from_props
        self.get_info_link_from_props = self.scraper_info.get_info_link_from_props
        self.get_user_link_from_props = self.scraper_user.get_user_link_from_props
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
                if not self.configuration.scrape_only_first_items:
                    for scraper in self.scrapers:
                        if not scraper.items_queue.empty():
                            needs_rerun = True
                if not needs_rerun:
                    break

            logger.info("Awaiting images")
            self.img_executor.shutdown()

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
            for key in self.processor.null_categories:
                logger.info(f"\t{key}")

            logger.info("IFIXIT_EXTERNAL URLS:")
            for exturl in sorted(self.processor.ifixit_external_content):
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
            self.img_executor.shutdown(wait=False)
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
        if not self.configuration.stats_path:
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
        with open(self.configuration.stats_path, "w") as outfile:
            json.dump(progress, outfile, indent=2)

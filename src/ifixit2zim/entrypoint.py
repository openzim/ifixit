#!/usr/bin/env python

import argparse
import os
import sys

from ifixit2zim.constants import NAME, SCRAPER, URLS
from ifixit2zim.shared import logger, set_debug


def main():
    parser = argparse.ArgumentParser(
        prog=NAME,
        description="Scraper to create ZIM files ifixit articles",
    )

    parser.add_argument(
        "--language",
        choices=URLS.keys(),
        required=True,
        help="ifixit website to build from",
        dest="lang_code",
    )

    parser.add_argument(
        "--output",
        help="Output folder for ZIM file",
        default="/output",
        dest="_output_name",
    )

    parser.add_argument(
        "--name",
        help="ZIM name. Used as identifier and filename (date will be appended). "
        "Constructed from language if not supplied",
    )

    parser.add_argument(
        "--title",
        help="Custom title for your ZIM (30 chars max).",
    )

    parser.add_argument(
        "--description",
        help="Custom description for your ZIM (80 chars max). "
        "Based on iFixit homepage description (meta) otherwise",
    )

    parser.add_argument(
        "--long-description",
        help="Custom long description for your ZIM (4000 chars max). "
        "Based on iFixit homepage description (meta) otherwise",
    )

    parser.add_argument(
        "--icon",
        help="Custom icon for your ZIM (path or URL). iFixit square logo otherwise",
    )

    parser.add_argument(
        "--creator",
        help="Name of content creator. “iFixit” otherwise",
        dest="author",
        default="iFixit",
    )

    parser.add_argument(
        "--publisher",
        help="Custom publisher name (ZIM metadata). “openZIM” otherwise",
        default="openZIM",
    )

    parser.add_argument(
        "--tag",
        help="Add tag to the ZIM file. "
        "_category:ifixit and ifixit added automatically. Use --tag several "
        " times or separate with `;`",
        default=[],
        action="append",
    )

    parser.add_argument(
        "--zim-file",
        help="ZIM file name (based on --name if not provided)",
        dest="fname",
    )

    parser.add_argument(
        "--optimization-cache",
        help="URL with credentials to S3 for using as optimization cache",
        dest="s3_url_with_credentials",
    )

    parser.add_argument(
        "--debug",
        help="Enable verbose output",
        action="store_true",
        dest="debug",
        default=False,
    )

    parser.add_argument(
        "--tmp-dir",
        help="Path to create temp folder in. Used for building ZIM file.",
        default=os.getenv("TMPDIR", "."),
        dest="_tmp_name",
    )

    parser.add_argument(
        "--keep",
        help="Don't remove build folder on start (for debug/devel)",
        default=False,
        action="store_true",
        dest="keep_build_dir",
    )

    parser.add_argument(
        "--build-in-tmp",
        help="Use --tmp-dir value as workdir. Otherwise, a unique sub-folder "
        "is created inside it. Useful to reuse downloaded files (debug/devel)",
        default=False,
        action="store_true",
        dest="build_dir_is_tmp_dir",
    )

    parser.add_argument(
        "--delay",
        help="Add this delay (seconds) before each request to please "
        "iFixit servers. Can be fractions. Defaults to 0: no delay",
        type=float,
    )

    parser.add_argument(
        "--api-delay",
        help="Add this delay (seconds) before each API query (!= calls) to "
        "please iFixit servers. Can be fractions. Defaults to 0: no delay",
        type=float,
    )

    parser.add_argument(
        "--cdn-delay",
        help="Add this delay (seconds) before each CDN file download to please "
        "iFixit servers. Can be fractions. Defaults to 0: no delay",
        type=float,
    )

    parser.add_argument(
        "--skip-checks",
        help="[dev] Don't perform Integrity Checks on start",
        default=False,
        action="store_true",
        dest="skip_checks",
    )

    parser.add_argument(
        "--stats-filename",
        help="Path to store the progress JSON file to.",
        dest="stats_filename",
    )

    parser.add_argument(
        "--version",
        help="Display scraper version and exit",
        action="version",
        version=SCRAPER,
    )

    parser.add_argument(
        "--max-missing-items-percent",
        help="Amount of missing items which will force the scraper to stop, expressed"
        " as a percentage of the total number of items to retrieve. Integer from 1 to"
        " 100.",
        default=5,
        type=int,
        dest="max_missing_items_percent",
    )

    parser.add_argument(
        "--max-error-items-percent",
        help="Amount of items with failed processing which will force the scraper to"
        " stop, expressed as a percentage of the total number of items to retrieve."
        " Integer from 1 to 100.",
        default=5,
        type=int,
        dest="max_error_items_percent",
    )

    parser.add_argument(
        "--category",
        help="Only scrape this category (can be specified multiple times). "
        "Specify the category name",
        dest="categories",
        action="append",
    )

    parser.add_argument(
        "--no-category",
        help="Do not scrape any category.",
        dest="no_category",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--guide",
        help="Only scrape this guide (can be specified multiple times). "
        "Specify the guide name",
        dest="guides",
        action="append",
    )

    parser.add_argument(
        "--no-guide",
        help="Do not scrape any guide.",
        dest="no_guide",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--info",
        help="Only scrape this info (can be specified multiple times). "
        "Specify the info name",
        dest="infos",
        action="append",
    )

    parser.add_argument(
        "--no-info",
        help="Do not scrape any info.",
        dest="no_info",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--user",
        help="Only scrape this user (can be specified multiple times). "
        "Specify the userid",
        dest="users",
        action="append",
    )

    parser.add_argument(
        "--no-user",
        help="Do not scrape any user.",
        dest="no_user",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--scrape-only-first-items",
        help="Scrape only first items of every type.",
        dest="scrape_only_first_items",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--no-cleanup",
        help="Do not cleanup HTML content.",
        dest="no_cleanup",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()
    set_debug(args.debug)

    from ifixit2zim.scraper import IFixit2Zim

    try:
        scraper = IFixit2Zim(**dict(args._get_kwargs()))
        sys.exit(scraper.run())
    except Exception as exc:
        logger.error("FAILED. An error occurred", exc_info=exc)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

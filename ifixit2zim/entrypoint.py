#!/usr/bin/env python

import argparse
import os
import sys

from .constants import NAME, SCRAPER, URLS
from .shared import Global, logger


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
        dest="_output_dir",
    )

    parser.add_argument(
        "--name",
        help="ZIM name. Used as identifier and filename (date will be appended). "
        "Constructed from language if not supplied",
    )

    parser.add_argument(
        "--title",
        help="Custom title for your ZIM. iFixit homepage title otherwise",
    )

    parser.add_argument(
        "--description",
        help="Custom description for your ZIM. "
        "iFixit homepage description (meta) otherwise",
    )

    parser.add_argument(
        "--icon",
        help="Custom icon for your ZIM (path or URL). " "iFixit square logo otherwise",
    )

    parser.add_argument(
        "--creator",
        help="Name of content creator. “iFixit” otherwise",
        dest="author",
    )

    parser.add_argument(
        "--publisher",
        help="Custom publisher name (ZIM metadata). “openZIM” otherwise",
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
        default=False,
    )

    parser.add_argument(
        "--tmp-dir",
        help="Path to create temp folder in. Used for building ZIM file.",
        default=os.getenv("TMPDIR", "."),
        dest="_tmp_dir",
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
        "--max-missing-guides",
        help="Amount of missing guides which will force the scraper to stop",
        default=100,
        type=int,
        dest="max_missing_guides",
    )

    parser.add_argument(
        "--max-missing-categories",
        help="Amount of missing categories which will force the scraper to stop",
        default=100,
        type=int,
        dest="max_missing_categories",
    )

    parser.add_argument(
        "--max-error-guides",
        help="Amount of guides with failed processing which will force the scraper to "
        "stop",
        default=100,
        type=int,
        dest="max_error_guides",
    )

    parser.add_argument(
        "--max-error-categories",
        help="Amount of categories with failed processing which will force the scraper "
        "to stop",
        default=100,
        type=int,
        dest="max_error_categories",
    )

    parser.add_argument(
        "--category",
        help="Only scrape this category (can be specified multiple times). "
        "Specify the category name",
        dest="categories",
        action="append",
    )

    parser.add_argument(
        "--categories_include_children",
        help="If only specific categories are requested with the paramter --category,"
        " this parameter specifies that we also want their children categories in the"
        " given ZIM",
        default=False,
        action="store_true",
        dest="categories_include_children",
    )

    parser.add_argument(
        "--guide",
        help="Only scrape this guide (can be specified multiple times). "
        "Specify the guide ID (number)",
        dest="guides",
        action="append",
    )

    args = parser.parse_args()
    Global.set_debug(args.debug)

    from .scraper import ifixit2zim

    try:
        scraper = ifixit2zim(**dict(args._get_kwargs()))
        sys.exit(scraper.run())
    except Exception as exc:
        logger.error(f"FAILED. An error occurred: {exc}")
        if args.debug:
            logger.exception(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()

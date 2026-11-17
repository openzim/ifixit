#!/usr/bin/env python3
"""Download and localize the iFixit CSS assets used by the templates.

Asset filenames contain generated hashes and change when iFixit rebuilds its
frontend. This script therefore discovers the current CSS URLs from a local
HTTrack mirror (or from explicitly supplied HTML pages), downloads the CSS
files and their ``url(...)`` dependencies, rewrites those dependencies to local
``../assets/...`` paths, and updates the Jinja templates to the new filenames.

Typical usage::

    python scripts/update_assets.py --mirror-dir tmp/www.ifixit.com

The mirror is only read for HTML; the CSS and dependencies are downloaded from
``assets.cdn.ifixit.com``.
"""

import argparse
import collections
import logging
import pathlib
import re
import sys
import urllib.parse

import requests

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "src" / "ifixit2zim" / "assets"
TEMPLATES_DIR = ROOT_DIR / "src" / "ifixit2zim" / "templates"
DEFAULT_MIRROR_DIR = ROOT_DIR / "tmp" / "www.ifixit.com"
CDN_HOST = "assets.cdn.ifixit.com"
DEFAULT_TIMEOUT = 30

# Stable prefix -> logical asset. The rest of the filename is a generated hash.
ASSET_PREFIXES = {
    "font-awesome-": "base",
    "header_footer_old-": "base",
    "Shared-print-": "base",
    "guide-all-": "base",
    "module-all-": "base",
    "7593.": "base",
    "guidepage.js.": "base",
    "tailwind-phtml.css.": "base",
    "area_index-": "home",
    "Wiki-topic-": "category/info",
    "Wiki-common-": "category/info/user",
    "Shared-cart_banner-": "guide",
    "Shared-attachment_link-": "guide",
    "new-guide-view-all-": "guide",
    "prosemirror-all-": "guide",
    "Wiki-wiki-": "user",
}

HTML_CSS_RE = re.compile(r"https://assets\.cdn\.ifixit\.com/[^\"'\s>]+\.css")
CSS_URL_RE = re.compile(r"url\((.*?)\)", re.IGNORECASE)
logger = logging.getLogger("update-assets")


def local_name(url: str) -> str:
    """Basename of an asset URL, without query string."""
    path = urllib.parse.urlparse(url).path
    return pathlib.PurePosixPath(path).name


def is_cdn_asset(url: str) -> bool:
    """Whether the URL points to a downloadable iFixit static asset."""
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc == CDN_HOST and parsed.path.startswith("/static/")


def download(session: requests.Session, url: str, timeout: int) -> bytes:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def discover_css_urls(
    mirror_dir: pathlib.Path | None,
    page_urls: list[str],
    session: requests.Session,
    timeout: int,
) -> collections.Counter[str]:
    """Collect CSS URLs referenced by mirrored or live HTML pages."""
    counts: collections.Counter[str] = collections.Counter()
    wanted = tuple(ASSET_PREFIXES)

    def add_css_from_html(html: str) -> None:
        for url in HTML_CSS_RE.findall(html):
            counts[url] += 1

    def all_prefixes_found() -> bool:
        names = [local_name(url) for url in counts]
        return all(any(name.startswith(prefix) for name in names) for prefix in wanted)

    if mirror_dir is not None:
        if not mirror_dir.is_dir():
            raise FileNotFoundError(f"mirror directory not found: {mirror_dir}")
        for path in mirror_dir.rglob("*.html"):
            try:
                add_css_from_html(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError as exc:
                logger.warning(f"Unable to read {path}: {exc}")
            if all_prefixes_found():
                break

    for page_url in page_urls:
        logger.info(f"Discovering assets from {page_url}")
        html = download(session, page_url, timeout).decode("utf-8", errors="replace")
        add_css_from_html(html)

    return counts


def select_current_assets(
    counts: collections.Counter[str],
) -> dict[str, str]:
    """Pick the current URL for each stable prefix."""
    selected: dict[str, str] = {}
    for prefix in ASSET_PREFIXES:
        matches = [
            (count, url)
            for url, count in counts.items()
            if local_name(url).startswith(prefix)
        ]
        if not matches:
            raise RuntimeError(f"no CSS asset found for prefix {prefix!r}")
        matches.sort(key=lambda item: (-item[0], item[1]))
        count, url = matches[0]
        if len(matches) > 1:
            logger.warning(
                f"Multiple assets found for {prefix!r}; using {local_name(url)} "
                f"(seen {count} times)"
            )
        selected[prefix] = url
    return selected


def rewrite_css(
    session: requests.Session,
    css_url: str,
    css_text: str,
    timeout: int,
    *,
    dry_run: bool,
) -> str:
    """Rewrite a CSS file's url(...) references to local asset paths."""
    downloaded: set[str] = set()

    def replace_url(match: re.Match[str]) -> str:
        raw_url = match.group(1).strip().strip("\"'")
        if raw_url.startswith("data:"):
            return match.group(0)

        resolved_url = urllib.parse.urljoin(css_url, raw_url)
        if not is_cdn_asset(resolved_url):
            logger.warning(f"Leaving non-CDN URL untouched in {css_url}: {raw_url}")
            return match.group(0)

        asset_name = local_name(resolved_url)
        if not asset_name:
            logger.warning(f"Unable to determine asset name for {resolved_url}")
            return match.group(0)

        if asset_name not in downloaded:
            logger.info(f"  + {asset_name}")
            if not dry_run:
                (ASSETS_DIR / asset_name).write_bytes(
                    download(session, resolved_url, timeout)
                )
            downloaded.add(asset_name)

        return f"url(../assets/{asset_name})"

    return CSS_URL_RE.sub(replace_url, css_text)


def update_templates(
    selected: dict[str, str],
    *,
    dry_run: bool,
) -> None:
    """Point all template CSS references at the newly discovered filenames."""
    replacements = {prefix: local_name(url) for prefix, url in selected.items()}
    for template in TEMPLATES_DIR.glob("*.html"):
        text = template.read_text(encoding="utf-8")
        updated = text
        for prefix, new_name in replacements.items():
            updated = re.sub(
                rf"assets/{re.escape(prefix)}[^\"'\s>]+\.css",
                f"assets/{new_name}",
                updated,
            )
        if updated != text:
            logger.info(f"Updating {template.name}")
            if not dry_run:
                template.write_text(updated, encoding="utf-8")


def remove_stale_css(
    selected: dict[str, str],
    *,
    dry_run: bool,
) -> None:
    """Delete CSS files for managed prefixes that are no longer referenced."""
    current = {local_name(url) for url in selected.values()}
    for asset in ASSETS_DIR.glob("*.css"):
        if asset.name in current:
            continue
        if any(asset.name.startswith(prefix) for prefix in ASSET_PREFIXES):
            logger.info(f"Removing stale {asset.name}")
            if not dry_run:
                asset.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mirror-dir",
        type=pathlib.Path,
        default=DEFAULT_MIRROR_DIR,
        help=f"HTTrack mirror directory (default: {DEFAULT_MIRROR_DIR})",
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        help="additional HTML page URL to discover CSS references from",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be downloaded or changed without writing files",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    mirror_dir = args.mirror_dir
    if not mirror_dir.is_dir() and not args.url:
        logger.error(
            f"Mirror directory not found: {mirror_dir}. "
            "Pass --mirror-dir or at least one --url."
        )
        sys.exit(1)

    with requests.Session() as session:
        session.headers["User-Agent"] = "ifixit2zim asset updater"
        counts = discover_css_urls(mirror_dir, args.url, session, args.timeout)
        selected = select_current_assets(counts)

        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        for css_url in selected.values():
            css_name = local_name(css_url)
            logger.info(f"Downloading {css_name}")
            css_text = download(session, css_url, args.timeout).decode(
                "utf-8", errors="replace"
            )
            rewritten = rewrite_css(
                session,
                css_url,
                css_text,
                args.timeout,
                dry_run=args.dry_run,
            )
            if not args.dry_run:
                (ASSETS_DIR / css_name).write_text(rewritten, encoding="utf-8")

        update_templates(selected, dry_run=args.dry_run)
        remove_stale_css(selected, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

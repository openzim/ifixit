import re
import urllib.parse
from typing import Any

from ifixit2zim.constants import URLS
from ifixit2zim.context import Context
from ifixit2zim.exceptions import UnexpectedDataKindExceptionError
from ifixit2zim.scraper_generic import ScraperGeneric
from ifixit2zim.shared import logger

ITEM_PATH_PREFIX = "Item/"
LOCALE_PREFIX_RE = re.compile(r"^[a-z]{2}-[a-z]{2}$")


def build_item_path(url_or_path: str) -> str:
    """Local ZIM path for an Item URL, e.g. ``Item/Spudger``."""
    path = urllib.parse.unquote(urllib.parse.urlparse(url_or_path).path)
    parts = path.lstrip("/").split("/")
    if parts and parts[0].lower() == "item":
        parts[0] = "Item"
    item_path = "/".join(parts)
    if not item_path.startswith(ITEM_PATH_PREFIX):
        item_path = f"{ITEM_PATH_PREFIX}{item_path.lstrip('/')}"
    return item_path


def normalize_product_url(url: str) -> str:
    """Locale-independent path key for a product URL."""
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    parts = [part for part in path.split("/") if part]
    if parts and LOCALE_PREFIX_RE.match(parts[0]):
        parts = parts[1:]
    return "/".join(parts)


class ScraperItem(ScraperGeneric):
    """Scraper for WIKI namespace ITEM pages (parts and tools)."""

    def __init__(self, context: Context) -> None:
        super().__init__(context)
        # Rendering is deferred until all guides have been processed so that
        # every guide reference using this item is known.
        self.pending_items: list[tuple[str, dict[str, Any], Any]] = []
        self.guide_refs: dict[str, list[dict[str, str]]] = {}
        self.product_to_item: dict[str, str] = {}

    def setup(self) -> None:
        self.item_template = self.env.get_template("item.html")

    def get_items_name(self) -> str:
        return "item"

    def record_guide_reference(
        self,
        item_url: str,
        product_url: str | None,
        guide_title: str,
        guide_url: str,
    ) -> None:
        """Record a guide reference and product URL for an Item page."""
        item_path = build_item_path(item_url)
        if product_url:
            self.product_to_item.setdefault(
                normalize_product_url(product_url), item_path
            )
        self._add_item_to_scrape(item_path, item_url)
        references = self.guide_refs.setdefault(item_path, [])
        reference = {"title": guide_title, "url": guide_url}
        if reference not in references:
            references.append(reference)

    def get_item_link_from_product(self, product_url: str) -> str | None:
        """Local Item link for a product URL, when a guide mapped it."""
        item_path = self.product_to_item.get(normalize_product_url(product_url))
        if item_path is None:
            return None
        self.record_item_link(item_path, item_path)
        return urllib.parse.quote(item_path)

    def _add_item_to_scrape(self, item_path: str, item_url: str | None) -> str:
        self.add_item_to_scrape(
            item_path,
            {"item_url": item_url},
            is_expected=False,
            warn_unexpected=False,
        )
        return item_path

    def get_item_link_from_obj(self, item: dict[str, Any]) -> str:
        item_url = item.get("wiki_url")
        if not item_url:
            raise UnexpectedDataKindExceptionError(
                f"Impossible to extract item wiki URL from {item}"
            )
        item_path = build_item_path(item_url)
        self.record_item_link(item_path, item_path)
        self._add_item_to_scrape(item_path, item_url)
        return urllib.parse.quote(item_path)

    def get_item_link_from_props(self, item_path: str) -> str:
        built_path = build_item_path(item_path)
        self.record_item_link(built_path, built_path)
        self._add_item_to_scrape(built_path, item_path)
        return urllib.parse.quote(built_path)

    def build_expected_items(self) -> None:
        # Items are discovered while processing guides and rendered content.
        return

    def _get_item_endpoint(self, item_path: str) -> str:
        slug = item_path.split("/", 1)[1]
        return f"/wikis/ITEM/{slug}"

    def _get_item_content(self, endpoint: str) -> dict[str, Any] | None:
        content = self.client.get_api_content(
            endpoint, langid=self.configuration.lang_code
        )
        if content and content.get("revisionid", 0) > 0:
            return content

        logger.warning("Falling back to item in EN")
        content = self.client.get_api_content(endpoint, langid="en")
        if content and content.get("revisionid", 0) > 0:
            return content

        for lang in URLS:
            logger.warning(f"Falling back to item in {lang}")
            content = self.client.get_api_content(endpoint, langid=lang)
            if content and content.get("revisionid", 0) > 0:
                return content

        return None

    def get_one_item_content(
        self,
        item_key: str,
        item_data: dict[str, Any],  # noqa: ARG002
    ) -> Any:
        endpoint = self._get_item_endpoint(item_key)
        content = self._get_item_content(endpoint)
        if content is None:
            logger.warning(f"Impossible to get item content: {item_key}")
        return content

    def add_item_redirect(
        self,
        item_key: str,
        item_data: dict[str, Any],  # noqa: ARG002
        redirect_kind: str,
    ) -> None:
        self.processor.add_redirect(
            path=item_key,
            target_path=f"home/{redirect_kind}",
        )

    def process_one_item(
        self,
        item_key: str,
        item_data: dict[str, Any],
        item_content: Any,
    ) -> None:
        # Enqueue links from the rendered content now. Rendering itself is
        # deferred to finalize() so guide references are complete.
        rel_prefix = "../" * item_key.count("/")
        self.processor.cleanup_rendered_content(
            item_content.get("contents_rendered") or "", rel_prefix
        )
        self.pending_items.append((item_key, item_data, item_content))

    def _render_item(self, item_key: str, item_content: dict[str, Any]) -> None:
        rel_prefix = "../" * item_key.count("/")
        rendered = self.item_template.render(
            item=item_content,
            guide_references=self.guide_refs.get(item_key, []),
            metadata=self.metadata,
            lang=self.configuration.lang_code,
            rel_prefix=rel_prefix,
        )
        self.processor.add_html_item(
            path=item_key,
            title=item_content.get("display_title") or item_content["title"],
            content=rendered,
        )

    def finalize(self) -> None:
        for item_key, item_data, item_content in self.pending_items:
            try:
                self._render_item(item_key, item_content)
            except Exception as exc:
                self.error_items_keys.add(item_key)
                logger.warning(
                    f"Error while processing item {item_key}",
                    exc_info=exc,
                )
                self.add_item_error_redirect(item_key, item_data)
        self.pending_items.clear()

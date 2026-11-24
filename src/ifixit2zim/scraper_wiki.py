import re
import urllib.parse
from typing import Any

from bs4 import BeautifulSoup

from ifixit2zim.constants import CATEGORY_LABELS, URLS
from ifixit2zim.context import Context
from ifixit2zim.exceptions import UnexpectedDataKindExceptionError
from ifixit2zim.scraper_generic import ScraperGeneric
from ifixit2zim.shared import logger

TROUBLESHOOTING_PROBLEM_RE = re.compile(
    r"^(?:https?://[^/]+)?/Troubleshooting/(?P<category>[^/?#]+)/"
    r"(?P<title>[^/?#]+)/(?P<wikiid>\d+)$"
)
TROUBLESHOOTING_INDEX_PATH_PARTS = 2


def _normalize_problem_href(href: str) -> str:
    href = href.removeprefix("./")
    if href.startswith("Troubleshooting/"):
        href = f"/{href}"
    path = urllib.parse.urlparse(urllib.parse.urljoin("/Troubleshooting/", href)).path
    return path.removesuffix(".html")


class ScraperWiki(ScraperGeneric):
    """Scraper for WIKI namespace pages and troubleshooting indexes.

    This covers the ``/Wiki/<slug>`` pages, the
    ``/Troubleshooting/<category>/<title>/<id>`` problem pages and the
    ``/Troubleshooting/<category>`` index pages referenced by category
    ``related_wikis`` entries and by links inside rendered wiki content.
    """

    def __init__(self, context: Context) -> None:
        super().__init__(context)

    def setup(self) -> None:
        self.wiki_template = self.env.get_template("wiki.html")
        self.troubleshooting_template = self.env.get_template("troubleshooting.html")

    def get_items_name(self) -> str:
        return "wiki"

    def _build_wiki_path(self, url_or_path: str) -> str:
        """Local path for a wiki URL, e.g. ``Wiki/<slug>``,
        ``Troubleshooting/<category>`` or
        ``Troubleshooting/<category>/<title>/<id>``."""
        path = urllib.parse.unquote(urllib.parse.urlparse(url_or_path).path)
        parts = path.lstrip("/").split("/")
        if parts and parts[0].lower() == "wiki":
            parts[0] = "Wiki"
        elif parts and parts[0].lower() == "troubleshooting":
            parts[0] = "Troubleshooting"
            parts = [part.replace(" ", "+") for part in parts]
        return "/".join(parts)

    @staticmethod
    def _is_troubleshooting_index(item_key: str) -> bool:
        parts = item_key.split("/")
        return (
            len(parts) == TROUBLESHOOTING_INDEX_PATH_PARTS
            and parts[0] == "Troubleshooting"
        )

    def _add_wiki_to_scrape(self, wiki_path: str, wiki_url: str) -> None:
        self.add_item_to_scrape(
            wiki_path,
            {
                "wiki_url": wiki_url,
            },
            is_expected=False,
            warn_unexpected=False,
        )

    def get_wiki_link_from_obj(self, wiki: dict[str, Any]) -> str:
        if "url" not in wiki or not wiki["url"]:
            raise UnexpectedDataKindExceptionError(
                f"Impossible to extract wiki URL from {wiki}"
            )
        wiki_url = wiki["url"]
        wiki_path = self._build_wiki_path(wiki_url)
        self._add_wiki_to_scrape(wiki_path, wiki_url)
        return urllib.parse.quote(wiki_path)

    def get_wiki_link_from_props(self, wiki_path: str) -> str:
        build_path = self._build_wiki_path(wiki_path)
        self._add_wiki_to_scrape(build_path, wiki_path)
        return urllib.parse.quote(build_path)

    def build_expected_items(self) -> None:
        # Wikis are discovered while processing categories, guides and other wikis
        return

    def _get_wiki_endpoint(self, wiki_path: str) -> str:
        parts = wiki_path.split("/")
        if parts[0] == "Troubleshooting" and parts[-1].isdigit():
            return f"/wikis/{parts[-1]}"
        slug = wiki_path.split("/", 1)[1]
        return f"/wikis/WIKI/{slug}"

    def _get_wiki_content(self, endpoint: str) -> dict[str, Any] | None:
        content = self.client.get_api_content(
            endpoint, langid=self.configuration.lang_code
        )
        if content and content.get("revisionid", 0) > 0:
            return content

        logger.warning("Falling back to wiki in EN")
        content = self.client.get_api_content(endpoint, langid="en")
        if content and content.get("revisionid", 0) > 0:
            return content

        for lang in URLS:
            logger.warning(f"Falling back to wiki in {lang}")
            content = self.client.get_api_content(endpoint, langid=lang)
            if content and content.get("revisionid", 0) > 0:
                return content

        return None

    def _extract_toc(self, content: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(content, "lxml")
        toc: list[dict[str, Any]] = []
        for heading in soup.find_all(["h2", "h3"]):
            heading_id = heading.get("id")
            if not heading_id or not isinstance(heading_id, str):
                continue
            item: dict[str, Any] = {
                "id": heading_id,
                "text": heading.get_text(" ", strip=True),
                "children": [],
            }
            if heading.name == "h2" or not toc:
                toc.append(item)
            else:
                toc[-1]["children"].append(item)
        return toc

    def _extract_troubleshooting_sections(self, soup: Any) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_problem(
            target: list[dict[str, str | None]],
            link_href: str,
            title: str,
            summary: str,
            image_url: str | None,
            badge: str,
            device_title: str,
            device_image_url: str | None,
        ) -> None:
            link_href = _normalize_problem_href(link_href)
            match = TROUBLESHOOTING_PROBLEM_RE.match(link_href)
            if not match:
                return
            wikiid = match.group("wikiid")
            if wikiid in seen:
                return
            seen.add(wikiid)
            if image_url:
                image_url = urllib.parse.urljoin(
                    self.configuration.main_url.geturl(), image_url
                )
            if device_image_url:
                device_image_url = urllib.parse.urljoin(
                    self.configuration.main_url.geturl(), device_image_url
                )
            target.append(
                {
                    "title": title,
                    "summary": summary,
                    "link": self.get_wiki_link_from_props(wiki_path=link_href),
                    "image_url": image_url,
                    "badge": badge,
                    "device_title": device_title,
                    "device_image_url": device_image_url,
                }
            )

        def append_section(
            title: str | None, problems: list[dict[str, str | None]]
        ) -> None:
            if not problems:
                return
            if title is None and sections and sections[-1]["title"] is None:
                sections[-1]["problems"].extend(problems)
            else:
                sections.append({"title": title, "problems": problems})

        # An index can contain several lists: device-specific problems first,
        # then related problems from a parent category (e.g. iPhone 11 then
        # generic iPhone problems). The preceding h2, when present, is the
        # section title (e.g. "Related Apple iPhone Problems"). Trailing
        # headings such as "Didn't see your problem?" appear after the list
        # and are therefore never attached to a section.
        current_title: str | None = None
        for element in soup.find_all(["h2", "div"]):
            if element.name == "h2":
                current_title = element.get_text(" ", strip=True) or None
                continue
            if "problem-list" not in (element.get("class") or []):
                continue

            section_problems: list[dict[str, str | None]] = []
            for card in element.find_all("div", recursive=False):
                link = card.find("a", href=True)
                if link is None:
                    continue
                title_tag = card.find(["h3", "h4"])
                summary_tag = card.find("p")
                images = card.find_all("img")
                image_tag = images[0] if images else None
                device_image_tag = images[1] if len(images) > 1 else None
                badges_tag = card.select_one(".badges")
                device_tag = card.select_one(".device")
                add_problem(
                    section_problems,
                    link["href"],
                    (
                        title_tag.get_text(" ", strip=True)
                        if title_tag
                        else link.get_text(" ", strip=True)
                    ),
                    (summary_tag.get_text(" ", strip=True) if summary_tag else ""),
                    image_tag["src"] if image_tag and image_tag.get("src") else None,
                    (badges_tag.get_text(" ", strip=True) if badges_tag else ""),
                    (device_tag.get_text(" ", strip=True) if device_tag else ""),
                    (
                        device_image_tag["src"]
                        if device_image_tag and device_image_tag.get("src")
                        else None
                    ),
                )
            append_section(current_title, section_problems)
            current_title = None

        if sections:
            return sections

        # Fallback for a changed layout: collect every problem link on the page
        fallback_problems: list[dict[str, str | None]] = []
        for link in soup.find_all("a", href=True):
            href = _normalize_problem_href(link["href"])
            if not TROUBLESHOOTING_PROBLEM_RE.match(href):
                continue
            title_tag = link.find(["h3", "h4"])
            summary_tag = link.find_next("p")
            add_problem(
                fallback_problems,
                href,
                (
                    title_tag.get_text(" ", strip=True)
                    if title_tag
                    else link.get_text(" ", strip=True)
                ),
                (summary_tag.get_text(" ", strip=True) if summary_tag else ""),
                None,
                "",
                "",
                None,
            )
        append_section(None, fallback_problems)
        return sections

    def _get_troubleshooting_index_content(self, item_key: str) -> Any:
        category = item_key.split("/", 1)[1]
        try:
            soup, _ = self.client.get_soup(f"/Troubleshooting/{category}")
        except Exception as exc:
            logger.warning(
                f"Unable to fetch troubleshooting index for {category}: {exc}"
            )
            return None

        sections = self._extract_troubleshooting_sections(soup)
        problems: list[dict[str, str | None]] = [
            problem for section in sections for problem in section["problems"]
        ]
        if not problems:
            logger.warning(f"No troubleshooting problems found for {category}")
            return None

        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else f"{category} Troubleshooting"
        description = ""
        if h1 is not None:
            description_tag = h1.find_next("p")
            if description_tag is not None:
                description = description_tag.get_text(" ", strip=True)

        return {
            "title": title,
            "description": description,
            "problems": problems,
            "sections": sections,
        }

    def get_one_item_content(
        self,
        item_key: str,
        item_data: dict[str, Any],  # noqa: ARG002
    ) -> Any:
        if self._is_troubleshooting_index(item_key):
            return self._get_troubleshooting_index_content(item_key)

        endpoint = self._get_wiki_endpoint(item_key)
        content = self._get_wiki_content(endpoint)
        if content is None:
            logger.warning(f"Impossible to get wiki content: {item_key}")
        return content

    def add_item_redirect(
        self,
        item_key: str,
        item_data: dict[str, Any],  # noqa: ARG002
        redirect_kind: str,
    ) -> None:
        self.processor.add_redirect(
            path=item_key,
            target_path=(
                f"home/{redirect_kind}?{urllib.parse.urlencode({'url': item_key})}"
            ),
        )

    def process_one_item(
        self,
        item_key: str,
        item_data: dict[str, Any],  # noqa: ARG002
        item_content: Any,
    ) -> None:
        rel_prefix = "../" * item_key.count("/")

        if self._is_troubleshooting_index(item_key):
            rendered = self.troubleshooting_template.render(
                troubleshooter=item_content,
                metadata=self.metadata,
                lang=self.configuration.lang_code,
                rel_prefix=rel_prefix,
            )
            title = item_content["title"]
        else:
            headline = (
                item_content.get("page_title")
                or item_content.get("display_title")
                or item_content["title"]
            )
            toc = self._extract_toc(item_content.get("contents_rendered") or "")
            rendered = self.wiki_template.render(
                wiki=item_content,
                metadata=self.metadata,
                lang=self.configuration.lang_code,
                rel_prefix=rel_prefix,
                headline=headline,
                toc=toc,
                label=CATEGORY_LABELS[self.configuration.lang_code],
            )
            title = item_content["display_title"]

        self.processor.add_html_item(
            path=item_key,
            title=title,
            content=rendered,
        )

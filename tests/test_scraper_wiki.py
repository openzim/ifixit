from types import SimpleNamespace
from typing import Any, cast
from urllib.parse import unquote, urlparse

import pytest
from bs4 import BeautifulSoup

from ifixit2zim.scraper_wiki import (
    ScraperWiki,
    _normalize_problem_href,  # pyright: ignore[reportPrivateUsage]
)

PROBLEM_LISTS_HTML = """
<html>
  <body>
    <h1>iPhone 11 Troubleshooting: Fix Common Problems</h1>
    <p>Find out what's wrong with your iPhone 11 and how to fix it.</p>

    <div class="problem-list">
      <div>
        <a href="/Troubleshooting/iPhone_11/Will+Not+Turn+On/478192">
          <h4>Will Not Turn On</h4>
        </a>
        <p>Device-specific summary.</p>
        <img src="https://guide-images.cdn.ifixit.com/igi/upTu5NUX2V2yOlrD.standard" />
        <div class="badges"><span>Power</span></div>
        <div class="device">iPhone 11</div>
      </div>
    </div>

    <h2>Related Apple iPhone Problems</h2>
    <div class="problem-list">
      <div>
        <a href="iPhone/Lines+on+Screen/480100.html">
          <h3>Lines on Screen</h3>
        </a>
        <p>Generic summary.</p>
        <img src="https://guide-images.cdn.ifixit.com/igi/GPYmrAMg5g3WHrZf.standard" />
        <div class="badges"><span>Screen</span></div>
        <div class="device">Apple iPhone</div>
      </div>
    </div>

    <h2>Didn't see your problem? The iFixit Community has answers.</h2>
  </body>
</html>
"""


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        (
            "/Troubleshooting/iPhone_11/Will+Not+Turn+On/478192",
            "/Troubleshooting/iPhone_11/Will+Not+Turn+On/478192",
        ),
        (
            (
                "https://www.ifixit.com/Troubleshooting/iPhone/Lines+on+Screen/480100"
                "?foo=bar#section"
            ),
            "/Troubleshooting/iPhone/Lines+on+Screen/480100",
        ),
        (
            "iPhone/Battery+Draining+Fast/480045.html",
            "/Troubleshooting/iPhone/Battery+Draining+Fast/480045",
        ),
        (
            "./Troubleshooting/iPhone_11/Black+Screen/513737",
            "/Troubleshooting/iPhone_11/Black+Screen/513737",
        ),
        (
            "Troubleshooting/iPhone_11/Will+Not+Turn+On/478192",
            "/Troubleshooting/iPhone_11/Will+Not+Turn+On/478192",
        ),
        (
            "../Troubleshooting/iPhone_11/Will+Not+Turn+On/478192.html",
            "/Troubleshooting/iPhone_11/Will+Not+Turn+On/478192",
        ),
        (
            "iPhone/Lines%2bon%2bScreen/480100.html",
            "/Troubleshooting/iPhone/Lines%2bon%2bScreen/480100",
        ),
    ],
)
def test_normalize_problem_href(href: str, expected: str) -> None:
    assert _normalize_problem_href(href) == expected


def _make_scraper(soup: BeautifulSoup) -> ScraperWiki:
    configuration = SimpleNamespace(main_url=urlparse("https://www.ifixit.com"))

    def fake_get_soup(path: str) -> tuple[Any, list[str]]:
        return soup, [path]

    context = SimpleNamespace(
        configuration=configuration,
        client=SimpleNamespace(get_soup=fake_get_soup),
    )
    return ScraperWiki(cast(Any, context))


def test_troubleshooting_index_extracts_sections_and_all_problem_lists():
    soup = BeautifulSoup(PROBLEM_LISTS_HTML, "lxml")
    scraper = _make_scraper(soup)

    content = scraper.get_one_item_content("Troubleshooting/iPhone_11", {})

    assert content is not None
    assert content["description"] == (
        "Find out what's wrong with your iPhone 11 and how to fix it."
    )

    assert [unquote(problem["link"]) for problem in content["problems"]] == [
        "Troubleshooting/iPhone_11/Will+Not+Turn+On/478192",
        "Troubleshooting/iPhone/Lines+on+Screen/480100",
    ]
    assert content["problems"][0]["title"] == "Will Not Turn On"
    assert content["problems"][0]["badge"] == "Power"
    assert content["problems"][0]["device_title"] == "iPhone 11"
    assert content["problems"][1]["title"] == "Lines on Screen"
    assert content["problems"][1]["device_title"] == "Apple iPhone"

    assert [
        (section["title"], len(section["problems"])) for section in content["sections"]
    ] == [
        (None, 1),
        ("Related Apple iPhone Problems", 1),
    ]

    queued_keys: set[str] = set()
    while not scraper.items_queue.empty():
        queued_keys.add(scraper.items_queue.get_nowait()["key"])

    assert queued_keys == {
        "Troubleshooting/iPhone_11/Will+Not+Turn+On/478192",
        "Troubleshooting/iPhone/Lines+on+Screen/480100",
    }

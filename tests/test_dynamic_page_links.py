import threading
from types import SimpleNamespace
from typing import Any, cast
from urllib.parse import urlparse

import pytest

from ifixit2zim.processor import Processor
from ifixit2zim.utils import append_fragment_to_link, build_dynamic_page_link


@pytest.mark.parametrize(
    ("kind", "value", "expected"),
    [
        (
            "unavailable_offline",
            "https://www.ifixit.com/Store/iPhone",
            (
                "home/unavailable_offline"
                "#url=https%3A%2F%2Fwww.ifixit.com%2FStore%2FiPhone"
            ),
        ),
        (
            "external_content",
            "https://example.com/a?b=c#d",
            "home/external_content#url=https%3A%2F%2Fexample.com%2Fa%3Fb%3Dc%23d",
        ),
        (
            "not_scrapped",
            "/Guide/Foo Bar",
            "home/not_scrapped#url=%2FGuide%2FFoo%20Bar",
        ),
    ],
)
def test_build_dynamic_page_link(kind: str, value: str, expected: str) -> None:
    assert build_dynamic_page_link(kind, value) == expected


def test_build_dynamic_page_link_with_rel_prefix() -> None:
    assert build_dynamic_page_link("missing", "Item/Foo", "../") == (
        "../home/missing#url=Item%2FFoo"
    )


@pytest.mark.parametrize(
    ("link", "fragment", "expected"),
    [
        (
            "home/external_content#url=https%3A%2F%2Fexample.com%2Ffoo",
            "section one",
            "home/external_content#url=https%3A%2F%2Fexample.com%2Ffoo%23section%20one",
        ),
        ("../Guide/Foo", "section", "../Guide/Foo#section"),
        ("../Guide/Foo", "", "../Guide/Foo"),
    ],
)
def test_append_fragment_to_link(link: str, fragment: str, expected: str) -> None:
    assert append_fragment_to_link(link, fragment) == expected


def _make_processor() -> Processor:
    configuration = cast(
        Any, SimpleNamespace(main_url=urlparse("https://www.ifixit.com"))
    )
    return Processor(
        lock=threading.Lock(),
        configuration=configuration,
        creator=cast(Any, SimpleNamespace()),
        imager=cast(Any, SimpleNamespace()),
    )


def test_external_link_keeps_fragment_in_magic_anchor() -> None:
    processor = _make_processor()
    assert processor._process_href_regex(  # pyright: ignore[reportPrivateUsage]
        "https://example.com/foo#section", "../"
    ) == ("../home/external_content#url=https%3A%2F%2Fexample.com%2Ffoo%23section")


def test_kind_link_keeps_fragment_in_magic_anchor() -> None:
    processor = _make_processor()
    processor.final_hrefs["https://www.ifixit.com/Store/Foo"] = "/Store/Foo"
    assert processor._process_href_regex(  # pyright: ignore[reportPrivateUsage]
        "/Store/Foo#section", "../"
    ) == ("../home/unavailable_offline#url=%2FStore%2FFoo%23section")

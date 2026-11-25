from pathlib import Path

import pytest
from zimscraperlib.zim import Archive


def test_is_file(zim_file_path: Path):
    """Ensure ZIM file exists"""
    assert zim_file_path.exists()
    assert zim_file_path.is_file()


def test_zim_main_page(zim_fh: Archive):
    """Ensure main page redirects to the home page"""

    main_entry = zim_fh.main_entry
    assert main_entry.is_redirect
    main_page = main_entry.get_redirect_entry()
    assert main_page.path == "Main-Page"
    assert main_page.is_redirect
    assert main_page.get_redirect_entry().path == "home/home"


def test_zim_metadata(zim_fh: Archive):
    """Ensure ZIM metadata are present and correct"""

    assert zim_fh.get_text_metadata("Name") == "ifixit_en_test"
    assert zim_fh.get_text_metadata("Title") == "iFixit Test"
    assert zim_fh.get_text_metadata("Description") == "Test ZIM for iFixit"
    assert zim_fh.get_text_metadata("Language") == "eng"
    assert zim_fh.get_text_metadata("Publisher") == "openZIM"
    assert zim_fh.get_text_metadata("Creator") == "iFixit"


def test_zim_tags(zim_fh: Archive):
    """Ensure expected tags are present"""

    tags = zim_fh.get_text_metadata("Tags").split(";")
    for expected_tag in ["iFixit", "_category:iFixit"]:
        assert expected_tag in tags


def test_zim_illustration(zim_fh: Archive):
    """Ensure the 48x48 illustration is a PNG image"""

    illustration = zim_fh.get_metadata("Illustration_48x48@1")
    assert illustration.startswith(b"\x89PNG")


@pytest.mark.parametrize(
    "item_path",
    [
        pytest.param("home/home", id="home"),
        pytest.param("home/error", id="error"),
        pytest.param("home/missing", id="missing"),
        pytest.param("home/not_scrapped", id="not_scrapped"),
        pytest.param("home/not_yet_available", id="not_yet_available"),
        pytest.param("home/unavailable_offline", id="unavailable_offline"),
        pytest.param("home/external_content", id="external_content"),
        pytest.param("about-us", id="about-us"),
    ],
)
def test_zim_content_static_pages(zim_fh: Archive, item_path: str):
    """Ensure static pages are present"""

    item = zim_fh.get_item(item_path)
    assert item.mimetype == "text/html"
    assert len(item.content) > 0


@pytest.mark.parametrize(
    "item_path,expected_mimetype",
    [
        pytest.param("assets/customZimHelpers-1.js", "text/javascript", id="js"),
        pytest.param("assets/footer.css", "text/css", id="css"),
        pytest.param("assets/NoImage_300x225.jpg", "image/jpeg", id="no-image"),
    ],
)
def test_zim_content_assets(zim_fh: Archive, item_path: str, expected_mimetype: str):
    """Ensure bundled assets are present"""

    item = zim_fh.get_item(item_path)
    assert item.mimetype == expected_mimetype
    assert len(item.content) > 0


def _entry_paths(zim_fh: Archive) -> list[str]:
    return [
        zim_fh.get_entry_by_id(entry_id).path for entry_id in range(zim_fh.entry_count)
    ]


@pytest.mark.parametrize("prefix", ["Device/", "Guide/", "Info/", "User/", "Wiki/"])
def test_zim_content_scraped_pages(zim_fh: Archive, prefix: str):
    """Ensure at least one page of each scraped type is present"""

    paths = [path for path in _entry_paths(zim_fh) if path.startswith(prefix)]
    assert paths
    item = zim_fh.get_item(paths[0])
    assert item.mimetype == "text/html"
    assert len(item.content) > 0


def test_zim_content_images(zim_fh: Archive):
    """Ensure images have been added"""

    assert any(path.startswith("images/") for path in _entry_paths(zim_fh))

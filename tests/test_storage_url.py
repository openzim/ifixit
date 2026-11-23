import pytest

from ifixit2zim.utils import get_storage_url


def test_get_storage_url_rewrites_s3_https_scheme():
    url = (
        "s3+https://s3.us-west-1.wasabisys.com"
        "?bucketname=bucket&keyid=key&secretaccesskey=secret"
    )
    assert get_storage_url(url) == (
        "https://s3.us-west-1.wasabisys.com"
        "?bucketname=bucket&keyid=key&secretaccesskey=secret"
    )


def test_get_storage_url_rewrites_s3_http_scheme():
    assert get_storage_url("s3+http://localhost:9000") == "http://localhost:9000"


def test_get_storage_url_keeps_plain_https_url():
    url = "https://user:pass@s3.example.com/path?bucketname=b"
    assert get_storage_url(url) == url


def test_get_storage_url_rejects_unsupported_scheme():
    with pytest.raises(ValueError):
        get_storage_url("ftp://example.com")

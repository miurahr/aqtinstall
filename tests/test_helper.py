import binascii
import os
import re
from typing import Dict
from urllib.parse import urlparse

import pytest
import requests
from requests.models import Response

from aqt import helper
from aqt.exceptions import ArchiveChecksumError, ArchiveConnectionError, ArchiveDownloadError, ChecksumDownloadFailure
from aqt.helper import Settings, get_hash, getUrl, retry_on_errors
from aqt.metadata import Version


@pytest.fixture(autouse=True)
def load_default_settings(use_defaults: bool = True):
    """For each test, first load the default settings file, unless marked otherwise"""
    if use_defaults:
        helper.Settings.load_settings()


def test_helper_altlink(monkeypatch):
    class Message:
        headers = {"content-type": "text/plain", "length": 300}
        text = """<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
  <generator>MirrorBrain/2.17.0</generator>
  <origin dynamic="true">http://download.example.io/boo.7z.meta4</origin>
  <published>2020-03-04T01:11:48Z</published>
  <publisher>
    <name>Example Project</name>
    <url>https://download.example.io</url>
  </publisher>

  <file name="boo.7z">
    <size>651</size>
    <hash type="md5">d49eba3937fb063caa48769e8f28377c</hash>
    <hash type="sha-1">25d3a33d00c1e5880679a17fd4b8b831134cfa6f</hash>
    <hash type="sha-256">37e50248cf061109e2cb92105cd2c36a6e271701d6d4a72c4e73c6d82aad790a</hash>
    <pieces length="262144" type="sha-1">
      <hash>bec628a149ed24a3a9b83747776ecca5a1fad11c</hash>
      <hash>98b1dee3f741de51167a9428b0560cd2d1f4d945</hash>
      <hash>8717a0cb3d14c1958de5981635c9b90b146da165</hash>
      <hash>78cd2ae3ae37ca7c080a56a2b34eb33ec44a9ef1</hash>
    </pieces>
    <url location="cn" priority="1">http://mirrors.geekpie.club/boo.7z</url>
    <url location="jp" priority="2">http://ftp.jaist.ac.jp/pub/boo.7z</url>
    <url location="jp" priority="3">http://ftp.yz.yamagata-u.ac.jp/pub/boo.7z</url>
  </file>
</metalink>
"""

    def mock_return(url):
        return Message()

    monkeypatch.setattr(helper, "_get_meta", mock_return)

    url = "http://foo.baz/qtproject/boo.7z"
    alt = "http://mirrors.geekpie.club/boo.7z"
    newurl = helper.altlink(url, alt)
    assert newurl.startswith("http://ftp.jaist.ac.jp/")


def test_helper_altlink_black(monkeypatch):
    class Message:
        headers = {"content-type": "text/plain", "length": 300}
        text = """<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
  <generator>MirrorBrain/2.17.0</generator>
  <origin dynamic="true">http://download.example.io/boo.7z.meta4</origin>
  <published>2020-03-04T01:11:48Z</published>
  <publisher>
    <name>Example Project</name>
    <url>https://download.example.io</url>
  </publisher>

  <file name="boo.7z">
    <size>651</size>
    <hash type="md5">d49eba3937fb063caa48769e8f28377c</hash>
    <hash type="sha-1">25d3a33d00c1e5880679a17fd4b8b831134cfa6f</hash>
    <hash type="sha-256">37e50248cf061109e2cb92105cd2c36a6e271701d6d4a72c4e73c6d82aad790a</hash>
    <pieces length="262144" type="sha-1">
      <hash>bec628a149ed24a3a9b83747776ecca5a1fad11c</hash>
      <hash>98b1dee3f741de51167a9428b0560cd2d1f4d945</hash>
      <hash>8717a0cb3d14c1958de5981635c9b90b146da165</hash>
      <hash>78cd2ae3ae37ca7c080a56a2b34eb33ec44a9ef1</hash>
    </pieces>
    <url location="cn" priority="1">http://mirrors.geekpie.club/boo.7z</url>
  </file>
</metalink>
"""

    def mock_return(url):
        return Message()

    monkeypatch.setattr(helper, "_get_meta", mock_return)

    url = "http://foo.baz/qtproject/boo.7z"
    alt = "http://ftp.yz.yamagata-u.ac.jp/pub/boo.7z"
    newurl = helper.altlink(url, alt)
    assert newurl.startswith("http://ftp.yz.yamagata-u.ac.jp/pub/boo.7z")


@pytest.mark.load_default_settings(False)
def test_settings(tmp_path):
    helper.Settings.load_settings(os.path.join(os.path.dirname(__file__), "data", "settings.ini"))
    assert helper.Settings.concurrency == 3
    assert "http://mirror.example.com" in helper.Settings.blacklist


def mocked_iter_content(chunk_size):
    with open(os.path.join(os.path.dirname(__file__), "data", "windows-5150-update.xml"), "rb") as f:
        data = f.read(chunk_size)
        while len(data) > 0:
            yield data
            data = f.read(chunk_size)
        return b""


def mocked_requests_get(*args, **kwargs):
    response = Response()
    response.status_code = 200
    response.iter_content = mocked_iter_content
    return response


def test_helper_downloadBinary_md5(tmp_path, monkeypatch):
    monkeypatch.setattr(requests.Session, "get", mocked_requests_get)

    expected = binascii.unhexlify("1d41a93e4a585bb01e4518d4af431933")
    out = tmp_path.joinpath("text.xml")
    helper.downloadBinaryFile("http://example.com/test.xml", out, "md5", expected, 60)


def test_helper_downloadBinary_sha256(tmp_path, monkeypatch):
    monkeypatch.setattr(requests.Session, "get", mocked_requests_get)

    expected = binascii.unhexlify("07b3ef4606b712923a14816b1cfe9649687e617d030fc50f948920d784c0b1cd")
    out = tmp_path.joinpath("text.xml")
    helper.downloadBinaryFile("http://example.com/test.xml", out, "sha256", expected, 60)


@pytest.mark.parametrize(
    "mock_exception, expected_err_msg",
    (
        (requests.exceptions.ConnectionError("Connection failed!"), "Connection error: ('Connection failed!',)"),
        (requests.exceptions.Timeout("Connection timed out!"), "Connection timeout: ('Connection timed out!',)"),
    ),
)
def test_helper_downloadBinary_connection_err(tmp_path, monkeypatch, mock_exception, expected_err_msg):
    def _mock_get_conn_error(*args, **kwargs):
        raise mock_exception

    monkeypatch.setattr(requests.Session, "get", _mock_get_conn_error)

    expected = binascii.unhexlify("1d41a93e4a585bb01e4518d4af431933")
    out = tmp_path.joinpath("text.xml")
    with pytest.raises(ArchiveConnectionError) as e:
        helper.downloadBinaryFile("http://example.com/test.xml", out, "md5", expected, 60)
    assert e.type == ArchiveConnectionError
    assert format(e.value) == expected_err_msg


def test_helper_downloadBinary_wrong_checksum(tmp_path, monkeypatch):
    monkeypatch.setattr(requests.Session, "get", mocked_requests_get)

    actual_hash = binascii.unhexlify("1d41a93e4a585bb01e4518d4af431933")
    wrong_hash = binascii.unhexlify("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    out = tmp_path.joinpath("test.xml")
    url = "http://example.com/test.xml"
    expected_err = (
        f"Downloaded file test.xml is corrupted! Detect checksum error."
        f"\nExpect {wrong_hash.hex()}: {url}"
        f"\nActual {actual_hash.hex()}: {out.name}"
    )
    with pytest.raises(ArchiveChecksumError) as e:
        helper.downloadBinaryFile(url, out, "md5", wrong_hash, 60)
    assert e.type == ArchiveChecksumError
    assert format(e.value) == expected_err


def test_helper_downloadBinary_response_error_undefined(tmp_path, monkeypatch):
    contained_error_msg = "This chunk of downloaded content contains an error."

    def iter_broken_content(*args, **kwargs):
        raise RuntimeError(contained_error_msg)

    def mock_requests_get(*args, **kwargs):
        response = Response()
        response.status_code = 200
        response.iter_content = iter_broken_content
        return response

    monkeypatch.setattr(requests.Session, "get", mock_requests_get)

    expected = binascii.unhexlify("1d41a93e4a585bb01e4518d4af431933")
    out = tmp_path.joinpath("text.xml")
    with pytest.raises(ArchiveDownloadError) as e:
        helper.downloadBinaryFile("http://example.com/test.xml", out, "md5", expected, 60)
    assert e.type == ArchiveDownloadError
    assert format(e.value) == f"Download of test.xml has error: {contained_error_msg}"


@pytest.mark.parametrize(
    "num_attempts_before_success, num_retries_allowed",
    (
        (2, 5),
        (5, 5),
        (5, 2),
    ),
)
def test_helper_retry_on_error(num_attempts_before_success, num_retries_allowed):
    enclosed = {"call_count": 0}

    def action():
        enclosed["call_count"] += 1
        more_attempts_needed = num_attempts_before_success - enclosed["call_count"]
        if more_attempts_needed <= 0:
            return True
        raise RuntimeError(f"Must retry {more_attempts_needed} more times before success")

    if num_attempts_before_success > num_retries_allowed:
        with pytest.raises(RuntimeError) as e:
            retry_on_errors(action, (RuntimeError,), num_retries_allowed, "do something")
        assert e.type == RuntimeError
    else:
        assert retry_on_errors(action, (RuntimeError,), num_retries_allowed, "do something")


@pytest.mark.parametrize(
    "num_tries_required, num_retries_allowed",
    (
        (2, 5),
        (5, 5),
        (6, 5),
    ),
)
def test_helper_get_hash_retries(monkeypatch, num_tries_required, num_retries_allowed):
    num_tries = 0
    expected_hash = "a" * 64
    rest_of_url = "online/qtsdkrepository/some/path/to/archive.7z"

    def mock_getUrl(url, *args, **kwargs):
        nonlocal num_tries
        num_tries += 1
        if num_tries < num_tries_required:
            raise ArchiveConnectionError(f"Must retry {num_tries_required - num_tries} more times before success")
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        assert base in Settings.trusted_mirrors
        # Check that the url was composed properly
        assert url[len(base) :] == f"/{rest_of_url}.sha256"

        hash_filename = str(parsed.path.split("/")[-1])
        assert hash_filename == "archive.7z.sha256"
        return f"{expected_hash} archive.7z"

    monkeypatch.setattr("aqt.helper.getUrl", mock_getUrl)

    if num_tries_required > num_retries_allowed:
        with pytest.raises(ChecksumDownloadFailure) as e:
            get_hash(rest_of_url, "sha256", (5, 5))
        assert e.type == ChecksumDownloadFailure
    else:
        result = get_hash(rest_of_url, "sha256", (5, 5))
        assert result == binascii.unhexlify(expected_hash)


@pytest.mark.parametrize(
    "received_hash",
    (
        "",  # Empty
        "a" * 40,  # Hash length for sha1 checksums
        "q" * 64,  # Not a hex digit; you can't unhexlify this
    ),
)
def test_helper_get_hash_bad_hash(monkeypatch, received_hash):
    def mock_getUrl(url, *args, **kwargs):
        hash_filename = str(urlparse(url).path.split("/")[-1])
        assert hash_filename.endswith(".sha256")
        filename = hash_filename[: -len(".sha256")]
        return f"{received_hash} {filename}"

    monkeypatch.setattr("aqt.helper.getUrl", mock_getUrl)

    with pytest.raises(ChecksumDownloadFailure) as e:
        get_hash("online/qtsdkrepository/some/path/to/archive.7z", "sha256", (5, 5))
    assert e.type == ChecksumDownloadFailure


@pytest.mark.parametrize(
    "version, expect",
    [
        ("1.33.1", Version(major=1, minor=33, patch=1)),
        (
            "1.33.1-202102101246",
            Version(major=1, minor=33, patch=1, build=("202102101246",)),
        ),
        (
            "1.33-202102101246",
            Version(major=1, minor=33, patch=0, build=("202102101246",)),
        ),
        ("2020-05-19-1", Version(major=2020, minor=0, patch=0, build=("05-19-1",))),
    ],
)
def test_helper_to_version_permissive(version, expect):
    assert Version.permissive(version) == expect


def mocked_request_response_class(num_redirects: int = 0, forbidden_baseurls=None):
    if not forbidden_baseurls:
        forbidden_hostnames = []
    else:
        forbidden_hostnames = [urlparse(host).hostname for host in forbidden_baseurls]

    class MockResponse:
        redirects_for_host = {}

        def __init__(self, url: str, headers: Dict, text: str):
            self.url = url
            self.headers = {key: value for key, value in headers.items()}

            hostname = urlparse(url).hostname
            if hostname not in MockResponse.redirects_for_host:
                MockResponse.redirects_for_host[hostname] = num_redirects

            if MockResponse.redirects_for_host[hostname] > 0:
                MockResponse.redirects_for_host[hostname] -= 1
                self.status_code = 302
                self.headers["Location"] = f"{url}/redirect{MockResponse.redirects_for_host[hostname]}"
                self.text = f"Still {MockResponse.redirects_for_host[hostname]} redirects to go..."
                self.reason = "Redirect"
            elif hostname in forbidden_hostnames:
                raise requests.exceptions.ConnectionError()
            else:
                self.status_code = 200
                self.text = text

    return MockResponse


def mock_get_redirect(num_redirects: int):
    response_class = mocked_request_response_class(num_redirects)

    def _mock(url: str, timeout=None, allow_redirects=None):
        return response_class(url, {}, text="some_html_content")

    def _mock_session(self, url: str, allow_redirects=None, timeout=None, stream=None):
        return response_class(url, {}, text="some_html_content")

    return _mock, _mock_session


def test_helper_getUrl_ok(monkeypatch):
    mocked_get, mocked_session_get = mock_get_redirect(0)
    monkeypatch.setattr(requests, "get", mocked_get)
    monkeypatch.setattr(requests.Session, "get", mocked_session_get)
    assert getUrl("some_url", timeout=(5, 5)) == "some_html_content"


def test_helper_getUrl_redirect_5(monkeypatch):
    mocked_get, mocked_session_get = mock_get_redirect(num_redirects=5)
    monkeypatch.setattr(requests, "get", mocked_get)
    monkeypatch.setattr(requests.Session, "get", mocked_session_get)
    assert getUrl("some_url", (5, 5)) == "some_html_content"


def test_helper_getUrl_redirect_too_many(monkeypatch):
    mocked_get, mocked_session_get = mock_get_redirect(num_redirects=11)
    monkeypatch.setattr(requests, "get", mocked_get)
    monkeypatch.setattr(requests.Session, "get", mocked_session_get)
    with pytest.raises(ArchiveDownloadError) as e:
        getUrl("some_url", (5, 5))
    assert e.type == ArchiveDownloadError


def test_helper_getUrl_conn_error(monkeypatch):
    response_class = mocked_request_response_class(forbidden_baseurls=["https://www.forbidden.com"])
    url = "https://www.forbidden.com/some_path"
    timeout = (5, 5)

    expect_re = re.compile(r"^Failure to connect to.+" + re.escape(url))

    def _mock(url: str, *args, **kwargs):
        return response_class(url, {}, text="some_html_content")

    def _mock_session(self, url: str, *args, **kargs):
        return response_class(url, {}, text="some_html_content")

    monkeypatch.setattr(requests, "get", _mock)
    monkeypatch.setattr(requests.sessions.Session, "get", _mock_session)
    with pytest.raises(ArchiveConnectionError) as e:
        getUrl(url, timeout)
    assert e.type == ArchiveConnectionError
    assert expect_re.match(format(e.value))


def test_helper_getUrl_checksum_error(monkeypatch):
    mocked_get, mocked_session_get = mock_get_redirect(0)
    monkeypatch.setattr(requests, "get", mocked_get)
    monkeypatch.setattr(requests.Session, "get", mocked_session_get)
    with pytest.raises(ArchiveChecksumError) as e:
        getUrl("some_url", timeout=(5, 5), expected_hash=b"AAAAAAAAAAA")
    assert e.type == ArchiveChecksumError

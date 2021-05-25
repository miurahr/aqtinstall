import binascii
import logging
import os

import requests
from requests.models import Response

from aqt import helper


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


def test_settings(tmp_path):
    config = helper.Settings()
    assert config.concurrency == 3
    assert "http://mirror.example.com" in config.blacklist


def mocked_iter_content(chunk_size):
    with open(
        os.path.join(os.path.dirname(__file__), "data", "windows-5150-update.xml"), "rb"
    ) as f:
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
    logger = logging.getLogger(__file__)
    helper.downloadBinaryFile(
        "http://example.com/test.xml", out, "md5", expected, 60, logger
    )


def test_helper_downloadBinary_sha256(tmp_path, monkeypatch):

    monkeypatch.setattr(requests.Session, "get", mocked_requests_get)

    expected = binascii.unhexlify(
        "07b3ef4606b712923a14816b1cfe9649687e617d030fc50f948920d784c0b1cd"
    )
    out = tmp_path.joinpath("text.xml")
    logger = logging.getLogger(__file__)
    helper.downloadBinaryFile(
        "http://example.com/test.xml", out, "sha256", expected, 60, logger
    )

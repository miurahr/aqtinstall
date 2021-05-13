import re
from typing import Optional

import pytest
import json
from pathlib import Path

from aqt.archives import QtDownloadListFetcher
from aqt.helper import ArchiveId, get_packages_for_version

MINOR_REGEX = re.compile(r"^\d+\.(\d+)")


@pytest.mark.parametrize(
    "os_name,target,in_file,expect_out_file",
    [
        ("windows", "android", "windows-android.html", "windows-android-expect.json"),
        ("windows", "desktop", "windows-desktop.html", "windows-desktop-expect.json"),
        ("windows", "winrt", "windows-winrt.html", "windows-winrt-expect.json"),
        ("linux", "android", "linux-android.html", "linux-android-expect.json"),
        ("linux", "desktop", "linux-desktop.html", "linux-desktop-expect.json"),
        ("mac", "android", "mac-android.html", "mac-android-expect.json"),
        ("mac", "desktop", "mac-desktop.html", "mac-desktop-expect.json"),
        ("mac", "ios", "mac-ios.html", "mac-ios-expect.json"),
    ],
)
def test_list_folders(os_name, target, in_file, expect_out_file):
    _html = (Path(__file__).parent / "data" / in_file).read_text("utf-8")

    def html_fetcher(_: str) -> str:
        return _html

    expected = json.loads(
        (Path(__file__).parent / "data" / expect_out_file).read_text("utf-8")
    )

    archive_id = ArchiveId("tools", os_name, target)

    # Test 'aqt list tools'
    fetcher = QtDownloadListFetcher(archive_id, html_fetcher)
    out = fetcher.run()
    assert out.strip() == "\n".join(expected["tools"])

    for qt in ("qt5", "qt6"):
        archive_id.category = qt
        for extension, expected_output in expected[qt].items():
            archive_id.extension = extension if extension != "qt" else None
            fetcher = QtDownloadListFetcher(archive_id, html_fetcher)
            out = fetcher.run()

            if len(expected_output) == 0:
                assert not out
            else:
                assert out.strip() == "\n".join(expected_output)

            # Test filters
            out = QtDownloadListFetcher(archive_id, html_fetcher, is_latest=True).run()
            if len(expected_output) == 0:
                assert not out
            else:
                assert out.strip() == expected_output[-1].split(" ")[-1]

            for row in expected_output:
                minor = int(MINOR_REGEX.search(row).group(1))

                out = QtDownloadListFetcher(
                    archive_id, html_fetcher, is_latest=True, filter_minor=minor
                ).run()
                assert out.strip() == row.split(" ")[-1]

                out = QtDownloadListFetcher(
                    archive_id, html_fetcher, is_latest=False, filter_minor=minor
                ).run()
                assert out.strip() == row


@pytest.mark.parametrize(
    "version,extension,in_file,expect_out_file",
    [
        ("5.14.0", None, "windows-5140-update.xml", "windows-5140-expect.json"),
        ("5.15.0", None, "windows-5150-update.xml", "windows-5150-expect.json"),
        (
            "5.15.2",
            "src_doc_examples",
            "windows-5152-src-doc-example-update.xml",
            "windows-5152-src-doc-example-expect.json",
        ),
    ],
)
def test_list_archives(
    capsys, version: str, extension: Optional[str], in_file: str, expect_out_file: str
):
    archive_id = ArchiveId("qt", "windows", "desktop", extension)
    _xml = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
    expect = json.loads(
        (Path(__file__).parent / "data" / expect_out_file).read_text("utf-8")
    )

    def http_fetcher(_: str) -> str:
        return _xml

    packages = get_packages_for_version(version, archive_id, http_fetcher)
    assert packages == expect
    print(" ".join(packages))
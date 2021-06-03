import json
import re
from pathlib import Path

import pytest
from semantic_version import Version

from aqt import helper, installer
from aqt.archives import QtDownloadListFetcher
from aqt.helper import ArchiveId, get_modules_architectures_for_version

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
    fetcher = QtDownloadListFetcher(archive_id, html_fetcher=html_fetcher)
    out = fetcher.run()
    assert str(out) == "\n".join(expected["tools"])

    for qt in ("qt5", "qt6"):
        archive_id.category = qt
        for extension, expected_output in expected[qt].items():
            archive_id.extension = extension if extension != "qt" else ""
            fetcher = QtDownloadListFetcher(archive_id, html_fetcher=html_fetcher)
            out = fetcher.run()

            if len(expected_output) == 0:
                assert not out
            else:
                assert str(out) == "\n".join(expected_output)

            # Filter for the latest version only
            out = QtDownloadListFetcher(archive_id, html_fetcher=html_fetcher).run(
                is_latest=True
            )
            if len(expected_output) == 0:
                assert not out
            else:
                assert (
                    helper.Versions.stringify_ver(out)
                    == expected_output[-1].split(" ")[-1]
                )

            for row in expected_output:
                minor = int(MINOR_REGEX.search(row).group(1))

                # Find the latest version for a particular minor version
                out = QtDownloadListFetcher(
                    archive_id, html_fetcher=html_fetcher, filter_minor=minor
                ).run(is_latest=True)
                assert helper.Versions.stringify_ver(out) == row.split(" ")[-1]

                # Find all versions for a particular minor version
                out = QtDownloadListFetcher(
                    archive_id, html_fetcher=html_fetcher, filter_minor=minor
                ).run()
                assert str(out) == row


@pytest.mark.parametrize(
    "version,extension,in_file,expect_out_file",
    [
        ("5.14.0", "", "windows-5140-update.xml", "windows-5140-expect.json"),
        ("5.15.0", "", "windows-5150-update.xml", "windows-5150-expect.json"),
        (
            "5.15.2",
            "src_doc_examples",
            "windows-5152-src-doc-example-update.xml",
            "windows-5152-src-doc-example-expect.json",
        ),
    ],
)
def test_list_architectures_and_modules(
    capsys, version: str, extension: str, in_file: str, expect_out_file: str
):
    archive_id = ArchiveId("qt" + version[0], "windows", "desktop", extension)
    _xml = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
    expect = json.loads(
        (Path(__file__).parent / "data" / expect_out_file).read_text("utf-8")
    )

    def http_fetcher(_: str) -> str:
        return _xml

    modules, arches = get_modules_architectures_for_version(
        Version(version), archive_id, http_fetcher
    )
    print(" ".join(arches))
    assert modules == expect["modules"]
    assert arches == expect["architectures"]


@pytest.mark.parametrize(
    "cat, host, target, minor_ver, ver, ext, xmlfile, xmlexpect, htmlfile, htmlexpect",
    [
        (
            "qt5",
            "windows",
            "desktop",
            "14",
            "5.14.0",
            "wasm",
            "windows-5140-update.xml",
            "windows-5140-expect.json",
            "windows-desktop.html",
            "windows-desktop-expect.json",
        ),
    ],
)
def test_list_cli(
    capsys,
    monkeypatch,
    cat,
    host,
    target,
    minor_ver,
    ver,
    ext,
    xmlfile,
    xmlexpect,
    htmlfile,
    htmlexpect,
):
    def _mock(self, rest_of_url: str):
        in_file = xmlfile if rest_of_url.endswith("Updates.xml") else htmlfile
        text = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
        if not rest_of_url.endswith("Updates.xml"):
            return text

        # If we are serving an Updates.xml, `aqt list` will look for a Qt version number.
        # We will replace the version numbers in the file with the requested version.
        match = re.search(r"qt\d_(\d+)", rest_of_url)
        assert match
        desired_version = match.group(1)
        ver_to_replace = ver.replace(".", "")
        return text.replace(ver_to_replace, desired_version)

    monkeypatch.setattr(installer.Cli, "_default_http_fetcher", _mock)

    expected_modules_arches = json.loads(
        (Path(__file__).parent / "data" / xmlexpect).read_text("utf-8")
    )
    expect_modules = expected_modules_arches["modules"]
    expect_arches = expected_modules_arches["architectures"]

    def check_extensions():
        out, err = capsys.readouterr()
        # We should probably generate expected from htmlexpect, but this will work for now
        assert out.strip() == "wasm src_doc_examples"

    def check_modules():
        out, err = capsys.readouterr()
        assert set(out.strip().split()) == set(expect_modules)

    def check_arches():
        out, err = capsys.readouterr()
        assert set(out.strip().split()) == set(expect_arches)

    _minor = ["--filter-minor", minor_ver]
    _ext = ["--extension", ext]

    cli = installer.Cli()
    # Query extensions by latest version, minor version, and specific version
    cli.run(["list", cat, host, target, "--extensions", "latest"])
    check_extensions()
    cli.run(["list", cat, host, target, *_minor, "--extensions", "latest"])
    check_extensions()
    cli.run(["list", cat, host, target, "--extensions", ver])
    check_extensions()
    # Query modules by latest version, minor version, and specific version
    cli.run(["list", cat, host, target, "--modules", "latest"])
    check_modules()
    cli.run(["list", cat, host, target, *_minor, "--modules", "latest"])
    check_modules()
    cli.run(["list", cat, host, target, "--modules", ver])
    check_modules()
    cli.run(["list", cat, host, target, *_ext, "--modules", "latest"])
    check_modules()
    cli.run(["list", cat, host, target, *_ext, *_minor, "--modules", "latest"])
    check_modules()
    cli.run(["list", cat, host, target, *_ext, "--modules", ver])
    check_modules()
    # Query architectures by latest version, minor version, and specific version
    cli.run(["list", cat, host, target, "--arch", "latest"])
    check_arches()
    cli.run(["list", cat, host, target, *_minor, "--arch", "latest"])
    check_arches()
    cli.run(["list", cat, host, target, "--arch", ver])
    check_arches()
    cli.run(["list", cat, host, target, *_ext, "--arch", "latest"])
    check_arches()
    cli.run(["list", cat, host, target, *_ext, *_minor, "--arch", "latest"])
    check_arches()
    cli.run(["list", cat, host, target, *_ext, "--arch", ver])
    check_arches()

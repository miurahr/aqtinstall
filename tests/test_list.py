import json
import re
from pathlib import Path

import pytest
from semantic_version import Version

from aqt import archives, installer
from aqt.archives import ListCommand
from aqt.helper import ArchiveId

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
def test_list_versions_tools(monkeypatch, os_name, target, in_file, expect_out_file):
    _html = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
    monkeypatch.setattr(archives.ListCommand, "fetch_http", lambda self, _: _html)

    expected = json.loads(
        (Path(__file__).parent / "data" / expect_out_file).read_text("utf-8")
    )

    # Test 'aqt list tools'
    tools = ListCommand(ArchiveId("tools", os_name, target)).action()
    assert tools.pretty_print() == "\n".join(expected["tools"])

    for qt in ("qt5", "qt6"):
        for ext, expected_output in expected[qt].items():
            # Test 'aqt list qt'
            archive_id = ArchiveId(qt, os_name, target, ext if ext != "qt" else "")
            all_versions = ListCommand(archive_id).action()

            if len(expected_output) == 0:
                assert not all_versions
            else:
                assert all_versions.pretty_print() == "\n".join(expected_output)

            # Filter for the latest version only
            latest_ver = ListCommand(archive_id, is_latest_version=True).action()

            if len(expected_output) == 0:
                assert not latest_ver
            else:
                assert latest_ver.pretty_print() == expected_output[-1].split(" ")[-1]

            for row in expected_output:
                minor = int(MINOR_REGEX.search(row).group(1))

                # Find the latest version for a particular minor version
                latest_ver_for_minor = ListCommand(
                    archive_id,
                    filter_minor=minor,
                    is_latest_version=True,
                ).action()
                assert latest_ver_for_minor.pretty_print() == row.split(" ")[-1]

                # Find all versions for a particular minor version
                all_ver_for_minor = ListCommand(
                    archive_id,
                    filter_minor=minor,
                ).action()
                assert all_ver_for_minor.pretty_print() == row


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
    monkeypatch, version: str, extension: str, in_file: str, expect_out_file: str
):
    archive_id = ArchiveId("qt" + version[0], "windows", "desktop", extension)
    _xml = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
    expect = json.loads(
        (Path(__file__).parent / "data" / expect_out_file).read_text("utf-8")
    )

    monkeypatch.setattr(archives.ListCommand, "fetch_http", lambda self, _: _xml)

    modules = ListCommand(archive_id).fetch_modules(Version(version))
    assert modules.strings == expect["modules"]

    arches = ListCommand(archive_id).fetch_arches(Version(version))
    assert arches.strings == expect["architectures"]


@pytest.mark.parametrize(
    "host, target, tool_name",
    [
        ("mac", "desktop", "tools_cmake"),
        ("mac", "desktop", "tools_ifw"),
        ("mac", "desktop", "tools_qtcreator"),
    ],
)
def test_tool_modules(monkeypatch, host: str, target: str, tool_name: str):
    archive_id = ArchiveId("tools", host, target)
    in_file = "{}-{}-{}-update.xml".format(host, target, tool_name)
    expect_out_file = "{}-{}-{}-expect.json".format(host, target, tool_name)
    _xml = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
    expect = json.loads(
        (Path(__file__).parent / "data" / expect_out_file).read_text("utf-8")
    )

    monkeypatch.setattr(archives.ListCommand, "fetch_http", lambda self, _: _xml)

    modules = ListCommand(archive_id).fetch_tool_modules(tool_name)
    assert modules.strings == expect["modules"]


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
    def _mock(_, rest_of_url: str) -> str:
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

    monkeypatch.setattr(archives.ListCommand, "fetch_http", _mock)

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

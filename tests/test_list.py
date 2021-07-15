import json
import re
import sys
from pathlib import Path

import pytest

from aqt.installer import Cli
from aqt.metadata import ArchiveId, MetadataFactory, SimpleSpec, Version

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
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: _html)

    expected = json.loads(
        (Path(__file__).parent / "data" / expect_out_file).read_text("utf-8")
    )

    # Test 'aqt list tools'
    tools = MetadataFactory(ArchiveId("tools", os_name, target)).getList()
    assert tools == expected["tools"]

    for qt in ("qt5", "qt6"):
        for ext, expected_output in expected[qt].items():
            # Test 'aqt list qt'
            archive_id = ArchiveId(qt, os_name, target, ext if ext != "qt" else "")
            all_versions = MetadataFactory(archive_id).getList()

            if len(expected_output) == 0:
                assert not all_versions
            else:
                assert f"{all_versions}" == "\n".join(expected_output)

            # Filter for the latest version only
            latest_ver = MetadataFactory(archive_id, is_latest_version=True).getList()

            if len(expected_output) == 0:
                assert not latest_ver
            else:
                assert f"{latest_ver}" == expected_output[-1].split(" ")[-1]

            for row in expected_output:
                minor = int(MINOR_REGEX.search(row).group(1))

                # Find the latest version for a particular minor version
                latest_ver_for_minor = MetadataFactory(
                    archive_id,
                    filter_minor=minor,
                    is_latest_version=True,
                ).getList()
                assert f"{latest_ver_for_minor}" == row.split(" ")[-1]

                # Find all versions for a particular minor version
                all_ver_for_minor = MetadataFactory(
                    archive_id,
                    filter_minor=minor,
                ).getList()
                assert f"{all_ver_for_minor}" == row


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

    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: _xml)

    modules = MetadataFactory(archive_id).fetch_modules(Version(version))
    assert modules == expect["modules"]

    arches = MetadataFactory(archive_id).fetch_arches(Version(version))
    assert arches == expect["architectures"]


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

    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: _xml)

    modules = MetadataFactory(archive_id).fetch_tool_modules(tool_name)
    assert modules == expect["modules"]


@pytest.mark.parametrize(
    "host, target, tool_name",
    [
        ("mac", "desktop", "tools_cmake"),
        ("mac", "desktop", "tools_ifw"),
        ("mac", "desktop", "tools_qtcreator"),
    ],
)
def test_tool_long_listing(monkeypatch, host: str, target: str, tool_name: str):
    archive_id = ArchiveId("tools", host, target)
    in_file = "{}-{}-{}-update.xml".format(host, target, tool_name)
    expect_out_file = "{}-{}-{}-expect.json".format(host, target, tool_name)
    _xml = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
    expect = json.loads(
        (Path(__file__).parent / "data" / expect_out_file).read_text("utf-8")
    )

    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: _xml)

    table = MetadataFactory(archive_id).fetch_tool_long_listing(tool_name)
    assert table._rows() == expect["long_listing"]


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

    monkeypatch.setattr(MetadataFactory, "fetch_http", _mock)

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

    cli = Cli()
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


@pytest.mark.parametrize(
    "simple_spec, expected_name",
    (
        (SimpleSpec("*"), "mytool.999"),
        (SimpleSpec(">3.5"), "mytool.999"),
        (SimpleSpec("3.5.5"), "mytool.355"),
        (SimpleSpec("<3.5"), "mytool.300"),
        (SimpleSpec("<=3.5"), "mytool.355"),
        (SimpleSpec("<=3.5.0"), "mytool.350"),
        (SimpleSpec(">10"), None),
    ),
)
def test_list_choose_tool_by_version(simple_spec, expected_name):
    tools_data = {
        "mytool.999": {"Version": "9.9.9", "Name": "mytool.999"},
        "mytool.355": {"Version": "3.5.5", "Name": "mytool.355"},
        "mytool.350": {"Version": "3.5.0", "Name": "mytool.350"},
        "mytool.300": {"Version": "3.0.0", "Name": "mytool.300"},
    }
    item = MetadataFactory.choose_highest_version_in_spec(tools_data, simple_spec)
    if item is not None:
        assert item["Name"] == expected_name
    else:
        assert expected_name is None


qt6_android_requires_ext_msg = (
    "Qt 6 for Android requires one of the following extensions: "
    f"{ArchiveId.EXTENSIONS_REQUIRED_ANDROID_QT6}. "
    "Please add your extension using the `--extension` flag."
)
no_arm64_v8_msg = "The extension 'arm64_v8a' is only valid for Qt 6 for Android"
no_wasm_msg = "The extension 'wasm' is only available in Qt 5.13 to 5.15 on desktop."


@pytest.mark.parametrize(
    "target, ext, version, expected_msg",
    (
        ("android", "", "6.2.0", qt6_android_requires_ext_msg),
        ("android", "arm64_v8a", "5.13.0", no_arm64_v8_msg),
        ("desktop", "arm64_v8a", "5.13.0", no_arm64_v8_msg),
        ("desktop", "arm64_v8a", "6.2.0", no_arm64_v8_msg),
        ("desktop", "wasm", "5.12.11", no_wasm_msg),  # out of range
        ("desktop", "wasm", "6.2.0", no_wasm_msg),  # out of range
        ("android", "wasm", "5.12.11", no_wasm_msg),  # in range, wrong target
        ("android", "wasm", "5.14.0", no_wasm_msg),  # in range, wrong target
        ("android", "wasm", "6.2.0", qt6_android_requires_ext_msg),
    ),
)
def test_list_invalid_extensions(
    capsys, monkeypatch, target, ext, version, expected_msg
):
    def _mock(_, rest_of_url: str) -> str:
        return ""

    monkeypatch.setattr(MetadataFactory, "fetch_http", _mock)

    cat = "qt" + version[0]
    host = "windows"
    extension_params = ["--extension", ext] if ext else []
    cli = Cli()
    cli.run(["list", cat, host, target, *extension_params, "--arch", version])
    out, err = capsys.readouterr()
    sys.stdout.write(out)
    sys.stderr.write(err)
    assert expected_msg in err

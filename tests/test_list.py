import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional, Set, Union
from urllib.parse import urlparse

import pytest

from aqt.exceptions import (
    AqtException,
    ArchiveConnectionError,
    ArchiveDownloadError,
    ArchiveListError,
    CliInputError,
    EmptyMetadata,
)
from aqt.helper import Settings
from aqt.installer import Cli
from aqt.metadata import (
    ArchiveId,
    MetadataFactory,
    QtRepoProperty,
    SimpleSpec,
    ToolData,
    Version,
    Versions,
    show_list,
    suggested_follow_up,
)

ModulesQuery = MetadataFactory.ModulesQuery

Settings.load_settings()


@pytest.mark.parametrize(
    "arch, version, expect",
    (
        ("wasm_32", Version("5.13.1"), "wasm"),
        ("mingw", Version("5.13.1"), ""),
        ("android_fake", Version("5.13.1"), ""),
        ("android_x86", Version("5.13.1"), ""),
        ("android_x86", Version("6.13.1"), "x86"),
        ("android_x86", Version("6.0.0"), "x86"),
    ),
)
def test_list_extension_for_arch(arch: str, version: Version, expect: str):
    ext = QtRepoProperty.extension_for_arch(arch, version >= Version("6.0.0"))
    assert ext == expect


@pytest.mark.parametrize(
    "arch, expect",
    (
        ("wasm_32", ["wasm"]),
        ("mingw", [""]),
        ("android_fake", [""]),
        ("android", [""]),
        ("android_x86", ["", "x86"]),
    ),
)
def test_list_possible_extension_for_arch(arch: str, expect: List[str]):
    exts = QtRepoProperty.possible_extensions_for_arch(arch)
    assert set(exts) == set(expect)


@pytest.mark.parametrize(
    "init_data, expect_str, expect_fmt, expect_flat, expect_last, expect_bool",
    (
        (
            [
                (1, [Version("1.1.1"), Version("1.1.2")]),
                (2, [Version("1.2.1"), Version("1.2.2")]),
            ],
            "[[Version('1.1.1'), Version('1.1.2')], [Version('1.2.1'), Version('1.2.2')]]",
            "1.1.1 1.1.2\n1.2.1 1.2.2",
            [Version("1.1.1"), Version("1.1.2"), Version("1.2.1"), Version("1.2.2")],
            Version("1.2.2"),
            True,
        ),
        (
            [],
            "[]",
            "",
            [],
            None,
            False,
        ),
        (
            Version("1.2.3"),
            "[[Version('1.2.3')]]",
            "1.2.3",
            [Version("1.2.3")],
            Version("1.2.3"),
            True,
        ),
    ),
)
def test_versions(init_data, expect_str, expect_fmt, expect_flat, expect_last, expect_bool):
    versions = Versions(init_data)
    assert str(versions) == expect_str
    assert format(versions) == expect_fmt
    assert format(versions, "s") == expect_str
    assert versions.flattened() == expect_flat
    assert versions.latest() == expect_last
    assert bool(versions) == expect_bool

    with pytest.raises(TypeError) as pytest_wrapped_e:
        format(versions, "x")
    assert pytest_wrapped_e.type == TypeError


@pytest.fixture
def spec_regex():
    return re.compile(r"^(\d+\.\d+)")


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
        ("windows", "android", "mirror-pre-a.html", "mirror-expect.json"),
        ("windows", "android", "mirror-table-before-pre-a.html", "mirror-expect.json"),
        ("windows", "android", "mirror-first-td.html", "mirror-expect.json"),
        ("windows", "android", "mirror-tag-in-a.html", "mirror-expect.json"),
    ],
)
def test_list_versions_tools(monkeypatch, spec_regex, os_name, target, in_file, expect_out_file):
    _html = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda *args, **kwargs: _html)

    expected = json.loads((Path(__file__).parent / "data" / expect_out_file).read_text("utf-8"))

    # Test 'aqt list-tool'
    tools = MetadataFactory(ArchiveId("tools", os_name, target)).getList()
    assert tools == expected["tools"]

    # Test 'aqt list-qt'
    expected_output = expected["qt"]["qt"]
    archive_id = ArchiveId("qt", os_name, target)
    all_versions = MetadataFactory(archive_id).getList()
    assert f"{all_versions}" == "\n".join(expected_output)

    # Filter for the latest version only
    latest_ver = MetadataFactory(archive_id, is_latest_version=True).getList()
    assert f"{latest_ver}" == expected_output[-1].split(" ")[-1]

    for row in expected_output:
        spec = SimpleSpec(spec_regex.search(row).group(1))

        # Find the latest version for a particular spec
        latest_ver_for_spec = MetadataFactory(
            archive_id,
            spec=spec,
            is_latest_version=True,
        ).getList()
        assert f"{latest_ver_for_spec}" == row.split(" ")[-1]

        # Find all versions for a particular spec
        all_ver_for_spec = MetadataFactory(
            archive_id,
            spec=spec,
        ).getList()
        assert f"{all_ver_for_spec}" == row


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
        ("6.2.0", "", "windows-620-update.xml", "windows-620-expect.json"),
    ],
)
def test_list_qt_modules(monkeypatch, version: str, extension: str, in_file: str, expect_out_file: str):
    archive_id = ArchiveId("qt", "windows", "desktop")
    _xml = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
    expect = json.loads((Path(__file__).parent / "data" / expect_out_file).read_text("utf-8"))

    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: _xml)

    for arch in expect["architectures"]:
        modules = MetadataFactory(archive_id).fetch_modules(Version(version), arch)
        assert modules == sorted(expect["modules_by_arch"][arch])


@pytest.fixture
def win_5152_sde_xml_file() -> str:
    return (Path(__file__).parent / "data" / "windows-5152-src-doc-example-update.xml").read_text("utf-8")


def win_5152_sde_expected(cmd_type: str, query_type: str) -> Set[str]:
    assert cmd_type in ("src", "doc", "examples")
    assert query_type in ("archives", "modules")
    _json = json.loads((Path(__file__).parent / "data/windows-5152-src-doc-example-expect.json").read_text("utf-8"))
    return set(_json[cmd_type][query_type])


@pytest.mark.parametrize(
    "cmd_type, host, version, expected",
    [
        (
            _cmd_type,
            "windows",
            "5.15.2",
            win_5152_sde_expected(_cmd_type, "archives"),
        )
        for _cmd_type in ("src", "doc", "examples")
    ],
)
def test_list_src_doc_examples_archives(
    monkeypatch, win_5152_sde_xml_file, cmd_type: str, host: str, version: str, expected: Set[str]
):
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: win_5152_sde_xml_file)

    archive_id = ArchiveId("qt", host, "desktop")
    archives = set(MetadataFactory(archive_id).fetch_archives_sde(cmd_type, Version(version)))
    assert archives == expected


@pytest.mark.parametrize(
    "cmd_type, host, version, expected",
    [
        (
            _cmd_type,
            "windows",
            "5.15.2",
            win_5152_sde_expected(_cmd_type, "modules"),
        )
        for _cmd_type in ("doc", "examples")
    ],
)
def test_list_src_doc_examples_modules(
    monkeypatch, win_5152_sde_xml_file, cmd_type: str, host: str, version: str, expected: Set[str]
):
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: win_5152_sde_xml_file)

    archive_id = ArchiveId("qt", host, "desktop")
    modules = set(MetadataFactory(archive_id).fetch_modules_sde(cmd_type, Version(version)))
    assert modules == expected


@pytest.mark.parametrize(
    "command, expected",
    (
        ("list-src windows 5.15.2", win_5152_sde_expected("src", "archives")),
        ("list-doc windows 5.15.2", win_5152_sde_expected("doc", "archives")),
        ("list-example windows 5.15.2", win_5152_sde_expected("examples", "archives")),
        ("list-doc windows 5.15.2 --modules", win_5152_sde_expected("doc", "modules")),
        ("list-example windows 5.15.2 --modules", win_5152_sde_expected("examples", "modules")),
    ),
)
def test_list_src_doc_examples_cli(monkeypatch, capsys, win_5152_sde_xml_file, command: str, expected: Set[str]):
    def mock_fetch(self, rest_of_url):
        assert rest_of_url == "online/qtsdkrepository/windows_x86/desktop/qt5_5152_src_doc_examples/Updates.xml"
        return win_5152_sde_xml_file

    monkeypatch.setattr(MetadataFactory, "fetch_http", mock_fetch)

    cli = Cli()
    assert 0 == cli.run(command.split())
    out, err = capsys.readouterr()
    assert not err
    out_set = set(out.strip().split())
    assert out_set == expected


@pytest.mark.parametrize(
    "version, arch, modules_to_query, modules_failed_query",
    (
        ("5.14.0", "win32_mingw73", [], []),
        ("5.14.0", "win32_mingw73", ["qtcharts"], []),
        ("5.14.0", "win32_mingw73", ["all"], []),
        ("5.14.0", "win32_mingw73", ["debug_info"], ["debug_info"]),
        ("5.14.0", "win64_msvc2017_64", [], []),
        ("5.14.0", "win64_msvc2017_64", ["debug_info"], []),
    ),
)
def test_list_archives(
    monkeypatch, capsys, version: str, arch: str, modules_to_query: List[str], modules_failed_query: List[str]
):
    archive_id = ArchiveId("qt", "windows", "desktop")
    in_file = f"{archive_id.host}-{version.replace('.', '')}-update.xml"
    expect_out_file = f"{archive_id.host}-{version.replace('.', '')}-expect.json"
    _xml = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: _xml)
    expect = json.loads((Path(__file__).parent / "data" / expect_out_file).read_text("utf-8"))

    if not modules_to_query:
        expected_qt_archives = expect["qt_base_pkgs_by_arch"][arch]["DownloadableArchives"]
        expected = set([arc.split("-")[0] for arc in expected_qt_archives])
    else:
        expected_mod_metadata = expect["modules_metadata_by_arch"][arch]
        if "all" not in modules_to_query:
            expected_mod_metadata = [mod for mod in expected_mod_metadata if mod["Name"].split(".")[-2] in modules_to_query]
        expected = set([arc.split("-")[0] for mod in expected_mod_metadata for arc in mod["DownloadableArchives"]])

    archives_query = [version, arch, *modules_to_query]
    cli_args = ["list-qt", "windows", "desktop", "--archives", *archives_query]
    if not modules_failed_query:
        meta = set(MetadataFactory(archive_id, archives_query=archives_query).getList())
        assert meta == expected

        cli = Cli()
        assert 0 == cli.run(cli_args)
        out, err = capsys.readouterr()
        assert out.rstrip() == " ".join(sorted(expected))
        return

    expected_err_msg = f"The requested modules were not located: {sorted(modules_failed_query)}"
    with pytest.raises(CliInputError) as err:
        MetadataFactory(archive_id, archives_query=archives_query).getList()
    assert err.type == CliInputError
    assert format(err.value).startswith(expected_err_msg)

    cli = Cli()
    assert 1 == cli.run(cli_args)
    out, err = capsys.readouterr()
    assert expected_err_msg in err


def test_list_archives_insufficient_args(capsys):
    cli = Cli()
    assert 1 == cli.run("list-qt mac desktop --archives 5.14.0".split())
    out, err = capsys.readouterr()
    assert err.strip() == "ERROR   : The '--archives' flag requires a 'QT_VERSION' and an 'ARCHITECTURE' parameter."


@pytest.mark.parametrize(
    "xml_content",
    (
        "<Updates><PackageUpdate><badname></badname></PackageUpdate></Updates>",
        "<Updates><PackageUpdate><Name></Name></PackageUpdate></Updates>",
        "<Updates></PackageUpdate><PackageUpdate></Updates><Name></Name>",
    ),
)
def test_list_archives_bad_xml(monkeypatch, xml_content: str):
    archive_id = ArchiveId("qt", "windows", "desktop")
    archives_query = ["5.15.2", "win32_mingw81", "qtcharts"]

    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: xml_content)
    with pytest.raises(ArchiveListError) as e:
        MetadataFactory(archive_id, archives_query=archives_query).getList()
    assert e.type == ArchiveListError


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
    expect = json.loads((Path(__file__).parent / "data" / expect_out_file).read_text("utf-8"))

    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: _xml)

    modules = MetadataFactory(archive_id, tool_name=tool_name).getList()
    assert modules == expect["modules"]

    table = MetadataFactory(archive_id, tool_name=tool_name, is_long_listing=True).getList()
    assert table._rows(table.long_heading_keys) == expect["long_listing"]


@pytest.mark.parametrize(
    "host, target, version, arch",
    [
        ["windows", "desktop", "5.14.0", arch]
        for arch in ["win32_mingw73", "win32_msvc2017", "win64_mingw73", "win64_msvc2015_64", "win64_msvc2017_64"]
    ],
)
def test_long_qt_modules(monkeypatch, host: str, target: str, version: str, arch: str):
    archive_id = ArchiveId("qt", host, target)
    in_file = f"{host}-{version.replace('.', '')}-update.xml"
    expect_out_file = f"{host}-{version.replace('.', '')}-expect.json"
    _xml = (Path(__file__).parent / "data" / in_file).read_text("utf-8")
    expect = json.loads((Path(__file__).parent / "data" / expect_out_file).read_text("utf-8"))

    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: _xml)

    table = MetadataFactory(archive_id, modules_query=ModulesQuery(version, arch), is_long_listing=True).getList()
    assert table._rows(table.long_heading_keys) == expect["modules_long_by_arch"][arch]


@pytest.fixture
def expected_windows_desktop_plus_wasm_5140() -> Dict:
    input_filenames = "windows-5140-expect.json", "windows-5140-wasm-expect.json"
    to_join = [json.loads((Path(__file__).parent / "data" / f).read_text("utf-8")) for f in input_filenames]
    return {
        "architectures": [arch for _dict in to_join for arch in _dict["architectures"]],
        "modules_by_arch": {**to_join[0]["modules_by_arch"], **to_join[1]["modules_by_arch"]},
    }


@pytest.mark.parametrize(
    "args, expect",
    (
        ("--modules latest win64_msvc2017_64", ["modules_by_arch", "win64_msvc2017_64"]),
        ("--spec 5.14 --modules latest win64_msvc2017_64", ["modules_by_arch", "win64_msvc2017_64"]),
        ("--modules 5.14.0 win32_mingw73", ["modules_by_arch", "win32_mingw73"]),
        ("--modules 5.14.0 win32_msvc2017", ["modules_by_arch", "win32_msvc2017"]),
        ("--modules 5.14.0 win64_mingw73", ["modules_by_arch", "win64_mingw73"]),
        ("--modules 5.14.0 win64_msvc2015_64", ["modules_by_arch", "win64_msvc2015_64"]),
        ("--modules 5.14.0 win64_msvc2017_64", ["modules_by_arch", "win64_msvc2017_64"]),
        ("--arch latest", ["architectures"]),
        ("--spec 5.14 --arch latest", ["architectures"]),
        ("--arch 5.14.0", ["architectures"]),
    ),
)
def test_list_qt_cli(
    monkeypatch,
    capsys,
    expected_windows_desktop_plus_wasm_5140: Dict[str, Set[str]],
    args: str,
    expect: Union[Set[str], List[str]],
):
    htmlfile, xmlfile, wasm_xmlfile = "windows-desktop.html", "windows-5140-update.xml", "windows-5140-wasm-update.xml"
    version_string_to_replace = "qt5.5140"
    if isinstance(expect, list):
        # In this case, 'expect' is a list of keys to follow to the expected values.
        expected_dict = expected_windows_desktop_plus_wasm_5140
        for key in expect:  # Follow the chain of keys to the list of values.
            expected_dict = expected_dict[key]
        assert isinstance(expected_dict, list)
        expect_set = set(expected_dict)
    else:
        expect_set = expect
    assert isinstance(expect_set, set)

    def _mock_fetch_http(_, rest_of_url, *args, **kwargs: str) -> str:
        htmltext = (Path(__file__).parent / "data" / htmlfile).read_text("utf-8")
        if not rest_of_url.endswith("Updates.xml"):
            return htmltext

        norm_xmltext = (Path(__file__).parent / "data" / xmlfile).read_text("utf-8")
        wasm_xmltext = (Path(__file__).parent / "data" / wasm_xmlfile).read_text("utf-8")
        xmltext = wasm_xmltext if rest_of_url.endswith("_wasm/Updates.xml") else norm_xmltext
        # If we are serving an Updates.xml, `aqt list` will look for a Qt version number.
        # We will replace the version numbers in the file with the requested version.
        match = re.search(r"qt(\d)_(\d+)", rest_of_url)
        assert match
        major, version_nodot = match.groups()
        desired_version_string = f"qt{major}.{version_nodot}"
        return xmltext.replace(version_string_to_replace, desired_version_string)

    monkeypatch.setattr(MetadataFactory, "fetch_http", _mock_fetch_http)

    cli = Cli()
    cli.run(["list-qt", "windows", "desktop", *args.split()])
    out, err = capsys.readouterr()
    output_set = set(out.strip().split())
    assert output_set == expect_set


@pytest.mark.parametrize(
    "qt_ver_str, expect_set", (("6.2.0", {"android_x86", "android_x86_64", "android_armv7", "android_arm64_v8a"}),)
)
def test_list_android_arches(monkeypatch, capsys, qt_ver_str: str, expect_set: Set[str]):
    host, target = "windows", "android"

    def _mock_fetch_http(_, rest_of_url, *args, **kwargs: str) -> str:
        assert rest_of_url.endswith("Updates.xml"), f"Fetched unexpected file at {rest_of_url}"

        xmltext = (Path(__file__).parent / "data" / "windows-620-android-armv7-update.xml").read_text("utf-8")
        # If we are serving an Updates.xml, `aqt list` will look for a Qt version number.
        # We will replace the version numbers in the file with the requested version.
        match = re.search(r"qt\d_\d+_(?P<arch>\w+)/Updates\.xml$", rest_of_url)
        assert match
        return xmltext.replace("armv7", match.group("arch"))

    monkeypatch.setattr(MetadataFactory, "fetch_http", _mock_fetch_http)

    # Unit test:
    archive_id = ArchiveId("qt", host, target)
    actual_arches = MetadataFactory(archive_id).fetch_arches(Version(qt_ver_str))
    assert set(actual_arches) == expect_set

    # Integration test:
    cli = Cli()
    cli.run(["list-qt", host, target, "--arch", qt_ver_str])
    out, err = capsys.readouterr()
    output_set = set(out.strip().split())
    assert output_set == expect_set


@pytest.mark.parametrize(
    "host, has_wasm",
    (("linux", True), ("windows", False), ("mac", False)),
)
def test_list_desktop_arches_qt5130(monkeypatch, capsys, host: str, has_wasm: bool):
    """Tests the edge case of desktop Qt 5.13.0, in which "wasm_32" is a valid arch for Linux but not win/mac."""

    # Generate some mock Updates.xml files. The host mismatch is not important; we just want to check for arch==wasm
    updates_xmltext, wasm_updates_xmltext = [
        (Path(__file__).parent / "data" / filename).read_text("utf-8").replace("qt5.5140", "qt5.5130")
        for filename in ("windows-5140-update.xml", "windows-5140-wasm-update.xml")
    ]

    def _mock_fetch_http(_, rest_of_url, *args, **kwargs: str) -> str:
        if rest_of_url == "online/qtsdkrepository/linux_x64/desktop/qt5_5130_wasm/Updates.xml":
            return wasm_updates_xmltext
        elif rest_of_url.endswith("/desktop/qt5_5130/Updates.xml"):
            return updates_xmltext
        else:
            assert False, f"Fetched an unexpected file at '{rest_of_url}'"

    monkeypatch.setattr(MetadataFactory, "fetch_http", _mock_fetch_http)

    cli = Cli()
    cli.run(["list-qt", host, "desktop", "--arch", "5.13.0"])
    out, err = capsys.readouterr()
    output_set = set(out.strip().split())
    if has_wasm:
        assert "wasm_32" in output_set
    else:
        assert "wasm_32" not in output_set


@pytest.mark.parametrize(
    "cmd, host, expect",
    (
        ("list-qt", "windows", {"desktop", "android", "winrt"}),
        ("list-qt", "linux", {"desktop", "android"}),
        ("list-qt", "mac", {"desktop", "android", "ios"}),
        ("list-tool", "windows", {"desktop", "android", "winrt"}),
        ("list-tool", "linux", {"desktop", "android"}),
        ("list-tool", "mac", {"desktop", "android", "ios"}),
    ),
)
def test_list_targets(capsys, cmd: str, host: str, expect: Set[str]):
    cli = Cli()
    cli.run([cmd, host])
    out, err = capsys.readouterr()
    output_set = set(out.strip().split())
    assert output_set == expect


@pytest.mark.parametrize(
    "cmd, host, target",
    (
        ("list-qt", "windows", "ios"),
        ("list-qt", "linux", "ios"),
        ("list-qt", "linux", "winrt"),
        ("list-qt", "mac", "winrt"),
        ("list-tool", "windows", "ios"),
        ("list-tool", "linux", "ios"),
        ("list-tool", "linux", "winrt"),
        ("list-tool", "mac", "winrt"),
    ),
)
def test_list_wrong_target(capsys, cmd: str, host: str, target: str):
    expect = f"ERROR   : '{target}' is not a valid target for host '{host}'"

    cli = Cli()
    return_code = cli.run([cmd, host, target])
    out, err = capsys.readouterr()
    assert return_code == 1
    assert err.strip() == expect


@pytest.mark.parametrize(
    "cmd, spec",
    (
        ("list-qt", "not a spec"),
        ("list-qt", "1...3"),
        ("list-qt", ""),
        ("list-qt", ">3 <5"),
    ),
)
def test_invalid_spec(capsys, cmd: str, spec: str):
    expect_prefix = f"ERROR   : Invalid version specification: '{spec}'"
    host, target = "linux", "desktop"
    cli = Cli()
    return_code = cli.run([cmd, host, target, "--spec", spec])
    out, err = capsys.readouterr()
    assert return_code == 1
    assert err.strip().startswith(expect_prefix)


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


mac_qt = ArchiveId("qt", "mac", "desktop")
wrong_tool_name_msg = "Please use 'aqt list-tool mac desktop' to check what tools are available."
wrong_qt_version_msg = "Please use 'aqt list-qt mac desktop' to show versions of Qt available."
wrong_arch_msg = "Please use 'aqt list-qt mac desktop --arch <QT_VERSION>' to list valid architectures."


@pytest.mark.parametrize(
    "meta, expected_message",
    (
        (MetadataFactory(mac_qt), []),
        (
            MetadataFactory(mac_qt, spec=SimpleSpec("5.0")),
            ["Please use 'aqt list-qt mac desktop' to check that versions of qt exist within the spec '5.0'."],
        ),
        (
            MetadataFactory(ArchiveId("tools", "mac", "desktop"), tool_name="ifw"),
            [wrong_tool_name_msg],
        ),
        (
            MetadataFactory(mac_qt, architectures_ver="1.2.3"),
            [wrong_qt_version_msg],
        ),
        (
            MetadataFactory(mac_qt, modules_query=ModulesQuery("1.2.3", "clang_64")),
            [wrong_qt_version_msg, wrong_arch_msg],
        ),
        (
            MetadataFactory(mac_qt, archives_query=["1.2.3", "clang_64", "a module", "another module"]),
            [
                "Please use 'aqt list-qt mac desktop' to show versions of Qt available.",
                "Please use 'aqt list-qt mac desktop --arch <QT_VERSION>' to show architectures available.",
                "Please use 'aqt list-qt mac desktop --modules <QT_VERSION>' to show modules available.",
            ],
        ),
        (
            MetadataFactory(mac_qt, archives_query=["1.2.3", "clang_64"]),
            [
                "Please use 'aqt list-qt mac desktop' to show versions of Qt available.",
                "Please use 'aqt list-qt mac desktop --arch <QT_VERSION>' to show architectures available.",
            ],
        ),
        (
            MetadataFactory(mac_qt, spec=SimpleSpec("<5.9")),
            ["Please use 'aqt list-qt mac desktop' to check that versions of qt exist within the spec '<5.9'."],
        ),
        (
            MetadataFactory(ArchiveId("tools", "mac", "desktop"), tool_name="ifw"),
            [wrong_tool_name_msg],
        ),
        (
            MetadataFactory(mac_qt, architectures_ver="1.2.3"),
            [wrong_qt_version_msg],
        ),
        (
            MetadataFactory(mac_qt, modules_query=ModulesQuery("1.2.3", "clang_64")),
            [wrong_qt_version_msg, wrong_arch_msg],
        ),
    ),
)
def test_suggested_follow_up(meta: MetadataFactory, expected_message: str):
    assert suggested_follow_up(meta) == expected_message


def test_format_suggested_follow_up():
    suggestions = [
        "Please use 'aqt list-tool mac desktop --modules <QT_VERSION>' to list valid modules.",
        "Please use 'aqt list-tool mac desktop' to check what tools are available.",
    ]
    expected = (
        "==============================Suggested follow-up:==============================\n"
        "* Please use 'aqt list-tool mac desktop --modules <QT_VERSION>' to list valid modules.\n"
        "* Please use 'aqt list-tool mac desktop' to check what tools are available."
    )
    ex = AqtException("msg", suggested_action=suggestions)
    assert ex._format_suggested_follow_up() == expected


def test_format_suggested_follow_up_empty():
    ex = AqtException("msg", suggested_action=[])
    assert format(ex) == "msg"


@pytest.mark.parametrize(
    "meta, expect",
    (
        (
            MetadataFactory(ArchiveId("qt", "mac", "desktop"), spec=SimpleSpec("5.42")),
            "qt/mac/desktop with spec 5.42",
        ),
        (
            MetadataFactory(ArchiveId("qt", "mac", "desktop"), spec=SimpleSpec("5.42")),
            "qt/mac/desktop with spec 5.42",
        ),
        (MetadataFactory(ArchiveId("qt", "mac", "desktop")), "qt/mac/desktop"),
        (
            MetadataFactory(ArchiveId("qt", "mac", "desktop")),
            "qt/mac/desktop",
        ),
    ),
)
def test_list_describe_filters(meta: MetadataFactory, expect: str):
    assert meta.describe_filters() == expect


@pytest.mark.parametrize(
    "archive_id, spec, version_str, arch, expect",
    (
        (mac_qt, None, "5.12.42", None, Version("5.12.42")),
        (
            mac_qt,
            None,
            "not a version",
            None,
            CliInputError("Invalid version string: 'not a version'"),
        ),
        (mac_qt, SimpleSpec("5"), "latest", None, Version("5.15.2")),
        (
            mac_qt,
            SimpleSpec("5.0"),
            "latest",
            None,
            CliInputError("There is no latest version of Qt with the criteria 'qt/mac/desktop with spec 5.0'"),
        ),
        (mac_qt, SimpleSpec("<6.2.0"), "latest", "wasm_32", Version("5.15.2")),
    ),
)
def test_list_to_version(monkeypatch, archive_id, spec, version_str, arch: Optional[str], expect):
    _html = (Path(__file__).parent / "data" / "mac-desktop.html").read_text("utf-8")
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda *args, **kwargs: _html)

    if isinstance(expect, Exception):
        with pytest.raises(CliInputError) as error:
            MetadataFactory(archive_id, spec=spec)._to_version(version_str, arch)
        assert error.type == CliInputError
        assert str(expect) == str(error.value)
    else:
        assert MetadataFactory(archive_id, spec=spec)._to_version(version_str, arch) == expect


def test_list_fetch_tool_by_simple_spec(monkeypatch):
    update_xml = (Path(__file__).parent / "data" / "windows-desktop-tools_vcredist-update.xml").read_text("utf-8")
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: update_xml)

    expect_json = (Path(__file__).parent / "data" / "windows-desktop-tools_vcredist-expect.json").read_text("utf-8")
    expected = json.loads(expect_json)["modules_data"]

    def check(actual, expect):
        for key in (
            "Description",
            "DisplayName",
            "DownloadableArchives",
            "ReleaseDate",
            "SHA1",
            "Version",
            "Virtual",
        ):
            assert actual[key] == expect[key]

    meta = MetadataFactory(ArchiveId("tools", "windows", "desktop"))
    check(
        meta.fetch_tool_by_simple_spec(tool_name="tools_vcredist", simple_spec=SimpleSpec("2011")),
        expected["qt.tools.vcredist"],
    )
    check(
        meta.fetch_tool_by_simple_spec(tool_name="tools_vcredist", simple_spec=SimpleSpec("2014")),
        expected["qt.tools.vcredist_msvc2013_x86"],
    )
    nonexistent = meta.fetch_tool_by_simple_spec(tool_name="tools_vcredist", simple_spec=SimpleSpec("1970"))
    assert nonexistent is None

    # Simulate a broken Updates.xml file, with invalid versions
    highest_module_info = MetadataFactory.choose_highest_version_in_spec(
        all_tools_data={"some_module": {"Version": "not_a_version"}},
        simple_spec=SimpleSpec("*"),
    )
    assert highest_module_info is None


@pytest.mark.parametrize(
    "columns, expect",
    (
        (
            120,
            (
                "Tool Variant Name        Version         Release Date          Display Name          "
                "            Description            \n"
                "====================================================================================="
                "===================================\n"
                "qt.tools.ifw.41     4.1.1-202105261132   2021-05-26     Qt Installer Framework 4.1   "
                "The Qt Installer Framework provides\n"
                "                                                                                     "
                "a set of tools and utilities to    \n"
                "                                                                                     "
                "create installers for the supported\n"
                "                                                                                     "
                "desktop Qt platforms: Linux,       \n"
                "                                                                                     "
                "Microsoft Windows, and macOS.      \n"
            ),
        ),
        (
            80,
            "Tool Variant Name        Version         Release Date\n"
            "=====================================================\n"
            "qt.tools.ifw.41     4.1.1-202105261132   2021-05-26  \n",
        ),
        (
            0,
            "Tool Variant Name        Version         Release Date          Display Name          "
            "                                                                           Descriptio"
            "n                                                                            \n"
            "====================================================================================="
            "====================================================================================="
            "=============================================================================\n"
            "qt.tools.ifw.41     4.1.1-202105261132   2021-05-26     Qt Installer Framework 4.1   "
            "The Qt Installer Framework provides a set of tools and utilities to create installers"
            " for the supported desktop Qt platforms: Linux, Microsoft Windows, and macOS.\n",
        ),
    ),
)
def test_show_list_tools_long_ifw(capsys, monkeypatch, columns, expect):
    update_xml = (Path(__file__).parent / "data" / "mac-desktop-tools_ifw-update.xml").read_text("utf-8")
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: update_xml)

    monkeypatch.setattr(shutil, "get_terminal_size", lambda fallback: os.terminal_size((columns, 24)))

    meta = MetadataFactory(
        ArchiveId("tools", "mac", "desktop"),
        tool_name="tools_ifw",
        is_long_listing=True,
    )
    show_list(meta)
    out, err = capsys.readouterr()
    sys.stdout.write(out)
    sys.stderr.write(err)
    assert out == expect


LONG_MODULES_WIN_5140_120 = (
    "   Module Name                        Display Name                     Release Date   Download Size   Installed Size\n"
    "====================================================================================================================\n"
    "qtcharts            Qt Charts for MinGW 7.3.0 32-bit                   2019-12-11     772.7K          7.8M          \n"
    "qtdatavis3d         Qt Data Visualization for MinGW 7.3.0 32-bit       2019-12-11     620.2K          5.0M          \n"
    "qtlottie            Qt Lottie Animation for MinGW 7.3.0 32-bit         2019-12-11     153.5K          968.4K        \n"
    "qtnetworkauth       Qt Network Authorization for MinGW 7.3.0 32-bit    2019-12-11     98.7K           638.6K        \n"
    "qtpurchasing        Qt Purchasing for MinGW 7.3.0 32-bit               2019-12-11     50.9K           306.8K        \n"
    "qtquick3d           Qt Quick 3D for MinGW 7.3.0 32-bit                 2019-12-11     9.8M            21.2M         \n"
    "qtquicktimeline     Qt Quick Timeline for MinGW 7.3.0 32-bit           2019-12-11     35.3K           154.1K        \n"
    "qtscript            Qt Script for MinGW 7.3.0 32-bit                   2019-12-11     1.0M            5.5M          \n"
    "qtvirtualkeyboard   Qt Virtual Keyboard for MinGW 7.3.0 32-bit         2019-12-11     2.1M            6.8M          \n"
    "qtwebglplugin       Qt WebGL Streaming Plugin for MinGW 7.3.0 32-bit   2019-12-11     201.7K          1.0M          \n"
)
LONG_MODULES_WIN_5140_80 = (
    "   Module Name                        Display Name                  \n"
    "====================================================================\n"
    "qtcharts            Qt Charts for MinGW 7.3.0 32-bit                \n"
    "qtdatavis3d         Qt Data Visualization for MinGW 7.3.0 32-bit    \n"
    "qtlottie            Qt Lottie Animation for MinGW 7.3.0 32-bit      \n"
    "qtnetworkauth       Qt Network Authorization for MinGW 7.3.0 32-bit \n"
    "qtpurchasing        Qt Purchasing for MinGW 7.3.0 32-bit            \n"
    "qtquick3d           Qt Quick 3D for MinGW 7.3.0 32-bit              \n"
    "qtquicktimeline     Qt Quick Timeline for MinGW 7.3.0 32-bit        \n"
    "qtscript            Qt Script for MinGW 7.3.0 32-bit                \n"
    "qtvirtualkeyboard   Qt Virtual Keyboard for MinGW 7.3.0 32-bit      \n"
    "qtwebglplugin       Qt WebGL Streaming Plugin for MinGW 7.3.0 32-bit\n"
)


@pytest.mark.parametrize(
    "columns, use_cli, expect",
    (
        (120, False, LONG_MODULES_WIN_5140_120),
        (80, False, LONG_MODULES_WIN_5140_80),
        (120, True, LONG_MODULES_WIN_5140_120),
        (80, True, LONG_MODULES_WIN_5140_80),
    ),
)
def test_show_list_long_qt_modules(capsys, monkeypatch, columns: int, use_cli: bool, expect: str):
    update_xml = (Path(__file__).parent / "data" / "windows-5140-update.xml").read_text("utf-8")
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: update_xml)

    cli = Cli()

    # Patching get_terminal_size prevents successful instantiation of Cli, so do it afterwards:
    monkeypatch.setattr(shutil, "get_terminal_size", lambda fallback: os.terminal_size((columns, 24)))

    if use_cli:
        return_code = cli.run("list-qt windows desktop --long-modules 5.14.0 win32_mingw73".split())
        assert return_code == 0
    else:
        meta = MetadataFactory(
            ArchiveId("qt", "windows", "desktop"),
            modules_query=ModulesQuery("5.14.0", "win32_mingw73"),
            is_long_listing=True,
        )
        show_list(meta)
    out, err = capsys.readouterr()
    sys.stdout.write(out)
    sys.stderr.write(err)
    assert out == expect


def test_show_list_versions(monkeypatch, capsys):
    _html = (Path(__file__).parent / "data" / "mac-desktop.html").read_text("utf-8")
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda *args: _html)

    expect_file = Path(__file__).parent / "data" / "mac-desktop-expect.json"
    expected = "\n".join(json.loads(expect_file.read_text("utf-8"))["qt"]["qt"]) + "\n"

    show_list(MetadataFactory(mac_qt))
    out, err = capsys.readouterr()
    assert out == expected


def test_show_list_tools(monkeypatch, capsys):
    page = (Path(__file__).parent / "data" / "mac-desktop.html").read_text("utf-8")
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda *args, **kwargs: page)

    expect_file = Path(__file__).parent / "data" / "mac-desktop-expect.json"
    expect = "\n".join(json.loads(expect_file.read_text("utf-8"))["tools"]) + "\n"

    meta = MetadataFactory(ArchiveId("tools", "mac", "desktop"))
    show_list(meta)
    out, err = capsys.readouterr()
    sys.stdout.write(out)
    sys.stderr.write(err)
    assert out == expect


def test_show_list_empty(monkeypatch, capsys):
    monkeypatch.setattr(MetadataFactory, "getList", lambda self: [])
    meta = MetadataFactory(ArchiveId("tools", "mac", "desktop"))
    with pytest.raises(EmptyMetadata) as error:
        show_list(meta)
    assert error.type == EmptyMetadata
    assert format(error.value) == "No tools available for this request."


@pytest.mark.parametrize(
    "exception_class, error_msg, source",
    (
        (ArchiveConnectionError, "Failure to connect to some url", "aqt.metadata.getUrl"),
        (ArchiveDownloadError, "Failure to download some xml file", "aqt.metadata.getUrl"),
    ),
)
def test_show_list_bad_connection(monkeypatch, capsys, exception_class, error_msg, source):
    def mock(*args, **kwargs):
        raise exception_class(error_msg)

    monkeypatch.setattr(source, mock)
    meta = MetadataFactory(mac_qt, spec=SimpleSpec("<5.9"))
    with pytest.raises(exception_class) as error:
        show_list(meta)
    assert error.type == exception_class
    assert format(error.value) == (
        f"{error_msg}\n"
        "==============================Suggested follow-up:==============================\n"
        "* Please use 'aqt list-qt mac desktop' to check that versions of qt exist within the spec '<5.9'."
    )


@pytest.mark.parametrize(
    "exception_class, error_msg, source", ((ArchiveConnectionError, "Failure to connect", "aqt.helper.getUrl"),)
)
def test_show_list_bad_connection_for_checksum(monkeypatch, capsys, exception_class, error_msg, source):
    def mock(*args, **kwargs):
        raise exception_class(error_msg)

    monkeypatch.setattr(source, mock)

    cli = Cli()
    cli.run("list-qt linux desktop --arch 6.4.0".split())
    out, err = capsys.readouterr()
    sys.stdout.write(out)
    sys.stderr.write(err)

    assert (
        err == "ERROR   : Failed to download checksum for the file 'Updates.xml' from mirrors "
        "'['https://download.qt.io']\n"
        "==============================Suggested follow-up:==============================\n"
        "* Check your internet connection\n"
        "* Consider modifying `requests.max_retries_to_retrieve_hash` in settings.ini\n"
        "* Consider modifying `mirrors.trusted_mirrors` in settings.ini "
        "(see https://aqtinstall.readthedocs.io/en/stable/configuration.html#configuration)\n"
        "* Please use 'aqt list-qt linux desktop' to show versions of Qt available.\n"
    )


def fetch_expected_tooldata(json_filename: str) -> ToolData:
    text = (Path(__file__).parent / "data" / json_filename).read_text("utf-8")
    raw_tooldata: List[List[str]] = json.loads(text)["long_listing"]
    keys = ("Version", "ReleaseDate", "DisplayName", "Description")

    tools: Dict[str, Dict[str, str]] = {}
    for variant_name, *values in raw_tooldata:
        assert len(keys) == len(values)
        tools[variant_name] = {k: v for k, v in zip(keys, values)}

    return ToolData(tools)


@pytest.mark.parametrize("host, target, tool_name", (("mac", "desktop", "tools_cmake"),))
def test_list_tool_cli(monkeypatch, capsys, host: str, target: str, tool_name: str):
    html_file = f"{host}-{target}.html"
    xml_file = f"{host}-{target}-{tool_name}-update.xml"
    html_expect = f"{host}-{target}-expect.json"
    xml_expect = f"{host}-{target}-{tool_name}-expect.json"
    htmltext, xmltext, htmljson, xmljson = [
        (Path(__file__).parent / "data" / filename).read_text("utf-8")
        for filename in (html_file, xml_file, html_expect, xml_expect)
    ]
    expected_tools = set(json.loads(htmljson)["tools"])
    xml_data = json.loads(xmljson)
    expected_tool_modules = set(xml_data["modules"])

    def _mock_fetch_http(_, rest_of_url, *args, **kwargs: str) -> str:
        if not rest_of_url.endswith("Updates.xml"):
            return htmltext
        folder = urlparse(rest_of_url).path.split("/")[-2]
        assert folder.startswith("tools_")
        return xmltext

    monkeypatch.setattr(MetadataFactory, "fetch_http", _mock_fetch_http)

    cli = Cli()
    cli.run(["list-tool", host, target])
    out, err = capsys.readouterr()
    output_set = set(out.strip().split())
    assert output_set == expected_tools

    cli.run(["list-tool", host, target, tool_name])
    out, err = capsys.readouterr()
    output_set = set(out.strip().split())
    assert output_set == expected_tool_modules

    # Test abbreviated tool name: "aqt list-tool mac desktop ifw"
    assert tool_name.startswith("tools_")
    short_tool_name = tool_name[6:]
    cli.run(["list-tool", host, target, short_tool_name])
    out, err = capsys.readouterr()
    output_set = set(out.strip().split())
    assert output_set == expected_tool_modules

    cli.run(["list-tool", host, target, tool_name, "-l"])
    out, err = capsys.readouterr()

    expected_tooldata = format(fetch_expected_tooldata(xml_expect))
    assert out.strip() == expected_tooldata


def test_fetch_http_ok(monkeypatch):
    html_content = b"some_html_content"
    base_url = "https://alt.baseurl.com"

    def mock_getUrl(url: str, *args, **kwargs) -> str:
        assert url.startswith(base_url)
        return str(html_content)

    monkeypatch.setattr("aqt.metadata.get_hash", lambda *args, **kwargs: hashlib.sha256(html_content).hexdigest())
    monkeypatch.setattr("aqt.metadata.getUrl", mock_getUrl)
    assert MetadataFactory(mac_qt, base_url=base_url).fetch_http("some_url") == str(html_content)


def test_fetch_http_failover(monkeypatch):
    urls_requested = set()

    def _mock(url, **kwargs):
        urls_requested.add(url)
        if len(urls_requested) <= 1:
            raise ArchiveDownloadError()
        return "some_html_content"

    monkeypatch.setattr("aqt.metadata.get_hash", lambda *args, **kwargs: hashlib.sha256(b"some_html_content").hexdigest())
    monkeypatch.setattr("aqt.metadata.getUrl", _mock)

    # Require that the first attempt failed, but the second did not
    assert MetadataFactory(mac_qt).fetch_http("some_url") == "some_html_content"
    assert len(urls_requested) == 2


@pytest.mark.parametrize("exception_on_error", (ArchiveDownloadError, ArchiveConnectionError))
def test_fetch_http_download_error(monkeypatch, exception_on_error):
    urls_requested = set()

    def _mock(url, **kwargs):
        urls_requested.add(url)
        raise exception_on_error()

    monkeypatch.setattr("aqt.metadata.get_hash", lambda *args, **kwargs: hashlib.sha256(b"some_html_content").hexdigest())
    monkeypatch.setattr("aqt.metadata.getUrl", _mock)
    with pytest.raises(exception_on_error) as e:
        MetadataFactory(mac_qt).fetch_http("some_url")
    assert e.type == exception_on_error

    # Require that a fallback url was tried
    assert len(urls_requested) == 2


@pytest.mark.parametrize(
    "host, expected, all_arches",
    (
        ("windows", "win32_mingw", ["win64_msvc2013_64", "win32_mingw", "win16_mingw"]),
        ("windows", "win32_mingw", ["win64_msvc2013_64", "win32_mingw"]),
        ("windows", "win1_mingw0", ["win64_msvc2013_64", "win_mingw900", "win1_mingw0"]),
        ("windows", "win32_mingw1", ["win64_msvc2013_64", "win32_mingw", "win32_mingw1"]),
        ("windows", "win64_mingw", ["win64_msvc2013_64", "win32_mingw900", "win64_mingw"]),
        ("windows", "win64_mingw81", ["win64_msvc2013_64", "win64_mingw81", "win64_mingw"]),
        ("windows", "win64_mingw73", ["win64_msvc2013_64", "win64_mingw53", "win64_mingw73"]),
        ("windows", "win64_mingw", ["win64_msvc2013_64", "win64_mingw", "win64_mingw"]),
        ("windows", EmptyMetadata(), []),
        ("linux", "gcc_64", ["should not fetch arches"]),
        ("mac", "clang_64", ["should not fetch arches"]),
    ),
)
def test_select_default_mingw(monkeypatch, host: str, expected: Union[str, Exception], all_arches: List[str]):
    monkeypatch.setattr("aqt.metadata.MetadataFactory.fetch_arches", lambda *args, **kwargs: all_arches)

    if isinstance(expected, Exception):
        with pytest.raises(type(expected)) as e:
            MetadataFactory(ArchiveId("qt", host, "desktop")).fetch_default_desktop_arch(Version("1.2.3"))
        assert e.type == type(expected)
    else:
        actual_arch = MetadataFactory(ArchiveId("qt", host, "desktop")).fetch_default_desktop_arch(Version("1.2.3"))
        assert actual_arch == expected


@pytest.mark.parametrize(
    "expected_result, installed_files",
    (
        ("mingw73_32", ["mingw73_32/bin/qmake.exe", "msvc2017/bin/qmake.exe"]),
        (None, ["msvc2017/bin/qmake.exe"]),
        (None, ["mingw73_win/bin/qmake.exe"]),  # Bad directory: mingw73_win does not fit the mingw naming convention
        (None, ["mingw73_32/bin/qmake", "msvc2017/bin/qmake.exe"]),
        ("mingw81_32", ["mingw73_32/bin/qmake.exe", "mingw81_32/bin/qmake.exe"]),
        ("mingw73_64", ["mingw73_64/bin/qmake.exe", "mingw73_32/bin/qmake.exe"]),
    ),
)
def test_find_installed_qt_mingw_dir(expected_result: str, installed_files: List[str]):
    qt_ver = "6.3.0"
    host = "windows"

    # Setup a mock install directory that includes some installed files
    with TemporaryDirectory() as base_dir:
        base_path = Path(base_dir)
        for file in installed_files:
            path = base_path / qt_ver / file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Mock installed file")

        actual_result = QtRepoProperty.find_installed_desktop_qt_dir(host, base_path, Version(qt_ver))
        assert (actual_result.name if actual_result else None) == expected_result

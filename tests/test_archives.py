import hashlib
import json
import os
import re
from itertools import groupby
from pathlib import Path
from typing import Dict, Iterable, List, Set

import pytest

from aqt.archives import ModuleToPackage, QtArchives, QtPackage, SrcDocExamplesArchives, ToolArchives
from aqt.exceptions import ArchiveListError, NoPackageFound
from aqt.helper import Settings
from aqt.metadata import Version


@pytest.fixture(autouse=True)
def setup():
    Settings.load_settings(os.path.join(os.path.dirname(__file__), "data", "settings.ini"))


@pytest.mark.parametrize(
    "os_name, version, arch, datafile",
    [
        ("windows", "5.15.0", "win64_msvc2019_64", "windows-5150-update.xml"),
        ("windows", "5.15.0", "win64_mingw81", "windows-5150-update.xml"),
        ("windows", "5.14.0", "win64_mingw73", "windows-5140-update.xml"),
    ],
)
def test_parse_update_xml(monkeypatch, os_name, version, arch, datafile):
    def _mock(self, url):
        with open(os.path.join(os.path.dirname(__file__), "data", datafile), "r") as f:
            self.update_xml_text = f.read()

    monkeypatch.setattr(QtArchives, "_download_update_xml", _mock)

    qt_archives = QtArchives(os_name, "desktop", version, arch, Settings.baseurl)
    assert qt_archives.archives is not None

    # Get packages with all extra modules
    qt_archives_all_modules = QtArchives(
        os_name,
        "desktop",
        version,
        arch,
        base="https://example.com/",
        modules=["all"],
        all_extra=True,
    )
    assert qt_archives_all_modules.archives is not None

    # Extract all urls
    url_list = [item.archive_path for item in qt_archives.archives]
    url_all_modules_list = [item.archive_path for item in qt_archives_all_modules.archives]

    # Check the difference list contains only extra modules urls for target specified
    list_diff = [item for item in url_all_modules_list if item not in url_list]
    unwanted_targets = [item for item in list_diff if arch not in item]

    # Assert if list_diff contains urls without target specified
    assert unwanted_targets == []


@pytest.fixture()
def corrupt_xmlfile():
    return "<UnclosedTag></SomeOtherTag>"


@pytest.mark.parametrize(
    "archives_class, init_args",
    (
        (QtArchives, ("mac", "desktop", "1.2.3", "clang", Settings.baseurl)),
        (ToolArchives, ("mac", "desktop", "tools_qtifw", Settings.baseurl)),
    ),
)
def test_qtarchive_parse_corrupt_xmlfile(monkeypatch, corrupt_xmlfile, archives_class, init_args):
    monkeypatch.setattr("aqt.archives.getUrl", lambda *args, **kwargs: corrupt_xmlfile)
    monkeypatch.setattr(
        "aqt.archives.get_hash", lambda *args, **kwargs: hashlib.sha256(bytes(corrupt_xmlfile, "utf-8")).hexdigest()
    )

    with pytest.raises(ArchiveListError) as error:
        archives_class(*init_args)
    assert error.type == ArchiveListError
    assert format(error.value) == "Downloaded metadata is corrupted. mismatched tag: line 1, column 15"


@pytest.mark.parametrize(
    "arch, requested_module_names, has_nonexistent_modules",
    (
        ("win32_mingw73", ("qtlottie", "qtcharts"), False),
        ("win32_mingw73", ("all",), False),
        ("win32_msvc2017", ("debug_info", "qtwebengine"), False),
        ("win64_mingw73", ("qtlottie", "qtcharts"), False),
        ("win64_msvc2015_64", ("debug_info", "qtnetworkauth"), False),
        ("win64_msvc2017_64", ("debug_info", "qtwebengine"), False),
        ("win64_msvc2017_64", ("all",), False),
        ("win32_mingw73", ("debug_info", "qtwebengine"), True),
        ("win64_mingw73", ("debug_info", "qtwebengine"), True),
        ("win64_msvc2015_64", ("qtwebengine", "nonexistent"), True),
    ),
)
def test_qt_archives_modules(monkeypatch, arch, requested_module_names, has_nonexistent_modules: bool):
    update_xml = (Path(__file__).parent / "data" / "windows-5140-update.xml").read_text("utf-8")

    def _mock(self, *args):
        self.update_xml_text = update_xml

    monkeypatch.setattr(QtArchives, "_download_update_xml", _mock)

    expect_json = json.loads((Path(__file__).parent / "data" / "windows-5140-expect.json").read_text("utf-8"))
    expected = expect_json["modules_metadata_by_arch"][arch]
    base_expected = expect_json["qt_base_pkgs_by_arch"][arch]

    os_name, target, base, version = "windows", "desktop", "https://example.com", Version("5.14.0")
    qt_base = "QT-BASE"

    def locate_module_data(haystack: Iterable[Dict[str, str]], name: str) -> Dict[str, str]:
        if name == qt_base:
            return base_expected
        for mod_meta in haystack:
            if mod_meta["Name"] == f"qt.qt5.5140.{name}.{arch}":
                return mod_meta
        return {}

    def verify_qt_package_stride(pkgs: Iterable[QtPackage], expect: Dict[str, str]):
        # https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt5_5140/
        # qt.qt5.5140.qtcharts.win32_mingw73/5.14.0-0-202108190846qtcharts-windows-win32_mingw73.7z

        url_begin = "online/qtsdkrepository/windows_x86/desktop/qt5_5140"
        expected_archive_url_pattern = re.compile(
            r"^" + re.escape(url_begin) + "/(" + expect["Name"] + ")/" + re.escape(expect["Version"]) + r"(.+\.7z)$"
        )

        expected_7z_files = set(expect["DownloadableArchives"])
        for pkg in pkgs:
            if not expect["Description"]:
                assert not pkg.package_desc
            else:
                assert pkg.package_desc == expect["Description"]
            url_match = expected_archive_url_pattern.match(pkg.archive_path)
            assert url_match
            mod_name, archive_name = url_match.groups()
            assert pkg.archive == archive_name
            assert archive_name in expected_7z_files
            expected_7z_files.remove(archive_name)
        assert len(expected_7z_files) == 0, "Actual number of packages was fewer than expected"

    if has_nonexistent_modules:
        expect_help = [f"Please use 'aqt list-qt {os_name} {target} --modules {version} <arch>' to show modules available."]
        for unexpected_module in requested_module_names:
            with pytest.raises(NoPackageFound) as e:
                mod_names = ("qtcharts", unexpected_module)
                QtArchives(os_name, target, str(version), arch, base, modules=mod_names)
            assert e.type == NoPackageFound
            assert unexpected_module in str(e.value), "Message should include the missing module"
            assert e.value.suggested_action == expect_help
        return

    is_all_modules = "all" in requested_module_names
    qt_pkgs = QtArchives(
        os_name, target, str(version), arch, base, modules=requested_module_names, all_extra=is_all_modules
    ).archives

    if is_all_modules:
        requested_module_names = [module["Name"].split(".")[-2] for module in expected]

    unvisited_modules = {*requested_module_names, qt_base}

    # This assumes that qt_pkgs are in a specific order
    for pkg_update_name, qt_packages in groupby(qt_pkgs, lambda x: x.pkg_update_name):
        match = re.match(r"^qt\.qt5\.5140(\.addons\.\w+|\.\w+|)\." + arch + r"$", pkg_update_name)
        assert match, f"QtArchive includes package named '{pkg_update_name}' with unexpected naming convention"
        mod_name = match.group(1)
        mod_name = mod_name[1:] if mod_name else qt_base
        assert mod_name in unvisited_modules
        unvisited_modules.remove(mod_name)
        expected_meta = locate_module_data(expected, mod_name)
        verify_qt_package_stride(qt_packages, expected_meta)

    assert len(unvisited_modules) == 0, f"Failed to produce packages for {unvisited_modules}"


@pytest.mark.parametrize(
    "tool_name, tool_variant_name, is_expect_fail",
    (
        ("tools_qtcreator", "qt.tools.qtcreator", False),
        ("tools_qtcreator", "qt.tools.qtcreatordbg", False),
        ("tools_qtcreator", "qt.tools.qtcreatordev", False),
        ("tools_qtcreator", "qt.tools.qtifw", True),
        ("tools_qtdesignstudio", "qt.tools.qtdesignstudio", False),
    ),
)
def test_tools_variants(monkeypatch, tool_name, tool_variant_name, is_expect_fail: bool):
    host, target, base = "mac", "desktop", "https://example.com"
    datafile = f"{host}-{target}-{tool_name}"
    update_xml = (Path(__file__).parent / "data" / f"{datafile}-update.xml").read_text("utf-8")

    def _mock(self, *args):
        self.update_xml_text = update_xml

    monkeypatch.setattr(QtArchives, "_download_update_xml", _mock)

    if is_expect_fail:
        expect_help = [f"Please use 'aqt list-tool {host} {target} {tool_name}' to show tool variants available."]
        with pytest.raises(NoPackageFound) as e:
            ToolArchives(host, target, tool_name, base, arch=tool_variant_name)
        assert e.type == NoPackageFound
        assert tool_variant_name in str(e.value), "Message should include the missing variant"
        assert e.value.suggested_action == expect_help
        return

    expect_json = json.loads((Path(__file__).parent / "data" / f"{datafile}-expect.json").read_text("utf-8"))
    expect = next(filter(lambda x: x["Name"] == tool_variant_name, expect_json["variants_metadata"]))
    expected_7z_files = set(expect["DownloadableArchives"])
    qt_pkgs = ToolArchives(host, target, tool_name, base, arch=tool_variant_name).archives
    url_begin = f"online/qtsdkrepository/mac_x64/{target}/{tool_name}"
    expected_archive_url_pattern = re.compile(
        r"^" + re.escape(url_begin) + "/(" + expect["Name"] + ")/" + re.escape(expect["Version"]) + r"(.+\.7z)$"
    )

    for pkg in qt_pkgs:
        if not expect["Description"]:
            assert not pkg.package_desc
        else:
            assert pkg.package_desc == expect["Description"]
        url_match = expected_archive_url_pattern.match(pkg.archive_path)
        assert url_match
        actual_variant_name, archive_name = url_match.groups()
        assert actual_variant_name == tool_variant_name
        assert pkg.archive == archive_name
        assert archive_name in expected_7z_files
        expected_7z_files.remove(archive_name)
    assert len(expected_7z_files) == 0, f"Failed to produce QtPackages for {expected_7z_files}"


def to_xml(package_updates: Iterable[Dict]) -> str:
    def wrap(tag: str, content: str, is_multiline: bool = True):
        newline = "\n" if is_multiline else ""
        return f"<{tag}>{newline}{content}{newline}</{tag}>"

    return wrap(
        "Updates",
        "\n".join(
            [
                wrap("PackageUpdate", "\n".join([wrap(key, value, False) for key, value in pu.items()]))
                for pu in package_updates
            ]
        ),
    )


@pytest.mark.parametrize(
    "tool_name, variant_name, version, actual_version",
    (("tools_qtcreator", "qt.tools.qtcreator", "1.2.3", "3.2.1"),),
)
def test_tool_archive_wrong_version(monkeypatch, tool_name, variant_name, version, actual_version):
    def _mock(self, *args):
        self.update_xml_text = to_xml([dict(Name=variant_name, Version=actual_version)])

    monkeypatch.setattr(QtArchives, "_download_update_xml", _mock)

    host, target, base = "mac", "desktop", "https://example.com"
    with pytest.raises(NoPackageFound) as e:
        ToolArchives(host, target, tool_name, base, version_str=version, arch=variant_name)
    assert e.type == NoPackageFound


# Test the helper class
def test_module_to_package():
    qt_base_names = ["qt.999.clang", "qt9.999.clang", "qt9.999.addon.clang"]
    qtcharts_names = ["qt.qt6.620.addons.qtcharts.arch", "qt.qt6.620.qtcharts.arch", "qt.620.addons.qtcharts.arch"]

    mapping = ModuleToPackage({"qt_base": qt_base_names})
    for package_name in qt_base_names:
        assert mapping.has_package(package_name), "Package must exist in reverse mapping"
    mapping.add("qtcharts", qtcharts_names)
    for package_name in qtcharts_names:
        assert mapping.has_package(package_name), "Package must exist in reverse mapping"
    assert mapping.has_package(qt_base_names[0]), "Mapping for existing packages must remain unaffected"

    mapping.remove_module_for_package(qt_base_names[0])
    for package_name in qt_base_names:
        assert not mapping.has_package(package_name), "None of the qt_base packages may remain after removal"
    assert len(mapping) == 1, "There must be one remaining module name"

    mapping.remove_module_for_package(qtcharts_names[2])
    for package_name in qtcharts_names:
        assert not mapping.has_package(package_name), "None of the qtcharts packages may remain after removal"
    assert len(mapping) == 0, "There must be no remaining module names"


qt_5140_xml_weird_module = """
<Updates>
 <PackageUpdate>
  <Name>qt.qt5.5140.qtcharts.win32_mingw73</Name>
  <DisplayName>Qt Charts</DisplayName>
  <Description>blah blah blah</Description>
  <Version>5.14.0-0-201912110700</Version>
  <ReleaseDate>2019-12-11</ReleaseDate>
  <Dependencies>qt.qt5.5140.doc.qtcharts, qt.qt5.5140.examples.qtcharts</Dependencies>
  <AutoDependOn/>
  <DownloadableArchives>weird-qtcharts.7z</DownloadableArchives>
  <UpdateFile CompressedSize="791213" OS="Any" UncompressedSize="8196243"/>
 </PackageUpdate>
 <PackageUpdate>
  <Name>qt.qt5.5140.win32_mingw73</Name>
  <DisplayName>Mingw 32-bit</DisplayName>
  <Description>blah blah blah</Description>
  <Version>5.14.0-0-201912110700</Version>
  <ReleaseDate>2019-12-11</ReleaseDate>
  <Dependencies>qt.tools.qtcreator, qt.qt5.5140.doc, qt.qt5.5140.examples</Dependencies>
  <AutoDependOn/>
  <DownloadableArchives>qtbase-mingw.7z, other-mingw.7z</DownloadableArchives>
  <UpdateFile CompressedSize="81303586" OS="Any" UncompressedSize="540178217"/>
 </PackageUpdate>
 <PackageUpdate>
  <Name>qt.qt5.5140.debug_info.win32_mingw73</Name>
  <DisplayName>Desktop Mingw 32-bit debug information files</DisplayName>
  <Description>Qt 5.14.0 debug information files for Desktop Mingw 32-bit</Description>
  <Version>5.14.0-0-201912110700</Version>
  <ReleaseDate>2019-12-11</ReleaseDate>
  <AutoDependOn>qt.qt5.5140.debug_info, qt.qt5.5140.win32_mingw73</AutoDependOn>
  <Dependencies>qt.qt5.5140.win32_mingw73</Dependencies>
  <DownloadableArchives>qtbase-debug_info.7z, weird-debug_info.7z, somethingELSE-debug_info.7z</DownloadableArchives>
  <UpdateFile CompressedSize="459720623" OS="Any" UncompressedSize="3579147640"/>
 </PackageUpdate>
</Updates>
"""
qt_doc_5152_xml_weird_module = """
<Updates>
 <PackageUpdate>
  <Name>qt.qt5.5152.doc.qtcharts</Name>
  <DisplayName>Documentation for Qt 5.15.2 GPLv3 components (QtCharts)</DisplayName>
  <Description>Documentation for Qt 5.15.2 GPLv3 components (QtCharts)</Description>
  <Version>5.15.2-0-202011130724</Version>
  <ReleaseDate>2020-11-13</ReleaseDate>
  <DownloadableArchives>weird-qtcharts-docs.7z</DownloadableArchives>
  <UpdateFile UncompressedSize="16802053" OS="Any" CompressedSize="8714357"/>
 </PackageUpdate>
 <PackageUpdate>
  <Name>qt.qt5.5152.doc</Name>
  <DisplayName>Qt 5.15.2 Documentation</DisplayName>
  <Description>Qt 5.15.2 documentation</Description>
  <Version>5.15.2-0-202011130724</Version>
  <ReleaseDate>2020-11-13</ReleaseDate>
  <Dependencies>qt.tools</Dependencies>
  <DownloadableArchives>tqtc-docs.7z, other-docs.7z</DownloadableArchives>
  <UpdateFile UncompressedSize="402906410" OS="Any" CompressedSize="134528625"/>
 </PackageUpdate>
</Updates>
"""


def make_qt_archives(subarchives, modules, is_include_base) -> QtArchives:
    return QtArchives(
        "mac",
        "desktop",
        "5.14.0",
        "win32_mingw73",
        "www.example.com",
        subarchives,
        modules,
        "all" in modules,
        is_include_base,
    )


def make_doc_archives(subarchives, modules, is_include_base) -> SrcDocExamplesArchives:
    return SrcDocExamplesArchives(
        flavor="doc",
        os_name="mac",
        target="desktop",
        version="5.15.2",
        base="www.example.com",
        subarchives=subarchives,
        modules=modules,
        all_extra="all" in modules,
        is_include_base_package=is_include_base,
    )


@pytest.mark.parametrize(
    "subarchives, modules, is_include_base, xml, make_archives_fn, expect_archives",
    (
        (["qtbase"], [], True, qt_5140_xml_weird_module, make_qt_archives, {"qtbase-mingw.7z"}),
        # --archives should apply to debug_info and base, but not qtcharts module
        (
            ["qtbase"],
            ["all"],
            True,
            qt_5140_xml_weird_module,
            make_qt_archives,
            {"qtbase-mingw.7z", "qtbase-debug_info.7z", "weird-qtcharts.7z"},
        ),
        # don't allow archives from debug_info
        (
            ["qtbase"],
            ["qtcharts"],
            True,
            qt_5140_xml_weird_module,
            make_qt_archives,
            {"qtbase-mingw.7z", "weird-qtcharts.7z"},
        ),
        # don't include anything from base module
        (["qtbase"], [], False, qt_5140_xml_weird_module, make_qt_archives, set()),
        # --archives should apply to debug_info
        (
            ["qtbase"],
            ["all"],
            False,
            qt_5140_xml_weird_module,
            make_qt_archives,
            {"qtbase-debug_info.7z", "weird-qtcharts.7z"},
        ),
        # don't allow archives from debug_info
        (["qtbase"], ["qtcharts"], False, qt_5140_xml_weird_module, make_qt_archives, {"weird-qtcharts.7z"}),
        (["tqtc"], [], True, qt_doc_5152_xml_weird_module, make_doc_archives, {"tqtc-docs.7z"}),
        (
            ["tqtc"],
            ["all"],
            True,
            qt_doc_5152_xml_weird_module,
            make_doc_archives,
            {"tqtc-docs.7z", "weird-qtcharts-docs.7z"},
        ),
        (
            ["tqtc"],
            ["qtcharts"],
            True,
            qt_doc_5152_xml_weird_module,
            make_doc_archives,
            {"tqtc-docs.7z", "weird-qtcharts-docs.7z"},
        ),
        (["tqtc"], [], False, qt_doc_5152_xml_weird_module, make_doc_archives, set()),
        (["tqtc"], ["all"], False, qt_doc_5152_xml_weird_module, make_doc_archives, {"weird-qtcharts-docs.7z"}),
        (["tqtc"], ["qtcharts"], False, qt_doc_5152_xml_weird_module, make_doc_archives, {"weird-qtcharts-docs.7z"}),
    ),
)
def test_archives_weird_module_7z_name(
    monkeypatch,
    subarchives: List[str],
    modules: List[str],
    is_include_base: bool,
    xml: str,
    make_archives_fn,
    expect_archives: Set[str],
):
    monkeypatch.setattr("aqt.archives.getUrl", lambda *args: xml)
    monkeypatch.setattr("aqt.archives.get_hash", lambda *args, **kwargs: hashlib.sha256(bytes(xml, "utf-8")).hexdigest())

    qt_archives = make_archives_fn(subarchives, modules, is_include_base)
    archives = {pkg.archive for pkg in qt_archives.archives}
    assert archives == expect_archives

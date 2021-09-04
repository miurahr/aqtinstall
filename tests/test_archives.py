import json
import os
import posixpath
import re
from itertools import groupby
from pathlib import Path
from typing import Dict, Iterable

import pytest

from aqt.archives import ModuleToPackage, QtArchives, QtPackage, ToolArchives
from aqt.exceptions import NoPackageFound
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
    url_list = [item.archive_url for item in qt_archives.archives]
    url_all_modules_list = [item.archive_url for item in qt_archives_all_modules.archives]

    # Check the difference list contains only extra modules urls for target specified
    list_diff = [item for item in url_all_modules_list if item not in url_list]
    unwanted_targets = [item for item in list_diff if arch not in item]

    # Assert if list_diff contains urls without target specified
    assert unwanted_targets == []


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

        url_begin = posixpath.join(base, "online/qtsdkrepository/windows_x86/desktop/qt5_5140")
        expected_archive_url_pattern = re.compile(
            r"^" + re.escape(url_begin) + "/(" + expect["Name"] + ")/" + re.escape(expect["Version"]) + r"(.+\.7z)$"
        )

        expected_7z_files = set(expect["DownloadableArchives"])
        for pkg in pkgs:
            if not expect["Description"]:
                assert not pkg.package_desc
            else:
                assert pkg.package_desc == expect["Description"]
            url_match = expected_archive_url_pattern.match(pkg.archive_url)
            assert url_match
            mod_name, archive_name = url_match.groups()
            assert pkg.archive == archive_name
            assert pkg.hashurl == pkg.archive_url + ".sha1"
            assert archive_name in expected_7z_files
            expected_7z_files.remove(archive_name)
        assert len(expected_7z_files) == 0, "Actual number of packages was fewer than expected"

    if has_nonexistent_modules:
        for unexpected_module in requested_module_names:
            with pytest.raises(NoPackageFound) as e:
                mod_names = ("qtcharts", unexpected_module)
                QtArchives(os_name, target, str(version), arch, base, modules=mod_names)
            assert e.type == NoPackageFound
            assert unexpected_module in str(e.value), "Message should include the missing module"
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
        with pytest.raises(NoPackageFound) as e:
            ToolArchives(host, target, tool_name, base, arch=tool_variant_name)
        assert e.type == NoPackageFound
        assert tool_variant_name in str(e.value), "Message should include the missing variant"
        return

    expect_json = json.loads((Path(__file__).parent / "data" / f"{datafile}-expect.json").read_text("utf-8"))
    expect = next(filter(lambda x: x["Name"] == tool_variant_name, expect_json["variants_metadata"]))
    expected_7z_files = set(expect["DownloadableArchives"])
    qt_pkgs = ToolArchives(host, target, tool_name, base, arch=tool_variant_name).archives
    url_begin = posixpath.join(base, f"online/qtsdkrepository/mac_x64/{target}/{tool_name}")
    expected_archive_url_pattern = re.compile(
        r"^" + re.escape(url_begin) + "/(" + expect["Name"] + ")/" + re.escape(expect["Version"]) + r"(.+\.7z)$"
    )

    for pkg in qt_pkgs:
        if not expect["Description"]:
            assert not pkg.package_desc
        else:
            assert pkg.package_desc == expect["Description"]
        url_match = expected_archive_url_pattern.match(pkg.archive_url)
        assert url_match
        actual_variant_name, archive_name = url_match.groups()
        assert actual_variant_name == tool_variant_name
        assert pkg.archive == archive_name
        assert pkg.hashurl == pkg.archive_url + ".sha1"
        assert archive_name in expected_7z_files
        expected_7z_files.remove(archive_name)
    assert len(expected_7z_files) == 0, f"Failed to produce QtPackages for {expected_7z_files}"


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

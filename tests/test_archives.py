import json
import os
import posixpath
import re
from itertools import groupby
from pathlib import Path
from typing import Dict, Iterable

import pytest

from aqt.archives import QtArchives, QtPackage
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
    "arch, expected_mod_names, unexpected_mod_names",
    (
        ("win32_mingw73", ("qtlottie", "qtcharts"), ("debug_info", "qtwebengine")),
        ("win32_msvc2017", ("debug_info", "qtwebengine"), ("nonexistent",)),
        ("win64_mingw73", ("qtlottie", "qtcharts"), ("debug_info", "qtwebengine")),
        ("win64_msvc2015_64", ("debug_info", "qtnetworkauth"), ("qtwebengine",)),
        ("win64_msvc2017_64", ("debug_info", "qtwebengine"), ("nonexistent",)),
    ),
)
def test_qt_archives_modules(monkeypatch, arch, expected_mod_names, unexpected_mod_names):
    update_xml = (Path(__file__).parent / "data" / "windows-5140-update.xml").read_text("utf-8")

    def _mock(self, *args):
        self.update_xml_text = update_xml

    monkeypatch.setattr(QtArchives, "_download_update_xml", _mock)

    expect_json = json.loads((Path(__file__).parent / "data" / "windows-5140-expect.json").read_text("utf-8"))
    expected = expect_json["modules_metadata_by_arch"][arch]
    base_expected = expect_json["qt_base_pkgs_by_arch"][arch]

    version = Version("5.14.0")
    os_name, target, base = "windows", "desktop", "https://example.com"
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

    # TODO compare all_modules to expected
    # qt_pkgs = QtArchives(os_name, target, str(version), arch, base, modules=("all",).archives

    for unexpected_module in unexpected_mod_names:
        with pytest.raises(NoPackageFound) as e:
            mod_names = ("qtcharts", unexpected_module)
            QtArchives(os_name, target, str(version), arch, base, modules=mod_names)
        assert e.type == NoPackageFound
        assert unexpected_module in str(e.value), "Message should include the missing module"

    qt_pkgs = QtArchives(os_name, target, str(version), arch, base, modules=expected_mod_names).archives

    unvisited_modules = {*expected_mod_names, qt_base}

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

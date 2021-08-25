import json
import os
import posixpath
import re
from pathlib import Path

import pytest

from aqt.archives import QtArchives, ToolArchives
from aqt.exceptions import NoPackageFound
from aqt.helper import Settings


@pytest.fixture(autouse=True)
def setup():
    Settings.load_settings(os.path.join(os.path.dirname(__file__), "data", "settings.ini"))


@pytest.mark.parametrize(
    "os_name,version,target,datafile",
    [
        ("windows", "5.15.0", "win64_msvc2019_64", "windows-5150-update.xml"),
        ("windows", "5.15.0", "win64_mingw81", "windows-5150-update.xml"),
        ("windows", "5.14.0", "win64_mingw73", "windows-5140-update.xml"),
    ],
)
def test_parse_update_xml(monkeypatch, os_name, version, target, datafile):
    def _mock(self, url):
        with open(os.path.join(os.path.dirname(__file__), "data", datafile), "r") as f:
            self.update_xml_text = f.read()

    monkeypatch.setattr(QtArchives, "_download_update_xml", _mock)

    Settings.load_settings(os.path.join(os.path.dirname(__file__), "data", "settings.ini"))
    qt_archives = QtArchives(os_name, "desktop", version, target, Settings.baseurl)
    assert qt_archives.archives is not None

    # Get packages with all extra modules
    qt_archives_all_modules = QtArchives(
        os_name,
        "desktop",
        version,
        target,
        "https://example.com/",
        ["all"],
        None,
        None,
        True,
    )
    assert qt_archives_all_modules.archives is not None

    # Extract all urls
    url_list = [item.archive_url for item in qt_archives.archives]
    url_all_modules_list = [item.url for item in qt_archives_all_modules.archives]

    # Check the difference list contains only extra modules urls for target specified
    list_diff = [item for item in url_all_modules_list if item not in url_list]
    unwanted_targets = [item for item in list_diff if target not in item]

    # Assert if list_diff contains urls without target specified
    assert unwanted_targets == []


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

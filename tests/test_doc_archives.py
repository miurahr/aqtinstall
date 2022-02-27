import os

import pytest

from aqt.archives import QtArchives, SrcDocExamplesArchives
from aqt.helper import Settings


@pytest.fixture(autouse=True)
def setup():
    Settings.load_settings(os.path.join(os.path.dirname(__file__), "data", "settings.ini"))


@pytest.mark.parametrize(
    "os_name, version, flavor, datafile",
    (
        ("windows", "5.15.2", "doc", "windows-5152-src-doc-example-update.xml"),
        ("windows", "5.15.2", "src", "windows-5152-src-doc-example-update.xml"),
        ("windows", "5.15.2", "examples", "windows-5152-src-doc-example-update.xml"),
    ),
)
def test_parse_update_xml(monkeypatch, os_name, version, flavor, datafile):
    def _mock(self, url):
        with open(os.path.join(os.path.dirname(__file__), "data", datafile), "r") as f:
            self.update_xml_text = f.read()

    monkeypatch.setattr(QtArchives, "_download_update_xml", _mock)

    qt_archives = SrcDocExamplesArchives(flavor, os_name, "desktop", version, Settings.baseurl)
    assert qt_archives.archives is not None

    # Get packages with all extra modules
    qt_archives_all_modules = SrcDocExamplesArchives(
        flavor,
        os_name,
        "desktop",
        version,
        Settings.baseurl,
        all_extra=True,
    )
    assert qt_archives_all_modules.archives is not None

    # Extract all urls
    url_list = [item.archive_path for item in qt_archives.archives]
    url_all_modules_list = [item.archive_path for item in qt_archives_all_modules.archives]

    # Check the difference list contains only extra modules urls for target specified
    list_diff = [item for item in url_all_modules_list if item not in url_list]
    unwanted_targets = [item for item in list_diff if flavor not in item]

    # Assert if list_diff contains urls without target specified
    assert unwanted_targets == []

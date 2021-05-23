import os

import pytest

from aqt.archives import QtArchives
from aqt.helper import Settings


@pytest.mark.parametrize(
    "os_name,version,target,datafile",
    [("windows", "5.15.2", "doc", "windows-5152-src-doc-example-update.xml")],
)
def test_parse_update_xml(monkeypatch, os_name, version, target, datafile):
    def _mock(self, url):
        with open(os.path.join(os.path.dirname(__file__), "data", datafile), "r") as f:
            self.update_xml_text = f.read()

    monkeypatch.setattr(QtArchives, "_download_update_xml", _mock)

    settings = Settings()
    qt_archives = QtArchives(os_name, "desktop", version, target, settings.baseurl)
    assert qt_archives.archives is not None

    # Get packages with all extra modules
    qt_archives_all_modules = QtArchives(
        os_name, "desktop", version, target, settings.baseurl, None, ["all"], None, True
    )
    assert qt_archives_all_modules.archives is not None

    # Extract all urls
    url_list = [item.url for item in qt_archives.archives]
    url_all_modules_list = [item.url for item in qt_archives_all_modules.archives]

    # Check the difference list contains only extra modules urls for target specified
    list_diff = [item for item in url_all_modules_list if item not in url_list]
    unwanted_targets = [item for item in list_diff if target not in item]

    # Assert if list_diff contains urls without target specified
    assert unwanted_targets == []

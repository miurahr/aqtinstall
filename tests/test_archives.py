import os

import pytest

from aqt.archives import QtArchives


@pytest.mark.parametrize("os_name,version,target,datafile", [
    ('windows', '5.15.0', 'win64_msvc2019_64', 'windows-5150-update.xml'),
    ('windows', '5.15.0', 'win64_mingw81', 'windows-5150-update.xml'),
    ('windows', '5.14.0', 'win64_mingw73', 'windows-5140-update.xml')
])
def test_parse_update_xml(monkeypatch, os_name, version, target, datafile):

    def _mock(self, url):
        with open(os.path.join(os.path.dirname(__file__), 'data', datafile), 'r') as f:
            self.update_xml_text = f.read()

    monkeypatch.setattr(QtArchives, "_download_update_xml", _mock)

    qt_archives = QtArchives(os_name, 'desktop', version, target)
    assert qt_archives.archives is not None

import os

import pytest

from aqt.archives import ToolArchives
from aqt.helper import Settings


@pytest.fixture(autouse=True)
def setup_settings():
    Settings.load_settings(os.path.join(os.path.dirname(__file__), "data", "settings.ini"))


def _stub_download_xml(self, *args, **kwargs):
    # Minimal valid Updates XML content; parsing is bypassed in these tests
    # because we monkeypatch _parse_update_xml.
    return "<Updates></Updates>"


@pytest.mark.parametrize(
    "os_name,target,tool_name,tool_version,expected_path",
    [
        (
            "linux",
            "desktop",
            "tools_ninja",
            None,
            "online/qtsdkrepository/linux_x64/desktop/tools_ninja",
        ),
        (
            "linux",
            "desktop",
            "tools_ifw",
            "tools_ifw410",
            "online/qtsdkrepository/linux_x64/ifw/tools_ifw410",
        ),
        (
            "linux",
            "desktop",
            "tools_ifw",
            "tools_ifw47",
            "online/qtsdkrepository/linux_x64/desktop/tools_ifw",
        ),
    ],
)
def test_tool_archives_repo_folder(monkeypatch, os_name, target, tool_name, tool_version, expected_path):
    # Capture the target folder passed to _parse_update_xml
    captured = {}

    def _capture_parse(self, os_target_folder, update_xml_text, *ignored):
        captured["folder"] = os_target_folder
        # Do nothing else; skip actual parsing for this test.
        return None

    # Avoid any network/file IO and ensure our capture is invoked
    monkeypatch.setattr(ToolArchives, "_download_update_xml", _stub_download_xml)
    monkeypatch.setattr(ToolArchives, "_parse_update_xml", _capture_parse)

    # Create the ToolArchives instance; __init__ triggers _get_archives()
    ToolArchives(os_name=os_name, target=target, tool_name=tool_name, base=Settings.baseurl, version_str=tool_version)

    assert captured["folder"] == expected_path

    # And that, when combined with base, it forms the expected URL root
    expected_url = f"{Settings.baseurl}/{expected_path}"
    assert expected_url.startswith("http")

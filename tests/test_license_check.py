import pytest

from aqt.license_check import GPL_ONLY, LGPL, UNKNOWN, check_modules, classify_description
from aqt.metadata import ModuleData

GPL_DESC = (
    "This component is available under commercial licenses from The Qt Company, or under "
    "GPL v3. For open source use, please note the additional requirements compared to LGPL v3."
)


@pytest.mark.parametrize(
    "description, expected",
    [
        ("", LGPL),
        (None, LGPL),
        ("   ", LGPL),
        (GPL_DESC, GPL_ONLY),
        ("Some unrelated marketing text about a great module.", UNKNOWN),
    ],
)
def test_classify_description(description, expected):
    assert classify_description(description) == expected


def test_check_modules_no_modules_requested_makes_no_network_call(monkeypatch):
    def fail(self, version, arch):
        raise AssertionError("should not be called when no modules are requested")

    monkeypatch.setattr("aqt.metadata.MetadataFactory.fetch_long_modules", fail)
    report = check_modules("linux", "desktop", "6.5.3", "gcc_64", [], base_url="https://example.invalid")
    assert report.verdicts == []
    assert report.is_clean


def test_check_modules_classifies_each_requested_module(monkeypatch):
    table = {
        "qtcharts": {"Description": GPL_DESC},
        "qtwebengine": {"Description": ""},
        "qtmystery": {"Description": "unrelated text"},
    }
    monkeypatch.setattr(
        "aqt.metadata.MetadataFactory.fetch_long_modules",
        lambda self, version, arch: ModuleData(table),
    )

    report = check_modules("linux", "desktop", "6.5.3", "gcc_64", ["qtcharts", "qtwebengine", "qtmystery"])
    statuses = {v.module: v.status for v in report.verdicts}
    assert statuses == {"qtcharts": GPL_ONLY, "qtwebengine": LGPL, "qtmystery": UNKNOWN}
    assert not report.is_clean


def test_check_modules_module_missing_from_metadata_is_unknown(monkeypatch):
    monkeypatch.setattr(
        "aqt.metadata.MetadataFactory.fetch_long_modules",
        lambda self, version, arch: ModuleData({}),
    )
    report = check_modules("linux", "desktop", "6.5.3", "gcc_64", ["does_not_exist"])
    assert report.verdicts[0].status == UNKNOWN
    assert not report.is_clean


def test_check_modules_all_expands_to_every_known_module(monkeypatch):
    table = {"qtcharts": {"Description": ""}, "qtwebsockets": {"Description": ""}}
    monkeypatch.setattr(
        "aqt.metadata.MetadataFactory.fetch_long_modules",
        lambda self, version, arch: ModuleData(table),
    )
    report = check_modules("linux", "desktop", "6.5.3", "gcc_64", ["all"])
    assert {v.module for v in report.verdicts} == {"qtcharts", "qtwebsockets"}
    assert report.is_clean


def test_check_modules_all_clean_report_is_clean(monkeypatch):
    monkeypatch.setattr(
        "aqt.metadata.MetadataFactory.fetch_long_modules",
        lambda self, version, arch: ModuleData({"qtcharts": {"Description": ""}}),
    )
    report = check_modules("linux", "desktop", "6.5.3", "gcc_64", ["qtcharts"])
    assert report.is_clean
    assert "OK (LGPL-eligible)" in report.format()

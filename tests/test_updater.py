import re
from tempfile import TemporaryDirectory

import pytest

from aqt.archives import TargetConfig
from aqt.exceptions import UpdaterError
from aqt.helper import Settings
from aqt.updater import Updater


@pytest.fixture(autouse=True)
def setup_settings():
    Settings.load_settings()


@pytest.mark.parametrize(
    "target_config, expected_err_pattern",
    (
        (
            TargetConfig("5.15.2", "winrt", "win64_msvc2019_winrt_x86", "windows"),
            re.compile(
                r"Updater caused an IO error: .*No such file or directory: "
                # '.*' wildcard used to match path separators on windows/*nix
                r".*5\.15\.2.*winrt_x86_msvc2019.*mkspecs.*qconfig.pri.*"
            ),
        ),
        (
            TargetConfig("5.15.2", "desktop", "win64_msvc2019_64", "windows"),
            re.compile(
                r"Updater caused an IO error: .*No such file or directory: "
                # '.*' wildcard used to match path separators on windows/*nix
                r".*5\.15\.2.*msvc2019_64.*mkspecs.*qconfig.pri.*"
            ),
        ),
        (
            TargetConfig("6.1.2", "desktop", "clang_64", "mac"),
            re.compile(
                r"Updater caused an IO error: .*No such file or directory: "
                # '.*' wildcard used to match path separators on windows/*nix
                r".*6\.1\.2.*macos.*mkspecs.*qconfig.pri.*"
            ),
        ),
        (
            TargetConfig("6.1.1", "desktop", "clang_64", "mac"),
            re.compile(
                r"Updater caused an IO error: .*No such file or directory: "
                # '.*' wildcard used to match path separators on windows/*nix
                r".*6\.1\.1.*clang_64.*mkspecs.*qconfig.pri.*"
            ),
        ),
    ),
)
def test_updater_update_license_io_error(monkeypatch, target_config: TargetConfig, expected_err_pattern: re.Pattern):
    """
    All of these tests will raise IOError when they attempt to patch the license file.
    """
    with pytest.raises(UpdaterError) as err:
        with TemporaryDirectory() as empty_dir:
            # Try to update a Qt installation that does not exist
            Updater.update(target_config, base_dir=empty_dir)
    assert err.type == UpdaterError
    err_msg = format(err.value)
    assert expected_err_pattern.match(err_msg)

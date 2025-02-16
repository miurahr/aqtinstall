import logging
import os
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest
import requests

from aqt.commercial import CommercialInstaller, QtPackageInfo, QtPackageManager
from aqt.exceptions import DiskAccessNotPermitted
from aqt.helper import Settings, get_qt_account_path
from aqt.installer import Cli
from aqt.metadata import Version


class CompletedProcess:
    def __init__(self, args, returncode):
        self.args = args
        self.returncode = returncode
        self.stdout = None
        self.stderr = None


# Test data
MOCK_XML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<availablepackages>
    <package name="qt.qt6.680.gcc_64" displayname="Desktop gcc" version="6.8.0-0-202312011"/>
    <package name="qt.qt6.680.addons.qtquick3d" displayname="Qt Quick 3D" version="6.8.0-0-202312011"/>
</availablepackages>"""

TEST_EMAIL = os.getenv("AQT_TEST_EMAIL")
TEST_PASSWORD = os.getenv("AQT_TEST_PASSWORD")


class MockResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"", text: str = "", headers: Dict = None):
        self.status_code = status_code
        self.content = content
        self.text = text
        self.headers = headers or {}
        self.ok = status_code == 200

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f"HTTP Error: {self.status_code}")

    def iter_content(self, chunk_size=None):
        yield self.content


@pytest.fixture
def mock_settings(monkeypatch):
    """Setup test settings"""
    # Instead of trying to set properties directly, we should mock the property getter
    monkeypatch.setattr(Settings, "qt_installer_timeout", property(lambda self: 60))
    monkeypatch.setattr(Settings, "qt_installer_cache_path", property(lambda self: str(Path.home() / ".qt" / "cache")))
    monkeypatch.setattr(Settings, "qt_installer_temp_path", property(lambda self: str(Path.home() / ".qt" / "temp")))


@pytest.fixture
def commercial_installer():
    return CommercialInstaller(
        target="desktop",
        arch="gcc_64",
        version="6.8.0",
        username=TEST_EMAIL,
        password=TEST_PASSWORD,
        output_dir="./test_output",
    )


@pytest.mark.enable_socket
@pytest.mark.parametrize(
    "cmd, expected_arch, expected_err",
    [
        pytest.param(
            "install-qt-commercial desktop {} 6.8.0",
            {"windows": "win64_msvc2022_64", "linux": "linux_gcc_64", "mac": "clang_64"},
            "No Qt account credentials found",
        ),
    ],
)
def test_cli_login_qt_commercial(capsys, monkeypatch, cmd, expected_arch, expected_err):
    """Test commercial Qt installation command"""
    # Detect current platform
    current_platform = sys.platform.lower()
    arch = expected_arch[current_platform]
    cmd = cmd.format(arch)

    if get_qt_account_path().exists():
        os.remove(get_qt_account_path())

    cli = Cli()
    cli._setup_settings()
    cli.run(cmd.split())

    out, err = capsys.readouterr()
    assert expected_err in err or expected_err in out


def test_package_manager_init():
    """Test QtPackageManager initialization"""
    manager = QtPackageManager(
        arch="gcc_64",
        version=Version("6.8.0"),
        target="desktop",
        username=TEST_EMAIL,
        password=TEST_PASSWORD,
    )
    assert manager.arch == "gcc_64"
    assert str(manager.version) == "6.8.0"
    assert manager.target == "desktop"
    assert manager.username == TEST_EMAIL
    assert manager.password == TEST_PASSWORD


@pytest.mark.parametrize(
    "xml_content, expected_packages",
    [
        (
            MOCK_XML_RESPONSE,
            [
                QtPackageInfo(name="qt.qt6.680.gcc_64", displayname="Desktop gcc", version="6.8.0-0-202312011"),
                QtPackageInfo(name="qt.qt6.680.addons.qtquick3d", displayname="Qt Quick 3D", version="6.8.0-0-202312011"),
            ],
        )
    ],
)
def test_parse_packages_xml(xml_content: str, expected_packages: List[QtPackageInfo]):
    """Test parsing of package XML data"""
    manager = QtPackageManager(arch="gcc_64", version=Version("6.8.0"), target="desktop")
    manager._parse_packages_xml(xml_content)

    assert len(manager.packages) == len(expected_packages)
    for actual, expected in zip(manager.packages, expected_packages):
        assert actual.name == expected.name
        assert actual.displayname == expected.displayname
        assert actual.version == expected.version


def test_commercial_installer_auto_answers():
    """Test generation of auto-answer options"""
    auto_answers = CommercialInstaller.get_auto_answers()
    assert "OperationDoesNotExistError=Ignore" in auto_answers
    assert "OverwriteTargetDirectory=No" in auto_answers
    assert "telemetry-question=No" in auto_answers


@pytest.mark.parametrize(
    "installer_path, override, username, password, output_dir, no_unattended, expected_cmd",
    [
        (
            "/path/to/installer",
            None,
            "user",
            "pass",
            "./output",
            False,
            [
                "/path/to/installer",
                "--accept-licenses",
                "--accept-obligations",
                "--confirm-command",
                "--email",
                "user",
                "--pw",
                "pass",
                "--root",
                str(Path("./output").absolute()),
                "--auto-answer",
                CommercialInstaller.get_auto_answers(),
            ],
        ),
        (
            "/path/to/installer",
            ["--override", "arg1", "arg2"],
            None,
            None,
            None,
            True,
            ["/path/to/installer", "--override", "arg1", "arg2"],
        ),
    ],
)
def test_build_command(
    installer_path: str,
    override: Optional[List[str]],
    username: Optional[str],
    password: Optional[str],
    output_dir: Optional[str],
    no_unattended: bool,
    expected_cmd: List[str],
):
    """Test building of installer command"""
    cmd = CommercialInstaller.build_command(
        installer_path,
        override=override,
        username=username,
        password=password,
        output_dir=output_dir,
        no_unattended=no_unattended,
    )
    assert cmd == expected_cmd


@pytest.mark.enable_socket
def test_commercial_installer_download(monkeypatch, commercial_installer):
    """Test downloading of commercial installer"""

    def mock_requests_get(*args, **kwargs):
        return MockResponse(content=b"installer_content")

    monkeypatch.setattr(requests, "get", mock_requests_get)

    with TemporaryDirectory() as temp_dir:
        target_path = Path(temp_dir) / "qt-installer"
        commercial_installer.download_installer(target_path, timeout=60)
        assert target_path.exists()
        assert target_path.read_bytes() == b"installer_content"


@pytest.mark.parametrize(
    "modules, expected_command",
    [
        (None, ["install", "qt.qt6.680.gcc_64"]),
        (["qtquick3d"], ["install", "qt.qt6.680.gcc_64", "qt.qt6.680.addons.qtquick3d"]),
        (["all"], ["install", "qt.qt6.680.gcc_64", "qt.qt6.680.addons.qtquick3d"]),
    ],
)
def test_get_install_command(monkeypatch, modules: Optional[List[str]], expected_command: List[str]):
    """Test generation of install commands"""
    manager = QtPackageManager(arch="gcc_64", version=Version("6.8.0"), target="desktop")

    def mock_gather_packages(self, installer_path: str) -> None:
        self.packages = [
            QtPackageInfo(name="qt.qt6.680.gcc_64", displayname="Desktop gcc", version="6.8.0"),
            QtPackageInfo(name="qt.qt6.680.addons.qtquick3d", displayname="Qt Quick 3D", version="6.8.0"),
        ]

    monkeypatch.setattr(QtPackageManager, "gather_packages", mock_gather_packages)

    command = manager.get_install_command(modules, "./temp")
    assert command == expected_command


@pytest.mark.enable_socket
@pytest.mark.parametrize(
    "cmd, arch_dict, details, expected_command",
    [
        (
            "install-qt-commercial desktop {} 6.8.1 " "--outputdir ./install-qt-commercial --email {} --pw {}",
            {"windows": "win64_msvc2022_64", "linux": "linux_gcc_64", "mac": "clang_64"},
            ["./install-qt-commercial", "qt6", "681"],
            "qt-unified-{}-x64-online.run --email ******** --pw ******** --root {} "
            "--accept-licenses --accept-obligations "
            "--confirm-command "
            "--auto-answer OperationDoesNotExistError=Ignore,OverwriteTargetDirectory=No,"
            "stopProcessesForUpdates=Cancel,installationErrorWithCancel=Cancel,installationErrorWithIgnore=Ignore,"
            "AssociateCommonFiletypes=Yes,telemetry-question=No install qt.{}.{}.{}",
        ),
        (
            "install-qt-commercial desktop {} 6.8.1 --outputdir ./install-qt-commercial --email {} --pw {}",
            {"windows": "win64_msvc2022_64", "linux": "linux_gcc_64", "mac": "clang_64"},
            ["./install-qt-commercial", "qt6", "681"],
            "qt-unified-{}-x64-online.run --email ******** --pw ******** --root {} "
            "--accept-licenses --accept-obligations "
            "--confirm-command "
            "--auto-answer OperationDoesNotExistError=Ignore,OverwriteTargetDirectory=Yes,"
            "stopProcessesForUpdates=Cancel,installationErrorWithCancel=Cancel,installationErrorWithIgnore=Ignore,"
            "AssociateCommonFiletypes=Yes,telemetry-question=No install qt.{}.{}.{}",
        ),
    ],
)
def test_install_qt_commercial(
    capsys, monkeypatch, cmd: str, arch_dict: dict[str, str], details: list[str], expected_command: str
) -> None:
    """Test commercial Qt installation command"""

    def mock_safely_run(*args, **kwargs):
        return CompletedProcess(args=args[0], returncode=0)

    monkeypatch.setattr("aqt.commercial.safely_run", mock_safely_run)

    current_platform = sys.platform.lower()
    arch = arch_dict[current_platform]

    abs_out = Path(details[0]).absolute()

    # Get the email and password from the test parameters
    email = TEST_EMAIL
    password = TEST_PASSWORD

    formatted_cmd = cmd.format(arch, email, password)
    formatted_expected = expected_command.format(current_platform, abs_out, *details[1:], arch)

    cli = Cli()
    cli._setup_settings()

    # First test the normal installation command
    try:
        cli.run(formatted_cmd.split())
    except AttributeError:
        out = " ".join(capsys.readouterr())
        assert str(out).find(formatted_expected) >= 0

    abs_out.joinpath(f"6.8.{str(details[2])[-1]}").mkdir(exist_ok=True, parents=True)

    # Create a new command with the temp directory
    new_cmd = (
        f"install-qt-commercial desktop {arch} 6.8.{str(details[2])[-1]} --outputdir {abs_out} --email {email} "
        f"--pw {password}"
    )

    # This should raise DiskAccessNotPermitted only for the first test (680)
    if details[2] == "680":
        with pytest.raises(DiskAccessNotPermitted) as exc_info:
            cli.run(new_cmd.split())
        assert "Target directory" in str(exc_info.value)
        assert "already exists" in str(exc_info.value)
    else:
        cli.run(new_cmd.split())

    def modify_qt_config(content):
        """
        Takes content of INI file as string and returns modified content
        """
        lines = content.splitlines()
        in_qt_commercial = False
        modified = []

        for line in lines:
            # Check if we're entering qtcommercial section
            if line.strip() == "[qtcommercial]":
                in_qt_commercial = True

            # If in qtcommercial section, look for the target line
            if in_qt_commercial and "overwrite_target_directory : No" in line:
                line = "overwrite_target_directory : Yes"
            elif in_qt_commercial and "overwrite_target_directory : Yes" in line:
                line = "overwrite_target_directory : No"

            modified.append(line)

        return "\n".join(modified)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "../aqt/settings.ini")

    with open(config_path, "r") as f:
        content = f.read()

    modified_content = modify_qt_config(content)

    with open(config_path, "w") as f:
        f.write(modified_content)
        Settings._initialize()

    shutil.rmtree(abs_out)


def create_mock_process(stdout):
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = 0
    return mock


def test_commercial_commands(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # Mock filesystem operations
    def mock_mkdir(*args, **kwargs):
        return None

    monkeypatch.setattr(Path, "mkdir", mock_mkdir)
    monkeypatch.setattr(Path, "exists", lambda x: False)

    # Mock subprocess run to return our predefined output
    sample_output = "Name: qt6.8.1-full"

    def mock_safely_run_save_output(cmd, timeout):
        return create_mock_process(sample_output)

    def mock_safely_run(cmd, timeout):
        return None

    monkeypatch.setattr("aqt.helper.safely_run_save_output", mock_safely_run_save_output)
    monkeypatch.setattr("aqt.helper.safely_run", mock_safely_run)

    # Mock requests for installer download
    def mock_get(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.raise_for_status = lambda: None
        mock_response.iter_content = lambda chunk_size: [b"mock data"]
        return mock_response

    monkeypatch.setattr("requests.get", mock_get)

    # Mock file operations
    mock_open = MagicMock()
    monkeypatch.setattr("builtins.open", mock_open)

    # Test list-qt-commercial command
    from aqt.installer import Cli

    cli = Cli()
    cli._setup_settings()
    list_args = ["list-qt-commercial", "--email", str(TEST_EMAIL), "--pw", str(TEST_PASSWORD), "6.8.1"]
    cli.run(list_args)

    # Verify key outputs in logs
    assert any("aqtinstall(aqt)" in record.message for record in caplog.records)
    assert any("Downloading Qt installer" in record.message for record in caplog.records)

    # Clear logs for next test
    caplog.clear()

    # Test install-qt-commercial command
    install_args = [
        "install-qt-commercial",
        "--override",
        "search",
        "6.8.0",
        "--email",
        str(TEST_EMAIL),
        "--pw",
        str(TEST_PASSWORD),
    ]
    cli.run(install_args)

    # Verify key outputs in logs
    assert any("Qt installation completed successfully" in record.message for record in caplog.records)
    assert any("Done" in record.message for record in caplog.records)


@pytest.mark.parametrize(
    "args, expected_error",
    [
        (["list-qt-commercial", "--bad-flag"], "usage: aqt [-h] [-c CONFIG]"),
    ],
)
def test_list_qt_commercial_errors(capsys, args, expected_error):
    """Test error handling in list-qt-commercial command"""
    cli = Cli()
    with pytest.raises(SystemExit):
        cli.run(args)
    _, err = capsys.readouterr()
    assert expected_error in err

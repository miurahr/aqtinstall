import os
import platform
import subprocess
import tempfile
from logging import Logger, getLogger
from pathlib import Path
from sys import platform
from typing import Optional

import requests

from aqt.metadata import Version


class CommercialInstaller:
    ALLOWED_INSTALLERS = {
        "windows": "qt-unified-windows-x64-online.exe",
        "mac": "qt-unified-macOS-x64-online.dmg",
        "linux": "qt-unified-linux-x64-online.run",
    }

    ALLOWED_AUTO_ANSWER_OPTIONS = {
        "OperationDoesNotExistError": frozenset({"Abort", "Ignore"}),
        "OverwriteTargetDirectory": frozenset({"Yes", "No"}),
        "stopProcessesForUpdates": frozenset({"Retry", "Ignore", "Cancel"}),
        "installationErrorWithCancel": frozenset({"Retry", "Ignore", "Cancel"}),
        "installationErrorWithIgnore": frozenset({"Retry", "Ignore"}),
        "AssociateCommonFiletypes": frozenset({"Yes", "No"}),
        "telemetry-question": frozenset({"Yes", "No"}),
    }

    def __init__(
        self,
        target: str,
        arch: Optional[str],
        version: Optional[str],
        username: Optional[str] = None,
        password: Optional[str] = None,
        output_dir: Optional[str] = None,
        logger: Optional[Logger] = None,
        timeout: Optional[float] = None,
        base_url: str = "https://download.qt.io",
        operation_does_not_exist_error="Ignore",
        overwrite_target_dir: str = "Yes",
        stop_processes_for_updates: str = "Cancel",
        installation_error_with_cancel: str = "Cancel",
        installation_error_with_ignore: str = "Ignore",
        associate_common_filetypes: str = "Yes",
        telemetry: str = "No",
    ):
        self.target = target
        self.arch = arch or ""
        self.version = Version(version) if version else Version()
        self.username = username
        self.password = password
        self.output_dir = output_dir
        self.logger = logger or getLogger(__name__)
        self.timeout = int(timeout) if timeout else 3600
        self.base_url = base_url

        # Store auto-answer options
        self.operation_does_not_exist_error = operation_does_not_exist_error
        self.overwrite_target_dir = overwrite_target_dir
        self.stop_processes_for_updates = stop_processes_for_updates
        self.installation_error_with_cancel = installation_error_with_cancel
        self.installation_error_with_ignore = installation_error_with_ignore
        self.associate_common_filetypes = associate_common_filetypes
        self.telemetry = telemetry

        # Set OS-specific properties
        self.os_name = self._get_os_name()
        self.installer_filename = self.ALLOWED_INSTALLERS[self.os_name]
        self.qt_account = self._get_qt_account_path()

    def _get_os_name(self) -> str:
        system = platform.system()
        if system == "Darwin":
            return "mac"
        elif system == "Linux":
            return "linux"
        elif system == "Windows":
            return "windows"
        else:
            raise ValueError(f"Unsupported operating system: {system}")

    def _get_qt_account_path(self) -> Path:
        if self.os_name == "windows":
            appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
            return Path(appdata) / "Qt" / "qtaccount.ini"
        elif self.os_name == "mac":
            return Path.home() / "Library" / "Application Support" / "Qt" / "qtaccount.ini"
        else:  # Linux
            return Path.home() / ".local" / "share" / "Qt" / "qtaccount.ini"

    def _download_installer(self, target_path: Path) -> None:
        url = f"{self.base_url}/official_releases/online_installers/{self.installer_filename}"
        try:
            response = requests.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()

            with open(target_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            if self.os_name != "windows":
                os.chmod(target_path, 0o700)
        except Exception as e:
            raise RuntimeError(f"Failed to download installer: {e}")

    def _get_package_name(self) -> str:
        qt_version = f"{self.version.major}{self.version.minor}{self.version.patch}"
        return f"qt.qt{self.version.major}.{qt_version}.{self.arch}"

    def _exec_qt_installer(self, cmd: list[str], working_dir: str) -> None:
        """Execute the Qt installer command with proper path handling and security"""

    def _get_install_command(self, installer_path: Path) -> list[str]:
        """Build the installation command array"""
        # Start with installer path (will be replaced with absolute path in _exec_qt_installer)
        cmd = [str(installer_path)]

        # Add authentication if provided
        if self.username and self.password:
            cmd.extend(["--email", self.username, "--pw", self.password])

        # Add output directory if specified
        if self.output_dir:
            output_path = Path(self.output_dir).resolve()
            output_path.mkdir(parents=True, exist_ok=True)
            cmd.extend(["--root", str(output_path)])

        # Add standard installation options
        cmd.extend(
            [
                "--accept-licenses",
                "--accept-obligations",
                "--confirm-command",
            ]
        )

        # Build auto-answer options
        auto_answers = []
        auto_answer_map = {
            "OperationDoesNotExistError": self.operation_does_not_exist_error,
            "OverwriteTargetDirectory": self.overwrite_target_dir,
            "stopProcessesForUpdates": self.stop_processes_for_updates,
            "installationErrorWithCancel": self.installation_error_with_cancel,
            "installationErrorWithIgnore": self.installation_error_with_ignore,
            "AssociateCommonFiletypes": self.associate_common_filetypes,
            "telemetry-question": self.telemetry,
        }

        for key, value in auto_answer_map.items():
            if key in self.ALLOWED_AUTO_ANSWER_OPTIONS and value in self.ALLOWED_AUTO_ANSWER_OPTIONS[key]:
                auto_answers.append(f"{key}={value}")

        if not auto_answers:
            raise ValueError("No valid auto-answer options provided")

        cmd.extend(["--auto-answer", ",".join(auto_answers)])

        # Add install command and package
        cmd.extend(["install", self._get_package_name()])

        return cmd

    def install(self) -> None:
        if (
            not self.qt_account.exists()
            and not (self.username and self.password)
            and os.environ.get("QT_INSTALLER_JWT_TOKEN") == ""
        ):
            raise RuntimeError(
                "No Qt account credentials found. Provide username and password or ensure qtaccount.ini exists."
            )

        with tempfile.TemporaryDirectory(prefix="qt_install_") as temp_dir:
            temp_path = Path(temp_dir)
            os.chmod(temp_dir, 0o700)

            installer_path = temp_path / self.installer_filename
            self.logger.info(f"Downloading Qt installer to {installer_path}")
            self._download_installer(installer_path)

            try:
                cmd = self._get_install_command(installer_path)
                safe_cmd = cmd.copy()
                if "--pw" in safe_cmd:
                    pw_index = safe_cmd.index("--pw")
                    if len(safe_cmd) > pw_index + 1:
                        safe_cmd[pw_index + 1] = "********"
                if "--email" in safe_cmd:
                    email_index = safe_cmd.index("--email")
                    if len(safe_cmd) > email_index + 1:
                        safe_cmd[email_index + 1] = "********"
                self.logger.info(f"Running: {' '.join(safe_cmd)}")

                subprocess.run(cmd, shell=False, check=True, cwd=temp_dir)

            except subprocess.CalledProcessError as e:
                self.logger.error(f"Installation failed with exit code {e.returncode}")
            except subprocess.TimeoutExpired:
                self.logger.error("Installation timed out")
            finally:
                if installer_path.exists():
                    installer_path.unlink()
                self.logger.info("Qt installation completed successfully")

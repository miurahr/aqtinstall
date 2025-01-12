import json
import os
import platform
import subprocess
import tempfile
from dataclasses import dataclass
from logging import Logger, getLogger
from pathlib import Path
from typing import List, Optional

import requests
from defusedxml import ElementTree

from aqt.helper import Settings
from aqt.metadata import Version


@dataclass
class QtPackageInfo:
    name: str
    displayname: str
    version: str


class QtPackageManager:
    def __init__(self, arch: str, version: Version, target: str, temp_dir: str):
        self.arch = arch
        self.version = version
        self.target = target
        self.temp_dir = temp_dir
        self.cache_dir = self._get_cache_dir()
        self.packages: List[QtPackageInfo] = []

    def _get_cache_dir(self) -> Path:
        """Create and return cache directory path."""
        base_cache = Path.home() / ".cache" / "aqt"
        cache_path = base_cache / self.target / self.arch / str(self.version)
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path

    def _get_cache_file(self) -> Path:
        """Get the cache file path."""
        return self.cache_dir / "packages.json"

    def _save_to_cache(self) -> None:
        """Save packages information to cache."""
        cache_data = [{"name": pkg.name, "displayname": pkg.displayname, "version": pkg.version} for pkg in self.packages]

        with open(self._get_cache_file(), "w") as f:
            json.dump(cache_data, f, indent=2)

    def _load_from_cache(self) -> bool:
        """Load packages information from cache if available."""
        cache_file = self._get_cache_file()
        if not cache_file.exists():
            return False

        try:
            with open(cache_file, "r") as f:
                cache_data = json.load(f)
                self.packages = [
                    QtPackageInfo(name=pkg["name"], displayname=pkg["displayname"], version=pkg["version"])
                    for pkg in cache_data
                ]
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def _parse_packages_xml(self, xml_content: str) -> None:
        """Parse packages XML content and extract package information using defusedxml."""
        try:
            # Use defusedxml.ElementTree to safely parse the XML content
            root = ElementTree.fromstring(xml_content)
            self.packages = []

            # Find all package elements using XPath-like expression
            # Note: defusedxml supports a subset of XPath
            for pkg in root.findall(".//package"):
                name = pkg.get("name", "")
                displayname = pkg.get("displayname", "")
                version = pkg.get("version", "")

                if all([name, displayname, version]):  # Ensure all required attributes are present
                    self.packages.append(QtPackageInfo(name=name, displayname=displayname, version=version))
        except ElementTree.ParseError as e:
            raise RuntimeError(f"Failed to parse package XML: {e}")

    def _get_version_string(self) -> str:
        """Get formatted version string for package names."""
        return f"{self.version.major}{self.version.minor}{self.version.patch}"

    def _get_base_package_name(self) -> str:
        """Get the base package name for the current configuration."""
        version_str = self._get_version_string()
        return f"qt.qt{self.version.major}.{version_str}"

    def gather_packages(self, installer_path: str) -> None:
        """Gather package information using qt installer search command."""
        if self._load_from_cache():
            return

        version_str = self._get_version_string()
        base_package = f"qt.qt{self.version.major}.{version_str}"

        cmd = [
            installer_path,
            "--accept-licenses",
            "--accept-obligations",
            "--confirm-command",
            "--default-answer",
            "search",
            base_package,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Extract the XML portion from the output
            xml_start = result.stdout.find("<availablepackages>")
            xml_end = result.stdout.find("</availablepackages>") + len("</availablepackages>")

            if xml_start != -1 and xml_end != -1:
                xml_content = result.stdout[xml_start:xml_end]
                self._parse_packages_xml(xml_content)
                self._save_to_cache()
            else:
                raise RuntimeError("Failed to find package information in installer output")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to gather packages: {e}")

    def get_install_command(self, modules: Optional[List[str]], install_path: str) -> List[str]:
        """Generate installation command based on requested modules."""
        version_str = self._get_version_string()

        # If 'all' is in modules, use the -full package
        if modules and "all" in modules:
            package_name = f"{self._get_base_package_name()}.{self.arch}-full"
        else:
            # Base package name
            package_name = f"{self._get_base_package_name()}.{self.arch}"

        cmd = [
            "--root",
            install_path,
            "--accept-licenses",
            "--accept-obligations",
            "--confirm-command",
            "--auto-answer",
            "OperationDoesNotExistError=Ignore,OverwriteTargetDirectory=No,"
            "stopProcessesForUpdates=Cancel,installationErrorWithCancel=Cancel,"
            "installationErrorWithIgnore=Ignore,AssociateCommonFiletypes=Yes,"
            "telemetry-question=No",
            "install",
            package_name,
        ]

        # Add individual modules if specified and not using 'all'
        if modules and "all" not in modules:
            for module in modules:
                module_pkg = f"{self._get_base_package_name()}.addons.{module}"
                if any(p.name == module_pkg for p in self.packages):
                    cmd.append(module_pkg)

        return cmd


class CommercialInstaller:
    """Qt Commercial installer that handles module installation and package management."""

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

    UNATTENDED_FLAGS = frozenset(
        [
            "--accept-licenses",
            "--accept-obligations",
            "--confirm-command",
        ]
    )

    def __init__(
        self,
        target: str,
        arch: Optional[str],
        version: Optional[str],
        username: Optional[str] = None,
        password: Optional[str] = None,
        output_dir: Optional[str] = None,
        logger: Optional[Logger] = None,
        base_url: str = "https://download.qt.io",
        override: Optional[list[str]] = None,
        modules: Optional[List[str]] = None,
        no_unattended: bool = False,
    ):
        self.override = override
        self.target = target
        self.arch = arch or ""
        self.version = Version(version) if version else Version("0.0.0")
        self.username = username
        self.password = password
        self.output_dir = output_dir
        self.logger = logger or getLogger(__name__)
        self.base_url = base_url
        self.modules = modules
        self.no_unattended = no_unattended

        # Set OS-specific properties
        self.os_name = CommercialInstaller._get_os_name()
        self._installer_filename = CommercialInstaller._get_qt_installer_name()
        self.qt_account = CommercialInstaller._get_qt_account_path()
        self.package_manager = QtPackageManager(self.arch, self.version, self.target, Settings.qt_installer_cache_path)

    @staticmethod
    def get_auto_answers() -> str:
        """Get auto-answer options from settings."""
        settings_map = {
            "OperationDoesNotExistError": Settings.qt_installer_operationdoesnotexisterror,
            "OverwriteTargetDirectory": Settings.qt_installer_overwritetargetdirectory,
            "stopProcessesForUpdates": Settings.qt_installer_stopprocessesforupdates,
            "installationErrorWithCancel": Settings.qt_installer_installationerrorwithcancel,
            "installationErrorWithIgnore": Settings.qt_installer_installationerrorwithignore,
            "AssociateCommonFiletypes": Settings.qt_installer_associatecommonfiletypes,
            "telemetry-question": Settings.qt_installer_telemetry,
        }

        answers = []
        for key, value in settings_map.items():
            if value in CommercialInstaller.ALLOWED_AUTO_ANSWER_OPTIONS[key]:
                answers.append(f"{key}={value}")

        return ",".join(answers)

    @staticmethod
    def build_command(
        installer_path: str,
        override: Optional[List[str]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        output_dir: Optional[str] = None,
        no_unattended: bool = False,
    ) -> List[str]:
        """Build the installation command with proper safeguards."""
        cmd = [installer_path]

        # Add unattended flags unless explicitly disabled
        if not no_unattended:
            cmd.extend(CommercialInstaller.UNATTENDED_FLAGS)

        if override:
            # When using override, still include unattended flags unless disabled
            cmd.extend(override)
            return cmd

        # Add authentication if provided
        if username and password:
            cmd.extend(["--email", username, "--pw", password])

        # Add output directory if specified
        if output_dir:
            cmd.extend(["--root", str(Path(output_dir).resolve())])

        # Add auto-answer options from settings
        auto_answers = CommercialInstaller.get_auto_answers()
        if auto_answers:
            cmd.extend(["--auto-answer", auto_answers])

        return cmd

    def install(self) -> None:
        """Run the Qt installation process."""
        if (
            not self.qt_account.exists()
            and not (self.username and self.password)
            and not os.environ.get("QT_INSTALLER_JWT_TOKEN")
        ):
            raise RuntimeError(
                "No Qt account credentials found. Provide username and password or ensure qtaccount.ini exists."
            )

        cache_path = Path(Settings.qt_installer_cache_path)
        cache_path.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="qt_install_") as temp_dir:
            temp_path = Path(temp_dir)
            installer_path = temp_path / self._installer_filename

            self.logger.info(f"Downloading Qt installer to {installer_path}")
            self.download_installer(installer_path, Settings.qt_installer_timeout)

            try:
                cmd = None
                if self.override:
                    cmd = self.build_command(str(installer_path), override=self.override, no_unattended=self.no_unattended)
                else:
                    # Initialize package manager and gather packages
                    self.package_manager.gather_packages(str(installer_path))

                    base_cmd = self.build_command(
                        str(installer_path),
                        username=self.username,
                        password=self.password,
                        output_dir=self.output_dir,
                        no_unattended=self.no_unattended,
                    )

                    cmd = base_cmd + self.package_manager.get_install_command(self.modules, self.output_dir or os.getcwd())

                self.logger.info(f"Running: {' '.join(cmd)}")

                try:
                    subprocess.run(cmd, shell=False, check=True, cwd=temp_dir, timeout=Settings.qt_installer_timeout)
                except subprocess.TimeoutExpired:
                    self.logger.error(f"Installation timed out after {Settings.qt_installer_timeout} seconds")
                    raise
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Installation failed with exit code {e.returncode}")
                    raise

                self.logger.info("Qt installation completed successfully")

            finally:
                if installer_path.exists():
                    installer_path.unlink()

    @staticmethod
    def _get_os_name() -> str:
        system = platform.system()
        if system == "Darwin":
            return "mac"
        if system == "Linux":
            return "linux"
        if system == "Windows":
            return "windows"
        raise ValueError(f"Unsupported operating system: {system}")

    @staticmethod
    def _get_qt_local_folder_path() -> Path:
        os_name = CommercialInstaller._get_os_name()
        if os_name == "windows":
            appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
            return Path(appdata) / "Qt"
        if os_name == "mac":
            return Path.home() / "Library" / "Application Support" / "Qt"
        return Path.home() / ".local" / "share" / "Qt"

    @staticmethod
    def _get_qt_account_path() -> Path:
        return CommercialInstaller._get_qt_local_folder_path() / "qtaccount.ini"

    @staticmethod
    def _get_qt_installer_name() -> str:
        installer_dict = {
            "windows": "qt-unified-windows-x64-online.exe",
            "mac": "qt-unified-macOS-x64-online.dmg",
            "linux": "qt-unified-linux-x64-online.run",
        }
        return installer_dict[CommercialInstaller._get_os_name()]

    @staticmethod
    def _get_qt_installer_path() -> Path:
        return CommercialInstaller._get_qt_local_folder_path() / CommercialInstaller._get_qt_installer_name()

    def download_installer(self, target_path: Path, timeout: int) -> None:
        url = f"{self.base_url}/official_releases/online_installers/{self._installer_filename}"
        try:
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()

            with open(target_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            if self.os_name != "windows":
                os.chmod(target_path, 0o500)
        except Exception as e:
            raise RuntimeError(f"Failed to download installer: {e}")

    def _get_package_name(self) -> str:
        qt_version = f"{self.version.major}{self.version.minor}{self.version.patch}"
        return f"qt.qt{self.version.major}.{qt_version}.{self.arch}"

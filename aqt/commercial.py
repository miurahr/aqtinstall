import json
import os
from dataclasses import dataclass
from logging import Logger, getLogger
from pathlib import Path
from typing import List, Optional

import requests
from defusedxml import ElementTree

from aqt.exceptions import DiskAccessNotPermitted
from aqt.helper import Settings, get_os_name, get_qt_account_path, get_qt_installer_name, safely_run, safely_run_save_output
from aqt.metadata import Version


@dataclass
class QtPackageInfo:
    name: str
    displayname: str
    version: str


class QtPackageManager:
    def __init__(self, arch: str, version: Version, target: str):
        self.arch = arch
        self.version = version
        self.target = target
        self.cache_dir = self._get_cache_dir()
        self.packages: List[QtPackageInfo] = []

    def _get_cache_dir(self) -> Path:
        """Create and return cache directory path."""
        base_cache = Settings.qt_installer_cache_path
        cache_path = os.path.join(base_cache, self.target, self.arch, str(self.version))
        Path(cache_path).mkdir(parents=True, exist_ok=True)
        return Path(cache_path)

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
            output = safely_run_save_output(installer_path, cmd, Settings.qt_installer_timeout)

            # Extract the XML portion from the output
            xml_start = output.find("<availablepackages>")
            xml_end = output.find("</availablepackages>") + len("</availablepackages>")

            if xml_start != -1 and xml_end != -1:
                xml_content = output[xml_start:xml_end]
                self._parse_packages_xml(xml_content)
                self._save_to_cache()
            else:
                raise RuntimeError("Failed to find package information in installer output")

        except Exception as e:
            raise RuntimeError(f"Failed to get package information: {e}")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to gather packages: {e}")

    def get_install_command(self, modules: Optional[List[str]], temp_dir: str) -> List[str]:
        """Generate installation command based on requested modules."""
        package_name = f"{self._get_base_package_name()}.{self.arch}"
        cmd = ["install", package_name]

        # No modules requested, return base package only
        if not modules:
            return cmd

        # Ensure package cache exists
        self.gather_packages(temp_dir)

        if "all" in modules:
            # Find all addon and direct module packages
            for pkg in self.packages:
                if f"{self._get_base_package_name()}.addons." in pkg.name or pkg.name.startswith(
                    f"{self._get_base_package_name()}."
                ):
                    module_name = pkg.name.split(".")[-1]
                    if module_name != self.arch:  # Skip the base package
                        cmd.append(pkg.name)
        else:
            # Add specifically requested modules that exist in either format
            for module in modules:
                addon_name = f"{self._get_base_package_name()}.addons.{module}"
                direct_name = f"{self._get_base_package_name()}.{module}"

                # Check if either package name exists
                matching_pkg = next(
                    (pkg.name for pkg in self.packages if pkg.name == addon_name or pkg.name == direct_name), None
                )

                if matching_pkg:
                    cmd.append(matching_pkg)

        return cmd


class CommercialInstaller:
    """Qt Commercial installer that handles module installation and package management."""

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
        self.os_name = get_os_name()
        self._installer_filename = get_qt_installer_name()
        self.qt_account = get_qt_account_path()
        self.package_manager = QtPackageManager(self.arch, self.version, self.target)

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
            cmd.extend(["--accept-licenses", "--accept-obligations", "--confirm-command"])

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

        # Check output directory if specified
        if self.output_dir:
            output_path = Path(self.output_dir) / str(self.version)
            if output_path.exists():
                if Settings.qt_installer_overwritetargetdirectory.lower() == "yes":
                    self.logger.warning(f"Target directory {output_path} exists - removing as overwrite is enabled")
                    try:
                        import shutil

                        shutil.rmtree(output_path)
                    except (OSError, PermissionError) as e:
                        raise DiskAccessNotPermitted(f"Failed to remove existing target directory {output_path}: {str(e)}")
                else:
                    msg = (
                        f"Target directory {output_path} already exists. "
                        "Set overwrite_target_directory='Yes' in settings.ini to overwrite, or select another directory."
                    )
                    raise DiskAccessNotPermitted(msg)

        # Setup cache directory
        cache_path = Path(Settings.qt_installer_cache_path)
        cache_path.mkdir(parents=True, exist_ok=True)

        import shutil

        temp_dir = Settings.qt_installer_temp_path
        temp_path = Path(temp_dir)
        if temp_path.exists():
            shutil.rmtree(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)
        installer_path = temp_path / self._installer_filename

        self.logger.info(f"Downloading Qt installer to {installer_path}")
        self.download_installer(installer_path, Settings.qt_installer_timeout)

        try:
            cmd = []
            if self.override:
                cmd = self.build_command(str(installer_path), override=self.override, no_unattended=self.no_unattended)
            else:
                # Initialize package manager and gather packages
                self.package_manager.gather_packages(str(installer_path))

                base_cmd = self.build_command(
                    str(installer_path.absolute()),
                    username=self.username,
                    password=self.password,
                    output_dir=self.output_dir,
                    no_unattended=self.no_unattended,
                )

                cmd = [
                    *base_cmd,
                    *self.package_manager.get_install_command(self.modules, temp_dir),
                ]

            self.logger.info(f"Running: {cmd}")

            safely_run(installer_path, cmd, Settings.qt_installer_timeout)
        except Exception as e:
            self.logger.error(f"Installation failed with exit code {e.__str__()}")
            raise
        finally:
            self.logger.info("Qt installation completed successfully")

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

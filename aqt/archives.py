#!/usr/bin/env python
#
# Copyright (C) 2018 Linus Jahn <lnj@kaidan.im>
# Copyright (C) 2019-2021 Hiroshi Miura <miurahr@linux.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
import posixpath
from dataclasses import dataclass, field
from logging import getLogger
from typing import Dict, Iterable, List, Optional, Tuple

from defusedxml import ElementTree

from aqt.exceptions import ArchiveDownloadError, ArchiveListError, NoPackageFound
from aqt.helper import Settings, get_hash, getUrl, ssplit
from aqt.metadata import QtRepoProperty, Version


@dataclass
class TargetConfig:
    version: str
    target: str
    arch: str
    os_name: str

    def __post_init__(self):
        self.version = str(self.version)


@dataclass
class QtPackage:
    name: str
    base_url: str
    archive_path: str
    archive: str
    package_desc: str
    pkg_update_name: str
    version: Optional[Version] = field(default=None)

    def __repr__(self):
        v_info = f", version={self.version}" if self.version else ""
        return f"QtPackage(name={self.name}, archive={self.archive}{v_info})"

    def __str__(self):
        v_info = f", version={self.version}" if self.version else ""
        return (
            f"QtPackage(name={self.name}, url={self.archive_path}, "
            f"archive={self.archive}, desc={self.package_desc}"
            f"{v_info})"
        )


class ModuleToPackage:
    """
    Holds a mapping of module names to a list of Updates.xml PackageUpdate names.
    For example, we could have the following:
    {"qtcharts": ["qt.qt6.620.addons.qtcharts.arch", qt.qt6.620.qtcharts.arch", qt.620.addons.qtcharts.arch",])
    It also contains a reverse mapping of PackageUpdate names to module names, so that
    lookup of a package name and removal of a module name can be done in constant time.
    Without this reverse mapping, QtArchives._parse_update_xml would run at least one
    linear search on the forward mapping for each module installed.

    The list of PackageUpdate names consists of all the possible names for the PackageUpdate.
    The naming conventions for each PackageUpdate are not predictable, so we need to maintain
    a list of possibilities. While reading Updates.xml, if we encounter any one of the package
    names on this list, we can use it to install the package "qtcharts".

    Once we have installed the package, we need to remove the package "qtcharts" from this
    mapping, so we can keep track of what still needs to be installed.
    """

    def __init__(self, initial_map: Dict[str, List[str]]):
        self._modules_to_packages: Dict[str, List[str]] = initial_map
        self._packages_to_modules: Dict[str, str] = {
            value: key for key, list_of_values in initial_map.items() for value in list_of_values
        }

    def add(self, module_name: str, package_names: List[str]):
        self._modules_to_packages[module_name] = self._modules_to_packages.get(module_name, []) + package_names
        for package_name in package_names:
            assert package_name not in self._packages_to_modules, "Detected a package name collision"
            self._packages_to_modules[package_name] = module_name

    def remove_module_for_package(self, package_name: str):
        module_name = self._packages_to_modules[package_name]
        for package_name in self._modules_to_packages[module_name]:
            self._packages_to_modules.pop(package_name)
        self._modules_to_packages.pop(module_name)

    def has_package(self, package_name: str):
        return package_name in self._packages_to_modules

    def get_modules(self) -> Iterable[str]:
        return self._modules_to_packages.keys()

    def __len__(self) -> int:
        return len(self._modules_to_packages)

    def __format__(self, format_spec) -> str:
        return str(sorted(set(self._modules_to_packages.keys())))


class QtArchives:
    """Download and hold Qt archive packages list.
    It access to download.qt.io site and get Update.xml file.
    It parse XML file and store metadata into list of QtPackage object.
    """

    def __init__(
        self,
        os_name: str,
        target: str,
        version_str: str,
        arch: str,
        base: str,
        subarchives: Optional[Iterable[str]] = None,
        modules: Optional[Iterable[str]] = None,
        all_extra: bool = False,
        is_include_base_package: bool = True,
        timeout=(5, 5),
    ):
        self.version: Version = Version(version_str)
        self.target: str = target
        self.arch: str = arch
        self.os_name: str = os_name
        self.all_extra: bool = all_extra
        self.arch_list: List[str] = [item.get("arch") for item in Settings.qt_combinations]
        self.base: str = base
        self.logger = getLogger("aqt.archives")
        self.archives: List[QtPackage] = []
        self.subarchives: Optional[Iterable[str]] = subarchives
        self.mod_list: Iterable[str] = modules or []
        self.is_include_base_package: bool = is_include_base_package
        self.timeout = timeout
        try:
            self._get_archives()
        except ArchiveDownloadError as e:
            self.handle_missing_updates_xml(e)

    def handle_missing_updates_xml(self, e: ArchiveDownloadError):
        msg = f"Failed to locate XML data for Qt version '{self.version}'."
        help_msg = f"Please use 'aqt list-qt {self.os_name} {self.target}' to show versions available."
        raise ArchiveListError(msg, suggested_action=[help_msg]) from e

    def should_filter_archives(self, package_name: str) -> bool:
        """
        This tells us, based on the PackageUpdate.Name property, whether or not the `self.subarchives`
        list should be used to filter out archives that we are not interested in.

        If `package_name` is a base module or a debug_info module, the `subarchives` list will apply to it.
        """
        return package_name in self._base_package_names() or "debug_info" in package_name

    def _version_str(self) -> str:
        return ("{0.major}{0.minor}" if self.version == Version("5.9.0") else "{0.major}{0.minor}{0.patch}").format(
            self.version
        )

    def _arch_ext(self) -> str:
        ext = QtRepoProperty.extension_for_arch(self.arch, self.version >= Version("6.0.0"))
        return ("_" + ext) if ext else ""

    def _base_module_name(self) -> str:
        """
        This is the name for the base Qt module, whose PackageUpdate.Name property would be
        'qt.123.gcc_64' or 'qt.qt1.123.gcc_64' for Qt 1.2.3, for architecture gcc_64.
        """
        return "qt_base"

    def _base_package_names(self) -> Iterable[str]:
        """
        This is a list of all potential PackageUpdate.Name properties for the base Qt module,
        which would be 'qt.123.gcc_64' or 'qt.qt1.123.gcc_64' for Qt 1.2.3, for architecture gcc_64,
        or 'qt.123.src' or 'qt.qt1.123.src' for the source module.
        """
        return (
            f"qt.qt{self.version.major}.{self._version_str()}.{self.arch}",
            f"qt.{self._version_str()}.{self.arch}",
        )

    def _module_name_suffix(self, module: str) -> str:
        return f"{module}.{self.arch}"

    def _target_packages(self) -> ModuleToPackage:
        if self.all_extra:
            return ModuleToPackage({})
        base_package = {self._base_module_name(): list(self._base_package_names())}
        target_packages = ModuleToPackage(base_package if self.is_include_base_package else {})
        if self.all_extra:
            return target_packages
        for module in self.mod_list:
            suffix = self._module_name_suffix(module)
            package_names = [
                f"qt.qt{self.version.major}.{self._version_str()}.{suffix}",
                f"qt.{self._version_str()}.{suffix}",
            ]
            if not module.startswith("addons."):
                package_names.append(f"qt.qt{self.version.major}.{self._version_str()}.addons.{suffix}")
            target_packages.add(module, package_names)
        return target_packages

    def _get_archives(self):
        # Get packages index

        # os_target_folder: online/qtsdkrepository/windows_x86/desktop/qt5_59_src_doc_examples
        os_target_folder = posixpath.join(
            "online/qtsdkrepository",
            self.os_name + ("_x86" if self.os_name == "windows" else "_x64"),
            self.target,
            f"qt{self.version.major}_{self._version_str()}{self._arch_ext()}",
        )
        update_xml_path = posixpath.join(os_target_folder, "Updates.xml")
        self._download_update_xml(update_xml_path)
        self._parse_update_xml(os_target_folder, self._target_packages())

    def _download_update_xml(self, update_xml_path):
        """Hook for unit test."""
        xml_hash = get_hash(update_xml_path, "sha256", self.timeout)
        update_xml_text = getUrl(posixpath.join(self.base, update_xml_path), self.timeout, xml_hash)
        self.update_xml_text = update_xml_text

    def _parse_update_xml(self, os_target_folder, target_packages: Optional[ModuleToPackage]):
        if not target_packages:
            target_packages = ModuleToPackage({})
        try:
            self.update_xml = ElementTree.fromstring(self.update_xml_text)
        except ElementTree.ParseError as perror:
            raise ArchiveListError(f"Downloaded metadata is corrupted. {perror}") from perror

        for packageupdate in self.update_xml.iter("PackageUpdate"):
            pkg_name = packageupdate.find("Name").text
            downloads_text = packageupdate.find("DownloadableArchives").text
            if not downloads_text:
                continue
            # If we asked for `--noarchives`, we don't want the base module
            if not self.is_include_base_package and pkg_name in self._base_package_names():
                continue
            # Need to filter archives to download when we want all extra modules
            if self.all_extra:
                # Check platform
                name_last_section = pkg_name.split(".")[-1]
                if name_last_section in self.arch_list and self.arch != name_last_section:
                    continue
                # Check doc/examples
                if self.arch in ["doc", "examples"]:
                    if self.arch not in pkg_name:
                        continue
            elif not target_packages.has_package(pkg_name):
                continue
            else:
                target_packages.remove_module_for_package(pkg_name)
            full_version = packageupdate.find("Version").text
            package_desc = packageupdate.find("Description").text
            should_filter_archives: bool = self.subarchives and self.should_filter_archives(pkg_name)

            for archive in ssplit(downloads_text):
                archive_name = archive.split("-", maxsplit=1)[0]
                if should_filter_archives and archive_name not in self.subarchives:
                    continue
                archive_path = posixpath.join(
                    # online/qtsdkrepository/linux_x64/desktop/qt5_5150/
                    os_target_folder,
                    # qt.qt5.5150.gcc_64/
                    pkg_name,
                    # 5.15.0-0-202005140804qtbase-Linux-RHEL_7_6-GCC-Linux-RHEL_7_6-X86_64.7z
                    full_version + archive,
                )
                self.archives.append(
                    QtPackage(
                        name=archive_name,
                        base_url=self.base,
                        archive_path=archive_path,
                        archive=archive,
                        package_desc=package_desc,
                        pkg_update_name=pkg_name,  # For testing purposes
                    )
                )

        # if we have located every requested package, then target_packages will be empty
        if len(target_packages) > 0:
            message = f"The packages {target_packages} were not found while parsing XML of package information!"
            raise NoPackageFound(message, suggested_action=self.help_msg(target_packages.get_modules()))

    def help_msg(self, missing_modules: Iterable[str]) -> Iterable[str]:
        base_cmd = f"aqt list-qt {self.os_name} {self.target}"
        arch = f"Please use '{base_cmd} --arch {self.version}' to show architectures available."
        mods = f"Please use '{base_cmd} --modules {self.version} <arch>' to show modules available."
        has_base_pkg: bool = self._base_module_name() in missing_modules
        has_non_base_pkg: bool = len(list(missing_modules)) > 1 or not has_base_pkg
        messages = []
        if has_base_pkg:
            messages.append(arch)
        if has_non_base_pkg:
            messages.append(mods)
        return messages

    def get_packages(self) -> List[QtPackage]:
        """
         It returns an archive package list.

        :return package list
        :rtype: List[QtPackage]
        """
        return self.archives

    def get_target_config(self) -> TargetConfig:
        """Get target configuration

        :return: configured target and its version with arch
        :rtype: TargetConfig object
        """
        return TargetConfig(self.version, self.target, self.arch, self.os_name)


class SrcDocExamplesArchives(QtArchives):
    """Hold doc/src/example archive package list."""

    def __init__(
        self,
        flavor,
        os_name,
        target,
        version,
        base,
        subarchives=None,
        modules=None,
        all_extra=False,
        is_include_base_package: bool = True,
        timeout=(5, 5),
    ):
        self.flavor = flavor
        self.target = target
        self.os_name = os_name
        self.base = base
        self.logger = getLogger("aqt.archives")
        super(SrcDocExamplesArchives, self).__init__(
            os_name,
            target,
            version,
            arch=self.flavor,
            base=base,
            subarchives=subarchives,
            modules=modules,
            all_extra=all_extra,
            is_include_base_package=is_include_base_package,
            timeout=timeout,
        )

    def _arch_ext(self) -> str:
        return "_src_doc_examples"

    def _base_module_name(self) -> str:
        """
        This is the name for the base Qt Src/Doc/Example module, whose PackageUpdate.Name
        property would be 'qt.123.examples' or 'qt.qt1.123.examples' for Qt 1.2.3 examples.
        """
        return self.flavor  # src | doc | examples

    def _module_name_suffix(self, module: str) -> str:
        return f"{self.flavor}.{module}"

    def get_target_config(self) -> TargetConfig:
        """Get target configuration.

        :return tuple of three parameter, "src_doc_examples", target and arch
        """
        return TargetConfig("src_doc_examples", self.target, self.arch, self.os_name)

    def help_msg(self, missing_modules: Iterable[str]) -> Iterable[str]:
        cmd_type = "example" if self.flavor == "examples" else self.flavor
        base_cmd = f"aqt list-{cmd_type} {self.os_name} {self.version}"
        mods = f"Please use '{base_cmd} --modules' to show modules available."
        has_non_base_pkg: bool = len(list(missing_modules)) > 1
        messages = []
        if has_non_base_pkg:
            messages.append(mods)
        return messages


class ToolArchives(QtArchives):
    """Hold tool archive package list
    when installing mingw tool, argument would be
    ToolArchive(windows, desktop, 4.9.1-3, mingw)
    when installing ifw tool, argument would be
    ToolArchive(linux, desktop, 3.1.1, ifw)
    """

    def __init__(
        self,
        os_name: str,
        target: str,
        tool_name: str,
        base: str,
        version_str: Optional[str] = None,
        arch: Optional[str] = None,
        timeout: Tuple[int, int] = (5, 5),
    ):
        self.tool_name = tool_name
        self.os_name = os_name
        self.logger = getLogger("aqt.archives")
        self.tool_version_str: Optional[str] = version_str
        super(ToolArchives, self).__init__(
            os_name=os_name,
            target=target,
            version_str="0.0.1",  # dummy value
            arch=arch,
            base=base,
            timeout=timeout,
        )

    def __str__(self):
        return f"ToolArchives(tool_name={self.tool_name}, version={self.version}, arch={self.arch})"

    def handle_missing_updates_xml(self, e: ArchiveDownloadError):
        msg = f"Failed to locate XML data for the tool '{self.tool_name}'."
        help_msg = f"Please use 'aqt list-tool {self.os_name} {self.target}' to show tools available."
        raise ArchiveListError(msg, suggested_action=[help_msg]) from e

    def _get_archives(self):
        os_target_folder = posixpath.join(
            "online/qtsdkrepository",
            # linux_x64/
            self.os_name + ("_x86" if self.os_name == "windows" else "_x64"),
            # desktop/
            self.target,
            # tools_ifw/
            self.tool_name,
        )
        update_xml_url = posixpath.join(os_target_folder, "Updates.xml")
        self._download_update_xml(update_xml_url)  # call super method.
        self._parse_update_xml(os_target_folder, None)

    def _parse_update_xml(self, os_target_folder, *ignored):
        try:
            self.update_xml = ElementTree.fromstring(self.update_xml_text)
        except ElementTree.ParseError as perror:
            raise ArchiveListError(f"Downloaded metadata is corrupted. {perror}") from perror

        try:
            packageupdate = next(filter(lambda x: x.find("Name").text == self.arch, self.update_xml.iter("PackageUpdate")))
        except StopIteration:
            message = f"The package '{self.arch}' was not found while parsing XML of package information!"
            raise NoPackageFound(message, suggested_action=self.help_msg())

        name = packageupdate.find("Name").text
        named_version = packageupdate.find("Version").text
        if self.tool_version_str and named_version != self.tool_version_str:
            message = f"The package '{self.arch}' has the version '{named_version}', not the requested '{self.version}'."
            raise NoPackageFound(message, suggested_action=self.help_msg())
        package_desc = packageupdate.find("Description").text
        downloadable_archives = packageupdate.find("DownloadableArchives").text
        if not downloadable_archives:
            message = f"The package '{self.arch}' contains no downloadable archives!"
            raise NoPackageFound(message)
        for archive in ssplit(downloadable_archives):
            archive_path = posixpath.join(
                # online/qtsdkrepository/linux_x64/desktop/tools_ifw/
                os_target_folder,
                # qt.tools.ifw.41/
                name,
                #  4.1.1-202105261130ifw-linux-x64.7z
                f"{named_version}{archive}",
            )
            self.archives.append(
                QtPackage(
                    name=name,
                    base_url=self.base,
                    archive_path=archive_path,
                    archive=archive,
                    package_desc=package_desc,
                    pkg_update_name=name,  # Redundant
                )
            )

    def help_msg(self, *args) -> Iterable[str]:
        return [f"Please use 'aqt list-tool {self.os_name} {self.target} {self.tool_name}' to show tool variants available."]

    def get_target_config(self) -> TargetConfig:
        """Get target configuration.

        :return tuple of three parameter, "Tools", target and arch
        """
        return TargetConfig("Tools", self.target, self.arch, self.os_name)

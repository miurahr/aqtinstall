#!/usr/bin/env python
#
# Copyright (C) 2018 Linus Jahn <lnj@kaidan.im>
# Copyright (C) 2019-2022 Hiroshi Miura <miurahr@linux.com>
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
from typing import Dict, Iterable, List, Optional, Set, Tuple
from xml.etree.ElementTree import Element  # noqa

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


@dataclass
class PackageUpdate:
    """
    Data class to hold package data.
    key is its name.
    """

    name: str
    display_name: str
    description: str
    release_date: str
    full_version: str
    dependencies: Iterable[str]
    auto_dependon: Iterable[str]
    downloadable_archives: Iterable[str]
    default: bool
    virtual: bool
    base: str

    def __post_init__(self):
        for iter_of_str in self.dependencies, self.auto_dependon, self.downloadable_archives:
            assert isinstance(iter_of_str, Iterable) and not isinstance(iter_of_str, str)
        for _str in self.name, self.display_name, self.description, self.release_date, self.full_version, self.base:
            assert isinstance(_str, str)
        for boolean in self.default, self.virtual:
            assert isinstance(boolean, bool)

    @property
    def version(self):
        return Version.permissive(self.full_version)

    @property
    def arch(self):
        return self.name.split(".")[-1]

    def is_base_package(self) -> bool:
        return self.name in (
            f"qt.qt{self.version.major}.{self._version_str()}.{self.arch}",
            f"qt.{self._version_str()}.{self.arch}",
        )

    def _version_str(self) -> str:
        return ("{0.major}{0.minor}" if self.version == Version("5.9.0") else "{0.major}{0.minor}{0.patch}").format(
            self.version
        )


@dataclass(init=False)
class Updates:
    package_updates: List[PackageUpdate]

    def __init__(self):
        self.package_updates = []

    def extend(self, other):
        self.package_updates.extend(other.package_updates)

    @staticmethod
    def fromstring(base, update_xml_text: str):
        try:
            update_xml = ElementTree.fromstring(update_xml_text)
        except ElementTree.ParseError as perror:
            raise ArchiveListError(f"Downloaded metadata is corrupted. {perror}") from perror
        updates = Updates()
        for packageupdate in update_xml.iter("PackageUpdate"):
            pkg_name = updates._get_text(packageupdate.find("Name"))
            display_name = updates._get_text(packageupdate.find("DisplayName"))
            full_version = updates._get_text(packageupdate.find("Version"))
            package_desc = updates._get_text(packageupdate.find("Description"))
            release_date = updates._get_text(packageupdate.find("ReleaseDate"))
            dependencies = updates._get_list(packageupdate.find("Dependencies"))
            auto_dependon = updates._get_list(packageupdate.find("AutoDependOn"))
            archives = updates._get_list(packageupdate.find("DownloadableArchives"))
            default = updates._get_boolean(packageupdate.find("Default"))
            virtual = updates._get_boolean(packageupdate.find("Virtual"))
            updates.package_updates.append(
                PackageUpdate(
                    pkg_name,
                    display_name,
                    package_desc,
                    release_date,
                    full_version,
                    dependencies,
                    auto_dependon,
                    archives,
                    default,
                    virtual,
                    base,
                )
            )
        return updates

    def get(self, target: Optional[str] = None):
        if target is None:
            return self.package_updates
        for update in self.package_updates:
            if update.name == target:
                return update
        return None

    def get_from(self, arch: str, is_include_base: bool, target_packages: Optional[ModuleToPackage] = None):
        result = []
        for update in self.package_updates:
            # If we asked for `--noarchives`, we don't want the base module
            if not is_include_base and update.is_base_package():
                continue
            if target_packages is not None and not target_packages.has_package(update.name):
                continue
            if arch in update.name:
                result.append(update)
        return result

    def merge(self, other):
        self.package_updates.extend(other.package_updates)

    def get_depends(self, target: str) -> Iterable[str]:
        # initialize
        filo = [target]
        packages = []
        visited = []
        # dfs look-up
        while len(filo) > 0:
            next = filo.pop()
            packages.append(next)
            for entry in self.package_updates:
                if entry.name == next:
                    visited.append(next)
                    if entry.dependencies is not None:
                        for depend in entry.dependencies:
                            if depend not in visited:
                                filo.append(depend)
        return packages

    def _get_text(self, item: Optional[Element]) -> str:
        if item is not None and item.text is not None:
            return item.text
        return ""

    def _get_list(self, item: Optional[Element]) -> Iterable[str]:
        if item is not None and item.text is not None:
            return ssplit(item.text)
        else:
            return []

    def _get_boolean(self, item) -> bool:
        if "true" == item:
            return True
        else:
            return False


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
        self.mod_list: Set[str] = set(modules or [])
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
        self._get_archives_base(f"qt{self.version.major}_{self._version_str()}{self._arch_ext()}", self._target_packages())

    def _append_depends_tool(self, arch, tool_name):
        os_target_folder = posixpath.join(
            "online/qtsdkrepository",
            self.os_name + ("_x86" if self.os_name == "windows" else "_x64"),
            self.target,
            tool_name,
        )
        update_xml_url = posixpath.join(os_target_folder, "Updates.xml")
        update_xml_text = self._download_update_xml(update_xml_url)
        update_xml = Updates.fromstring(self.base, update_xml_text)
        self._append_tool_update(os_target_folder, update_xml, arch, None)

    def _get_archives_base(self, name, target_packages):
        os_target_folder = posixpath.join(
            "online/qtsdkrepository",
            self.os_name + ("_x86" if self.os_name == "windows" else "_x64"),
            self.target,
            # tools_ifw/
            name,
        )
        update_xml_url = posixpath.join(os_target_folder, "Updates.xml")
        update_xml_text = self._download_update_xml(update_xml_url)
        self._parse_update_xml(os_target_folder, update_xml_text, target_packages)

    def _download_update_xml(self, update_xml_path):
        """Hook for unit test."""
        xml_hash = get_hash(update_xml_path, "sha256", self.timeout)
        return getUrl(posixpath.join(self.base, update_xml_path), self.timeout, xml_hash)

    def _parse_update_xml(self, os_target_folder, update_xml_text, target_packages: Optional[ModuleToPackage]):
        if not target_packages:
            target_packages = ModuleToPackage({})
        update_xml = Updates.fromstring(self.base, update_xml_text)
        base_url = self.base
        if self.all_extra:
            package_updates = update_xml.get_from(self.arch, self.is_include_base_package)
        else:
            package_updates = update_xml.get_from(self.arch, self.is_include_base_package, target_packages)
        for packageupdate in package_updates:
            if not self.all_extra:
                target_packages.remove_module_for_package(packageupdate.name)
            should_filter_archives: bool = bool(self.subarchives) and self.should_filter_archives(packageupdate.name)

            for archive in packageupdate.downloadable_archives:
                archive_name = archive.split("-", maxsplit=1)[0]
                if should_filter_archives and self.subarchives is not None and archive_name not in self.subarchives:
                    continue
                archive_path = posixpath.join(
                    # online/qtsdkrepository/linux_x64/desktop/qt5_5150/
                    os_target_folder,
                    # qt.qt5.5150.gcc_64/
                    packageupdate.name,
                    # 5.15.0-0-202005140804qtbase-Linux-RHEL_7_6-GCC-Linux-RHEL_7_6-X86_64.7z
                    packageupdate.full_version + archive,
                )
                self.archives.append(
                    QtPackage(
                        name=archive_name,
                        base_url=base_url,
                        archive_path=archive_path,
                        archive=archive,
                        package_desc=packageupdate.description,
                        pkg_update_name=packageupdate.name,  # For testing purposes
                    )
                )
        # if we have located every requested package, then target_packages will be empty
        if not self.all_extra and len(target_packages) > 0:
            message = f"The packages {target_packages} were not found while parsing XML of package information!"
            raise NoPackageFound(message, suggested_action=self.help_msg(list(target_packages.get_modules())))

    def _append_tool_update(self, os_target_folder, update_xml, target, tool_version_str):
        packageupdate = update_xml.get(target)
        if packageupdate is None:
            message = f"The package '{self.arch}' was not found while parsing XML of package information!"
            raise NoPackageFound(message, suggested_action=self.help_msg())
        name = packageupdate.name
        named_version = packageupdate.full_version
        if tool_version_str and named_version != tool_version_str:
            message = f"The package '{self.arch}' has the version '{named_version}', not the requested '{self.version}'."
            raise NoPackageFound(message, suggested_action=self.help_msg())
        package_desc = packageupdate.description
        downloadable_archives = packageupdate.downloadable_archives
        if not downloadable_archives:
            message = f"The package '{self.arch}' contains no downloadable archives!"
            raise NoPackageFound(message)
        for archive in downloadable_archives:
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

    def help_msg(self, missing_modules: Optional[List[str]] = None) -> List[str]:
        _missing_modules: List[str] = missing_modules or []
        base_cmd = f"aqt list-qt {self.os_name} {self.target}"
        arch = f"Please use '{base_cmd} --arch {self.version}' to show architectures available."
        mods = f"Please use '{base_cmd} --modules {self.version} <arch>' to show modules available."
        has_base_pkg: bool = self._base_module_name() in _missing_modules
        has_non_base_pkg: bool = len(list(_missing_modules)) > 1 or not has_base_pkg
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
        return TargetConfig(str(self.version), self.target, self.arch, self.os_name)


class SrcDocExamplesArchives(QtArchives):
    """Hold doc/src/example archive package list."""

    def __init__(
        self,
        flavor: str,
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
        self.flavor: str = flavor
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

    def help_msg(self, missing_modules: Optional[List[str]] = None) -> List[str]:
        _missing_modules: List[str] = missing_modules or []
        cmd_type = "example" if self.flavor == "examples" else self.flavor
        base_cmd = f"aqt list-{cmd_type} {self.os_name} {self.version}"
        mods = f"Please use '{base_cmd} --modules' to show modules available."
        has_non_base_pkg: bool = len(list(_missing_modules)) > 1
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
        arch: str = "",
        timeout: Tuple[float, float] = (5, 5),
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
        self._get_archives_base(self.tool_name, None)

    def _parse_update_xml(self, os_target_folder, update_xml_text, *ignored):
        update_xml = Updates.fromstring(self.base, update_xml_text)
        self._append_tool_update(os_target_folder, update_xml, self.arch, self.tool_version_str)

    def help_msg(self, *args) -> List[str]:
        return [f"Please use 'aqt list-tool {self.os_name} {self.target} {self.tool_name}' to show tool variants available."]

    def get_target_config(self) -> TargetConfig:
        """Get target configuration.

        :return tuple of three parameter, "Tools", target and arch
        """
        return TargetConfig("Tools", self.target, self.arch, self.os_name)

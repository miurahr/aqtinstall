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
import itertools
import posixpath
import random
import re
import xml.etree.ElementTree as ElementTree
from logging import getLogger
from typing import Callable, Generator, Iterable, Iterator, List, Optional, Tuple, Union

import bs4
from semantic_version import SimpleSpec, Version

from aqt import helper
from aqt.exceptions import (
    ArchiveConnectionError,
    ArchiveDownloadError,
    ArchiveListError,
    CliInputError,
    NoPackageFound,
)
from aqt.helper import ArchiveId, Settings, getUrl, xml_to_modules


class TargetConfig:
    def __init__(self, version, target, arch, os_name):
        self.version = str(version)
        self.target = target
        self.arch = arch
        self.os_name = os_name

    def __str__(self):
        print(
            f"TargetConfig(version={self.version}, target={self.target}, "
            f"arch={self.arch}, os_name={self.os_name}"
        )

    def __repr__(self):
        print(f"({self.version}, {self.target}, {self.arch}, {self.os_name})")


class ListCommand:
    """Encapsulate all parts of the `aqt list` command"""

    # Inner helper classes
    class Versions:
        def __init__(
            self,
            versions: Union[None, Version, Iterable[Tuple[int, Iterable[Version]]]],
        ):
            if versions is None:
                self.versions = list()
            elif isinstance(versions, Version):
                self.versions = [[versions]]
            else:
                self.versions: List[List[Version]] = [
                    list(versions_iterator) for _, versions_iterator in versions
                ]

        def __str__(self) -> str:
            return str(self.versions)

        def pretty_print(self) -> str:
            return "\n".join(
                " ".join(
                    ListCommand.Versions.stringify_ver(version)
                    for version in minor_list
                )
                for minor_list in self.versions
            )

        def __bool__(self):
            return len(self.versions) > 0 and len(self.versions[0]) > 0

        def latest(self) -> Optional[Version]:
            if not self:
                return None
            return self.versions[-1][-1]

        @staticmethod
        def stringify_ver(version: Version) -> str:
            if version.prerelease:
                return "{}.{}-preview".format(version.major, version.minor)
            return str(version)

    class ListOfStr:
        def __init__(self, strings: List[str]):
            self.strings = strings

        def __str__(self):
            return str(self.strings)

        def pretty_print(self) -> str:
            return " ".join(self.strings)

        def __bool__(self):
            return len(self.strings) > 0 and len(self.strings[0]) > 0

    class Tools(ListOfStr):
        def pretty_print(self) -> str:
            return "\n".join(self.strings)

    def __init__(
        self,
        archive_id: ArchiveId,
        *,
        filter_minor: Optional[int] = None,
        is_latest_version: bool = False,
        modules_ver: Optional[str] = None,
        extensions_ver: Optional[str] = None,
        architectures_ver: Optional[str] = None,
        tool_name: Optional[str] = None,
    ):
        """
        Construct ListCommand.

        :param filter_minor:        When set, the ListCommand will filter out all versions of
                                    Qt that don't match this minor version.
        :param is_latest_version:   When True, the ListCommand will find all versions of Qt
                                    matching filters, and only print the most recent version
        :param modules_ver:         Version of Qt for which to list modules
        :param extensions_ver:      Version of Qt for which to list extensions
        :param architectures_ver:   Version of Qt for which to list architectures
        """
        self.logger = getLogger("aqt.archives")
        self.archive_id = archive_id
        self.filter_minor = filter_minor

        if archive_id.is_tools():
            if tool_name:
                self.request_type = "tool variant names"
                self._action = lambda: self.fetch_tool_modules(tool_name)
            else:
                self.request_type = "tools"
                self._action = self.fetch_tools
        elif is_latest_version:
            self.request_type = "latest version"
            self._action = lambda: ListCommand.Versions(self.fetch_latest_version())
        elif modules_ver:
            self.request_type = "modules"
            self._action = lambda: self.fetch_modules(self._to_version(modules_ver))
        elif extensions_ver:
            self.request_type = "extensions"
            self._action = lambda: self.fetch_extensions(
                self._to_version(extensions_ver)
            )
        elif architectures_ver:
            self.request_type = "architectures"
            self._action = lambda: self.fetch_arches(
                self._to_version(architectures_ver)
            )
        else:
            self.request_type = "versions"
            self._action = self.fetch_versions

    def action(self) -> Union[ListOfStr, Tools, Versions]:
        return self._action()

    def run(self) -> int:
        try:
            output = self.action()
            if not output:
                self.logger.info(
                    "No {} available for this request.".format(self.request_type)
                )
                self.print_suggested_follow_up(self.logger.info)
                return 1
            print(output.pretty_print())
            return 0
        except CliInputError as e:
            self.logger.error("Command line input error: {}".format(e))
            exit(1)
        except (ArchiveConnectionError, ArchiveDownloadError) as e:
            self.logger.error("{}".format(e))
            self.print_suggested_follow_up(self.logger.error)
            return 1

    def fetch_modules(self, version: Version) -> ListOfStr:
        return self.get_modules_architectures_for_version(version=version)[0]

    def fetch_arches(self, version: Version) -> ListOfStr:
        return self.get_modules_architectures_for_version(version=version)[1]

    def fetch_extensions(self, version: Version) -> ListOfStr:
        versions_extensions = ListCommand.get_versions_extensions(
            self.fetch_http(self.archive_id.to_url()), self.archive_id.category
        )
        filtered = filter(
            lambda ver_ext: ver_ext[0] == version and ver_ext[1],
            versions_extensions,
        )
        return ListCommand.ListOfStr(
            strings=list(map(lambda ver_ext: ver_ext[1], filtered))
        )

    def fetch_versions(self) -> Versions:
        def filter_by(ver_ext: Tuple[Optional[Version], str]) -> bool:
            version, extension = ver_ext
            return (
                version
                and (self.filter_minor is None or self.filter_minor == version.minor)
                and (self.archive_id.extension == extension)
            )

        def get_version(ver_ext: Tuple[Version, str]):
            return ver_ext[0]

        versions_extensions = ListCommand.get_versions_extensions(
            self.fetch_http(self.archive_id.to_url()), self.archive_id.category
        )
        versions = sorted(
            filter(None, map(get_version, filter(filter_by, versions_extensions)))
        )
        iterables = itertools.groupby(versions, lambda version: version.minor)
        return ListCommand.Versions(iterables)

    def fetch_latest_version(self) -> Optional[Version]:
        return self.fetch_versions().latest()

    def fetch_tools(self) -> Tools:
        html_doc = self.fetch_http(self.archive_id.to_url())
        return ListCommand.Tools(list(ListCommand.iterate_folders(html_doc, "tools")))

    def fetch_tool_modules(self, tool_name: str) -> ListOfStr:
        rest_of_url = self.archive_id.to_url() + tool_name + "/Updates.xml"
        xml = self.fetch_http(rest_of_url)  # raises RequestException
        modules = xml_to_modules(
            xml,
            predicate=ListCommand._has_nonempty_downloads,
            keys_to_keep=(),  # Just want names
        )
        return ListCommand.ListOfStr(strings=list(modules.keys()))

    def _to_version(self, qt_ver: str) -> Version:
        """
        Turns a string in the form of `5.X.Y | latest` into a semantic version.
        If the string does not fit either of these forms, CliInputError will be raised.
        If qt_ver == latest, and no versions exist corresponding to the filters specified,
        then CliInputError will be raised.
        If qt_ver == latest, and an HTTP error occurs, requests.RequestException will be raised.

        :param qt_ver:  Either the literal string `latest`, or a semantic version
                        with each part separated with dots.
        """
        assert qt_ver
        if qt_ver == "latest":
            latest_version = self.fetch_latest_version()
            if not latest_version:
                msg = "There is no latest version of Qt with the criteria '{}'".format(
                    self.describe_filters()
                )
                raise CliInputError(msg)
            return latest_version
        version = helper.to_version(qt_ver)
        if self.archive_id.is_major_ver_mismatch(version):
            msg = "Major version mismatch between {} and {}".format(
                self.archive_id.category, version
            )
            raise CliInputError(msg)
        return version

    @staticmethod
    def fetch_http(rest_of_url: str) -> str:
        base_urls = Settings.baseurl, random.choice(Settings.fallbacks)
        for i, base_url in enumerate(base_urls):
            try:
                url = posixpath.join(base_url, rest_of_url)
                return getUrl(
                    url=url,
                    timeout=(Settings.connection_timeout, Settings.response_timeout),
                )

            except (ArchiveDownloadError, ArchiveConnectionError) as e:
                if i == len(base_urls) - 1:
                    raise e

    @staticmethod
    def iterate_folders(
        html_doc: str, filter_category: str = ""
    ) -> Generator[str, None, None]:
        def table_row_to_folder(tr: bs4.element.Tag) -> str:
            try:
                return tr.find_all("td")[1].a.contents[0].rstrip("/")
            except (AttributeError, IndexError):
                return ""

        soup: bs4.BeautifulSoup = bs4.BeautifulSoup(html_doc, "html.parser")
        for row in soup.body.table.find_all("tr"):
            content: str = table_row_to_folder(row)
            if not content or content == "Parent Directory":
                continue
            if content.startswith(filter_category):
                yield content

    @staticmethod
    def get_versions_extensions(
        html_doc: str, category: str
    ) -> Iterator[Tuple[Optional[Version], str]]:
        def folder_to_version_extension(folder: str) -> Tuple[Optional[Version], str]:
            components = folder.split("_", maxsplit=2)
            ext = "" if len(components) < 3 else components[2]
            ver = "" if len(components) < 2 else components[1]
            return (
                helper.get_semantic_version(qt_ver=ver, is_preview="preview" in ext),
                ext,
            )

        return map(
            folder_to_version_extension, ListCommand.iterate_folders(html_doc, category)
        )

    @staticmethod
    def _has_nonempty_downloads(element: ElementTree.Element) -> bool:
        """Returns True if the element has an empty '<DownloadableArchives/>' tag"""
        downloads = element.find("DownloadableArchives")
        return downloads is not None and downloads.text

    def get_modules_architectures_for_version(
        self, version: Version
    ) -> Tuple[ListOfStr, ListOfStr]:
        """Returns [list of modules, list of architectures]"""
        patch = (
            ""
            if version.prerelease or self.archive_id.is_preview()
            else str(version.patch)
        )
        qt_ver_str = "{}{}{}".format(version.major, version.minor, patch)
        # Example: re.compile(r"^(preview\.)?qt\.(qt5\.)?590\.(.+)$")
        pattern = re.compile(
            r"^(preview\.)?qt\.(qt"
            + str(version.major)
            + r"\.)?"
            + qt_ver_str
            + r"\.(.+)$"
        )

        def to_module_arch(name: str) -> Tuple[Optional[str], Optional[str]]:
            _match = pattern.match(name)
            if not _match:
                return None, None
            module_with_arch = _match.group(3)
            if self.archive_id.is_no_arch() or "." not in module_with_arch:
                return module_with_arch, None
            module, arch = module_with_arch.rsplit(".", 1)
            return module, arch

        rest_of_url = self.archive_id.to_url(
            qt_version_no_dots=qt_ver_str, file="Updates.xml"
        )
        xml = self.fetch_http(rest_of_url)  # raises RequestException

        # We want the names of modules, regardless of architecture:
        modules = xml_to_modules(
            xml,
            predicate=ListCommand._has_nonempty_downloads,
            keys_to_keep=(),  # Just want names
        )

        def naive_modules_arches(
            names: Iterable[str],
        ) -> Tuple[ListCommand.ListOfStr, ListCommand.ListOfStr]:
            modules_and_arches, _modules, arches = set(), set(), set()
            for name in names:
                # First term could be a module name or an architecture
                first_term, arch = to_module_arch(name)
                if first_term:
                    modules_and_arches.add(first_term)
                if arch:
                    arches.add(arch)
            for first_term in modules_and_arches:
                if first_term not in arches:
                    _modules.add(first_term)
            return (
                ListCommand.ListOfStr(strings=sorted(_modules)),
                ListCommand.ListOfStr(strings=sorted(arches)),
            )

        return naive_modules_arches(modules.keys())

    def describe_filters(self) -> str:
        if self.filter_minor is None:
            return str(self.archive_id)
        return "{} with minor version {}".format(self.archive_id, self.filter_minor)

    def print_suggested_follow_up(self, printer: Callable[[str], None]) -> None:
        """Makes an informed guess at what the user got wrong, in the event of an error."""
        base_cmd = "aqt {0.category} {0.host} {0.target}".format(self.archive_id)
        if self.archive_id.extension:
            msg = "Please use '{} --extensions <QT_VERSION>' to list valid extensions.".format(
                base_cmd
            )
            printer(msg)

        if self.archive_id.is_tools() and self.request_type == "tool variant names":
            msg = "Please use '{}' to check what tools are available.".format(base_cmd)
            printer(msg)
        elif self.filter_minor is not None:
            msg = "Please use '{}' to check that versions of {} exist with the minor version '{}'".format(
                base_cmd, self.archive_id.category, self.filter_minor
            )
            printer(msg)
        elif self.request_type in ("architectures", "modules", "extensions"):
            msg = "Please use '{}' to show versions of Qt available".format(base_cmd)
            printer(msg)


class QtPackage:
    """
    Hold package information.
    """

    def __init__(
        self,
        name: str,
        archive_url: str,
        archive: str,
        package_desc: str,
        hashurl: str,
        version: Optional[Version] = None,
    ):
        self.name = name
        self.url = archive_url
        self.archive = archive
        self.desc = package_desc
        self.hashurl = hashurl
        self.version = version

    def __repr__(self):
        v_info = f", version={self.version}" if self.version else ""
        return f"QtPackage(name={self.name}, archive={self.archive}{v_info})"

    def __str__(self):
        v_info = f", version={self.version}" if self.version else ""
        return (
            f"QtPackage(name={self.name}, url={self.url}, "
            f"archive={self.archive}, desc={self.desc}"
            f"hashurl={self.hashurl}{v_info})"
        )


class ListInfo:
    """
    Hold list information
    """

    def __init__(self, name, display_name, desc, virtual):
        self.name = name
        self.display_name = display_name
        self.desc = desc
        self.virtual = virtual


class PackagesList:
    """
    Hold packages list information.
    """

    def __init__(self, version, os_name, target, base, timeout=(5, 5)):
        self.version = Version(version)
        self.os_name = os_name
        self.target = target
        self.archives = []
        self.base = posixpath.join(base, "online", "qtsdkrepository")
        self.timeout = timeout
        self.logger = getLogger("aqt")
        self._get_archives()

    def _get_archives(self):
        # Get packages index
        if self.version.major == 6 and self.target == "android":
            arch_ext = ["_armv7/", "_x86/", "_x86_64/", "_arm64_v8a/"]
        elif self.version in SimpleSpec(">=5.13.0,<6.0") and self.target == "desktop":
            arch_ext = ["/", "_wasm/"]
        else:
            arch_ext = ["/"]
        for ext in arch_ext:
            archive_path = "{0}{1}{2}/qt{3}_{3}{4}{5}{6}".format(
                self.os_name,
                "_x86/" if self.os_name == "windows" else "_x64/",
                self.target,
                self.version.major,
                self.version.minor,
                self.version.patch,
                ext,
            )
            update_xml_url = posixpath.join(self.base, archive_path, "Updates.xml")
            xml_text = getUrl(update_xml_url, self.timeout)
            self.update_xml = ElementTree.fromstring(xml_text)
            for packageupdate in self.update_xml.iter("PackageUpdate"):
                name = packageupdate.find("Name").text
                if packageupdate.find("DownloadableArchives").text is not None:
                    package_desc = packageupdate.findtext("Description")
                    display_name = packageupdate.findtext("DisplayName")
                    virtual_str = packageupdate.findtext("Virtual")
                    if virtual_str == "true":
                        virtual = True
                    else:
                        virtual = False
                    self.archives.append(
                        ListInfo(
                            name=name,
                            display_name=display_name,
                            desc=package_desc,
                            virtual=virtual,
                        )
                    )
        if len(self.archives) == 0:
            self.logger.error("Error while parsing package information!")
            exit(1)

    def get_list(self):
        return self.archives


class QtArchives:
    """Download and hold Qt archive packages list.
    It access to download.qt.io site and get Update.xml file.
    It parse XML file and store metadata into list of QtPackage object.
    """

    def __init__(
        self,
        os_name,
        target,
        version_str,
        arch,
        base,
        subarchives=None,
        modules=None,
        all_extra=False,
        timeout=(5, 5),
    ):
        self.version = Version(version_str)
        self.target = target
        self.arch = arch
        self.os_name = os_name
        self.all_extra = all_extra
        self.arch_list = [item.get("arch") for item in Settings.qt_combinations]
        all_archives = subarchives is None
        self.base = base + "/online/qtsdkrepository/"
        self.logger = getLogger("aqt.archives")
        self.archives = []
        self.mod_list = []
        if all_extra:
            self.all_extra = True
        else:
            for m in modules if modules is not None else []:
                self.mod_list.append(
                    "qt.qt{0}.{0}{1}{2}.{3}.{4}".format(
                        self.version.major,
                        self.version.minor,
                        self.version.patch,
                        m,
                        arch,
                    )
                )
                self.mod_list.append(
                    "qt.{0}{1}{2}.{3}.{4}".format(
                        self.version.major,
                        self.version.minor,
                        self.version.patch,
                        m,
                        arch,
                    )
                )
        self.timeout = timeout
        self._get_archives()
        if not all_archives:
            self.archives = list(filter(lambda a: a.name in subarchives, self.archives))

    def _get_archives(self):
        # Get packages index
        if self.arch == "wasm_32":
            arch_ext = "_wasm"
        elif self.arch.startswith("android_") and self.version.major == 6:
            arch_ext = "{}".format(self.arch[7:])
        else:
            arch_ext = ""
        archive_path = "{0}{1}{2}/qt{3}_{3}{4}{5}{6}/".format(
            self.os_name,
            "_x86/" if self.os_name == "windows" else "_x64/",
            self.target,
            self.version.major,
            self.version.minor,
            self.version.patch,
            arch_ext,
        )
        update_xml_url = "{0}{1}Updates.xml".format(self.base, archive_path)
        archive_url = "{0}{1}".format(self.base, archive_path)
        target_packages = []
        target_packages.append(
            "qt.qt{0}.{0}{1}{2}.{3}".format(
                self.version.major,
                self.version.minor,
                self.version.patch,
                self.arch,
            )
        )
        target_packages.append(
            "qt.{0}{1}{2}.{3}".format(
                self.version.major, self.version.minor, self.version.patch, self.arch
            )
        )
        target_packages.extend(self.mod_list)
        self._download_update_xml(update_xml_url)
        self._parse_update_xml(archive_url, target_packages)

    def _download_update_xml(self, update_xml_url):
        """Hook for unit test."""
        self.update_xml_text = getUrl(update_xml_url, self.timeout)

    def _parse_update_xml(self, archive_url, target_packages):
        try:
            self.update_xml = ElementTree.fromstring(self.update_xml_text)
        except ElementTree.ParseError as perror:
            self.logger.error("Downloaded metadata is corrupted. {}".format(perror))
            raise ArchiveListError("Downloaded metadata is corrupted.")

        for packageupdate in self.update_xml.iter("PackageUpdate"):
            name = packageupdate.find("Name").text
            # Need to filter archives to download when we want all extra modules
            if self.all_extra:
                # Check platform
                name_last_section = name.split(".")[-1]
                if (
                    name_last_section in self.arch_list
                    and self.arch != name_last_section
                ):
                    continue
                # Check doc/examples
                if self.arch in ["doc", "examples"]:
                    if self.arch not in name:
                        continue
            if self.all_extra or name in target_packages:
                if packageupdate.find("DownloadableArchives").text is not None:
                    downloadable_archives = packageupdate.find(
                        "DownloadableArchives"
                    ).text.split(", ")
                    full_version = packageupdate.find("Version").text
                    package_desc = packageupdate.find("Description").text
                    for archive in downloadable_archives:
                        archive_name = archive.split("-", maxsplit=1)[0]
                        package_url = posixpath.join(
                            # https://download.qt.io/online/qtsdkrepository/linux_x64/desktop/qt5_5150/
                            archive_url,
                            # qt.qt5.5150.gcc_64/
                            name,
                            # 5.15.0-0-202005140804qtbase-Linux-RHEL_7_6-GCC-Linux-RHEL_7_6-X86_64.7z
                            full_version + archive,
                        )
                        hashurl = package_url + ".sha1"
                        self.archives.append(
                            QtPackage(
                                name=archive_name,
                                archive_url=package_url,
                                archive=archive,
                                package_desc=package_desc,
                                hashurl=hashurl,
                            )
                        )
        if len(self.archives) == 0:
            self.logger.error(
                "Specified packages are not found while parsing XML of package information!"
            )
            raise NoPackageFound

    def get_archives(self):
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
            self.flavor,
            base,
            subarchives=subarchives,
            modules=modules,
            all_extra=all_extra,
            timeout=timeout,
        )

    def _get_archives(self):
        archive_path = "{0}{1}{2}/qt{3}_{3}{4}{5}{6}".format(
            self.os_name,
            "_x86/" if self.os_name == "windows" else "_x64/",
            self.target,
            self.version.major,
            self.version.minor,
            self.version.patch,
            "_src_doc_examples/",
        )
        archive_url = "{0}{1}".format(self.base, archive_path)
        update_xml_url = "{0}/Updates.xml".format(archive_url)
        target_packages = []
        target_packages.append(
            "qt.qt{0}.{0}{1}{2}.{3}".format(
                self.version.major,
                self.version.minor,
                self.version.patch,
                self.flavor,
            )
        )
        target_packages.extend(self.mod_list)
        self._download_update_xml(update_xml_url)
        self._parse_update_xml(archive_url, target_packages)

    def get_target_config(self) -> TargetConfig:
        """Get target configuration.

        :return tuple of three parameter, "src_doc_examples", target and arch
        """
        return TargetConfig("src_doc_examples", self.target, self.arch, self.os_name)


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
        tool_name: str,
        base: str,
        version_str: Optional[str] = None,
        arch: Optional[str] = None,
        timeout: Tuple[int, int] = (5, 5),
    ):
        self.tool_name = tool_name
        self.os_name = os_name
        self.logger = getLogger("aqt.archives")
        super(ToolArchives, self).__init__(
            os_name=os_name,
            target="desktop",
            version_str=version_str,
            arch=arch,
            base=base,
            timeout=timeout,
        )

    def __str__(self):
        return f"ToolArchives(tool_name={self.tool_name}, version={self.version_str}, arch={self.arch})"

    def _get_archives(self):
        _a = "_x64"
        if self.os_name == "windows":
            _a = "_x86"

        archive_url = posixpath.join(
            # https://download.qt.io/online/qtsdkrepository/
            self.base,
            # linux_x64/
            self.os_name + _a,
            # desktop/
            self.target,
            # tools_ifw/
            self.tool_name,
        )
        update_xml_url = posixpath.join(archive_url, "Updates.xml")
        self._download_update_xml(update_xml_url)  # call super method.
        self._parse_update_xml(archive_url, [])

    def _parse_update_xml(self, archive_url, target_packages):
        try:
            self.update_xml = ElementTree.fromstring(self.update_xml_text)
        except ElementTree.ParseError as perror:
            self.logger.error("Downloaded metadata is corrupted. {}".format(perror))
            raise ArchiveListError("Downloaded metadata is corrupted.")

        for packageupdate in self.update_xml.iter("PackageUpdate"):
            name = packageupdate.find("Name").text
            if name != self.arch:
                continue
            _archives = packageupdate.find("DownloadableArchives").text
            if _archives is not None:
                downloadable_archives = _archives.split(", ")
            else:
                downloadable_archives = []
            named_version = packageupdate.find("Version").text
            full_version = Version(named_version)
            if full_version.truncate("patch") != self.version.truncate("patch"):
                self.logger.warning(
                    "Base Version of {} is different from requested version {} -- skip.".format(
                        named_version, self.version
                    )
                )
                continue
            package_desc = packageupdate.find("Description").text
            for archive in downloadable_archives:
                package_url = posixpath.join(
                    # https://download.qt.io/online/qtsdkrepository/linux_x64/desktop/tools_ifw/
                    archive_url,
                    # qt.tools.ifw.41/
                    name,
                    #  4.1.1-202105261130ifw-linux-x64.7z
                    f"{named_version}{archive}",
                )
                hashurl = package_url + ".sha1"
                self.archives.append(
                    QtPackage(
                        name=name,
                        archive_url=package_url,
                        archive=archive,
                        package_desc=package_desc,
                        hashurl=hashurl,
                    )
                )

    def get_target_config(self) -> TargetConfig:
        """Get target configuration.

        :return tuple of three parameter, "Tools", target and arch
        """
        return TargetConfig("Tools", self.target, self.arch, self.os_name)

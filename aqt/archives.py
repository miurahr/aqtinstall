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
import random
import re
import xml.etree.ElementTree as ElementTree
from logging import getLogger
from typing import Callable, Generator, Iterable, Iterator, List, Optional, Tuple, Union

from semantic_version import SimpleSpec, Version

from aqt.exceptions import ArchiveListError, NoPackageFound
from aqt.helper import Settings, getUrl
import bs4
import requests
from semantic_version import Version

from aqt import helper
from aqt.exceptions import ArchiveListError, CliInputError, NoPackageFound
from aqt.helper import (
    ArchiveId,
    ListOfStr,
    Settings,
    Tools,
    Versions,
    getUrl,
    xml_to_modules,
)


class TargetConfig:
    def __init__(self, version, target, arch, os_name):
        self.version = str(version)
        self.target = target
        self.arch = arch
        self.os_name = os_name


class ListCommand:
    """Encapsulate all parts of the `aqt list` command"""

    def __init__(
        self,
        archive_id: ArchiveId,
        *,
        filter_minor: Optional[int] = None,
        is_latest_version: bool = False,
        modules_ver: Optional[str] = None,
        extensions_ver: Optional[str] = None,
        architectures_ver: Optional[str] = None,
        http_fetcher: Optional[Callable[[str], str]] = None,
    ):
        """
        Construct ListCommand.
        @param filter_minor         When set, the ListCommand will filter out all versions of
                                    Qt that don't match this minor version.
        @param is_latest_version    When True, the ListCommand will find all versions of Qt
                                    matching filters, and only print the most recent version
        @param modules_ver          Version of Qt for which to list modules
        @param extensions_ver       Version of Qt for which to list extensions
        @param architectures_ver    Version of Qt for which to list architectures
        @param http_fetcher         Function used to fetch documents via http
        """
        self.logger = getLogger("aqt")
        self.http_fetcher = (
            http_fetcher if http_fetcher else ListCommand._default_http_fetcher
        )
        self.archive_id = archive_id
        self.filter_minor = filter_minor

        if is_latest_version:
            self.request_type = "latest version"
            self._action = self.fetch_latest_version
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
        elif archive_id.is_tools():
            self.request_type = "tools"
            self._action = self.fetch_tools
        else:
            self.request_type = "versions"
            self._action = self.fetch_versions

    def action(self) -> Union[Optional[Version], ListOfStr, Tools, Versions]:
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
            print(str(output))
            return 0
        except CliInputError as e:
            self.logger.error("Command line input error: {}".format(e))
            return 1
        except requests.RequestException as e:
            self.logger.error("{}".format(e))
            self.print_suggested_follow_up(self.logger.error)
            return 1

    def fetch_modules(self, version: Version) -> helper.ListOfStr:
        return self.get_modules_architectures_for_version(version=version)[0]

    def fetch_arches(self, version: Version) -> helper.ListOfStr:
        return self.get_modules_architectures_for_version(version=version)[1]

    def fetch_extensions(self, version: Version) -> helper.ListOfStr:
        versions_extensions = ListCommand.get_versions_extensions(
            self.http_fetcher(self.archive_id.to_url()), self.archive_id.category
        )
        filtered = filter(
            lambda ver_ext: ver_ext[0] == version and ver_ext[1],
            versions_extensions,
        )
        return ListOfStr(strings=list(map(lambda ver_ext: ver_ext[1], filtered)))

    def fetch_versions(self) -> helper.Versions:
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
            self.http_fetcher(self.archive_id.to_url()), self.archive_id.category
        )
        versions = sorted(
            filter(None, map(get_version, filter(filter_by, versions_extensions)))
        )
        iterables = itertools.groupby(versions, lambda version: version.minor)
        return Versions(iterables)

    def fetch_latest_version(self) -> Optional[Version]:
        return self.fetch_versions().latest()

    def fetch_tools(self) -> helper.Tools:
        html_doc = self.http_fetcher(self.archive_id.to_url())
        return Tools(tools=list(ListCommand.iterate_folders(html_doc, "tools")))

    def _to_version(self, qt_ver: str) -> Version:
        """
        Turns a string in the form of `5.X.Y | latest` into a semantic version.
        If the string does not fit either of these forms, CliInputError will be raised.
        If qt_ver == latest, and no versions exist corresponding to the filters specified,
        then CliInputError will be raised.
        If qt_ver == latest, and an HTTP error occurs, requests.RequestException will be raised.
        @param qt_ver   Either the literal string `latest`, or a semantic version
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
    def _default_http_fetcher(rest_of_url: str):
        settings = Settings()  # Borg/Singleton ensures we get the right settings
        return helper.request_http_with_failover(
            base_urls=[settings.baseurl, random.choice(settings.fallbacks)],
            rest_of_url=rest_of_url,
            timeout=(settings.connection_timeout, settings.response_timeout),
        )

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

        def has_nonempty_downloads(element: ElementTree.Element) -> bool:
            """Returns True if the element has an empty '<DownloadableArchives/>' tag"""
            downloads = element.find("DownloadableArchives")
            return downloads is not None and downloads.text

        rest_of_url = self.archive_id.to_url(
            qt_version_no_dots=qt_ver_str, file="Updates.xml"
        )
        xml = self.http_fetcher(rest_of_url)  # raises RequestException

        # We want the names of modules, regardless of architecture:
        modules = xml_to_modules(
            xml,
            predicate=has_nonempty_downloads,
            keys_to_keep=(),  # Just want names
        )

        def naive_modules_arches(names: Iterable[str]) -> Tuple[ListOfStr, ListOfStr]:
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
            return ListOfStr(strings=sorted(_modules)), ListOfStr(
                strings=sorted(arches)
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

        if self.filter_minor is not None:
            msg = "Please use '{}' to check that versions of {} exist with the minor version '{}'".format(
                base_cmd, self.archive_id.category, self.filter_minor
            )
            printer(msg)


class QtPackage:
    """
    Hold package information.
    """

    def __init__(self, name, archive_url, archive, package_desc, hashurl):
        self.name = name
        self.url = archive_url
        self.archive = archive
        self.desc = package_desc
        self.hashurl = hashurl


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
        self.base = base
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
            update_xml_url = "{0}{1}Updates.xml".format(self.base, archive_path)
            xml_text = getUrl(update_xml_url, self.timeout, self.logger)
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
                        ListInfo(name, display_name, package_desc, virtual)
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
        version,
        arch,
        base,
        subarchives=None,
        modules=None,
        logging=None,
        all_extra=False,
        timeout=(5, 5),
    ):
        self.version = Version(version)
        self.target = target
        self.arch = arch
        self.os_name = os_name
        self.all_extra = all_extra
        self.arch_list = [item.get("arch") for item in Settings().qt_combinations]
        all_archives = subarchives is None
        self.base = base + "/online/qtsdkrepository/"
        if logging:
            self.logger = logging
        else:
            self.logger = getLogger("aqt")
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
        self.update_xml_text = getUrl(update_xml_url, self.timeout, self.logger)

    def _parse_update_xml(self, archive_url, target_packages):
        try:
            self.update_xml = ElementTree.fromstring(self.update_xml_text)
        except ElementTree.ParseError as perror:
            self.logger.error("Downloaded metadata is corrupted. {}".format(perror))
            raise ArchiveListError("Downloaded metadata is corrupted.")
        else:
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
                            package_url = (
                                archive_url + name + "/" + full_version + archive
                            )
                            hashurl = package_url + ".sha1"
                            self.archives.append(
                                QtPackage(
                                    archive_name,
                                    package_url,
                                    archive,
                                    package_desc,
                                    hashurl,
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
        logging=None,
        all_extra=False,
        timeout=(5, 5),
    ):
        self.flavor = flavor
        self.target = target
        self.os_name = os_name
        self.base = base
        super(SrcDocExamplesArchives, self).__init__(
            os_name,
            target,
            version,
            self.flavor,
            base,
            subarchives=subarchives,
            modules=modules,
            logging=logging,
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
        self, os_name, tool_name, version, arch, base, logging=None, timeout=(5, 5)
    ):
        self.tool_name = tool_name
        self.os_name = os_name
        super(ToolArchives, self).__init__(
            os_name, "desktop", version, arch, base, logging=logging, timeout=timeout
        )

    def _get_archives(self):
        if self.os_name == "windows":
            archive_url = self.base + self.os_name + "_x86/" + self.target + "/"
        else:
            archive_url = self.base + self.os_name + "_x64/" + self.target + "/"
        update_xml_url = "{0}{1}/Updates.xml".format(archive_url, self.tool_name)
        self._download_update_xml(update_xml_url)  # call super method.
        self._parse_update_xml(archive_url, [])

    def _parse_update_xml(self, archive_url, target_packages):
        try:
            self.update_xml = ElementTree.fromstring(self.update_xml_text)
        except ElementTree.ParseError as perror:
            self.logger.error("Downloaded metadata is corrupted. {}".format(perror))
            raise ArchiveListError("Downloaded metadata is corrupted.")
        else:
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
                if not full_version.base_version == self.version.base_version:
                    self.logger.warning(
                        "Base Version of {} is different from requested version {} -- skip.".format(
                            named_version, self.version
                        )
                    )
                    continue
                package_desc = packageupdate.find("Description").text
                for archive in downloadable_archives:
                    package_url = (
                        archive_url
                        + self.tool_name
                        + "/"
                        + name
                        + "/"
                        + named_version
                        + archive
                    )
                    hashurl = package_url + ".sha1"
                    self.archives.append(
                        QtPackage(name, package_url, archive, package_desc, hashurl)
                    )

    def get_target_config(self) -> TargetConfig:
        """Get target configuration.

        :return tuple of three parameter, "Tools", target and arch
        """
        return TargetConfig("Tools", self.target, self.arch, self.os_name)

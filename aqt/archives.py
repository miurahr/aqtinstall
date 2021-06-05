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
import xml.etree.ElementTree as ElementTree
from functools import reduce
from logging import getLogger
from typing import Callable, List, Optional, Union

from semantic_version import Version

from aqt import helper
from aqt.exceptions import ArchiveListError, CliInputError, NoPackageFound
from aqt.helper import ArchiveId, Settings, getUrl


class TargetConfig:
    def __init__(self, version, target, arch, os_name):
        self.version = version
        self.target = target
        self.arch = arch
        self.os_name = os_name


# List packages for a particular version of Qt
# Find all versions
class QtDownloadListFetcher:
    """
    Fetches lists of tools and Qt packages that can be downloaded at downloads.qt.io.
    Parses html files and filters data based on an argument list.
    Produces lists of Qt5 versions, Qt6 versions, and lists of tools (openssl, qtifw, etc)
    """

    def __init__(
        self,
        archive_id: ArchiveId,
        filter_minor: Optional[int] = None,
        html_fetcher: Callable[[str], str] = helper.default_http_fetcher,
    ):
        self.archive_id = archive_id
        self.filter_minor = filter_minor
        self.html_fetcher = html_fetcher
        self.logger = getLogger("aqt")

    def run(
        self, *, list_extensions_ver: Optional[Version] = None
    ) -> Union[helper.Versions, helper.Tools, helper.ListOfStr]:
        html_doc = self.html_fetcher(self.archive_id.to_url())
        if list_extensions_ver is not None:
            return helper.get_extensions_for_version(
                list_extensions_ver, self.archive_id, html_doc
            )
        if self.archive_id.is_tools():
            return helper.get_tools(html_doc)
        versions = helper.get_versions_for_minor(
            self.filter_minor, self.archive_id, html_doc
        )
        return versions


class ListCommand:
    """Encapsulate all parts of the `aqt list` command"""

    def __init__(
        self,
        archive_id: ArchiveId,
        filter_minor: Optional[int],
        is_latest_version: bool,
        modules_ver: Optional[str],
        extensions_ver: Optional[str],
        architectures_ver: Optional[str],
        http_fetcher: Optional[Callable[[str], str]] = None,
    ):
        """
        Construct ListCommand.
        Raises `CliInputError` for invalid Qt versions, at time of construction.
        @param filter_minor         When set, the ListCommand will filter out all versions of
                                    Qt that don't match this minor version.
        @param is_latest_version    When True, the ListCommand will find all versions of Qt
                                    matching filters, and only print the most recent version
        @param modules_ver          Version of Qt for which to list modules
        @param extensions_ver       Version of Qt for which to list extensions
        @param architectures_ver    Version of Qt for which to list architectures
        @param http_fetcher         Function to use to fetch documents via http
        """
        self.http_fetcher = (
            http_fetcher if http_fetcher else ListCommand._default_http_fetcher
        )
        self.archive_id = archive_id
        self.filter_minor = filter_minor

        def determine_action() -> Callable[
            [], Union[helper.Versions, helper.Tools, helper.ListOfStr, Version]
        ]:
            """Translate args into the actual command to be run"""
            if is_latest_version:
                return self.get_latest_version

            version: Optional[str] = reduce(
                lambda x, y: x if x else y,
                (modules_ver, extensions_ver, architectures_ver),
                None,
            )
            if version:
                if self.archive_id.is_major_ver_mismatch(version):
                    msg = "Major version mismatch between {} and {}".format(
                        self.archive_id.category, version
                    )
                    raise CliInputError(msg)
                get_ver = self._transform_qt_ver_with_dots(version)

                if modules_ver:
                    return lambda: self.fetch_modules(get_ver)
                elif extensions_ver:
                    return lambda: self.fetch_extensions(get_ver)
                elif architectures_ver:
                    return lambda: self.fetch_arches(get_ver)
                else:
                    assert False, "This branch should be unreachable"

            return self.list_all_versions

        self._action = determine_action()
        self.logger = getLogger("aqt")

    def run(self) -> int:
        try:
            output = self._action()
            if not output:
                self.logger.info("No data available for this request.")
                return 1
            print(str(output))
            return 0
        except Exception as e:
            self.logger.error("{}".format(e))
            return 1

    def list_all_versions(self) -> helper.Versions:
        return QtDownloadListFetcher(
            archive_id=self.archive_id,
            filter_minor=self.filter_minor,
            html_fetcher=self.http_fetcher,
        ).run()

    def get_latest_version(self) -> Version:
        return self.list_all_versions().latest()

    def fetch_modules(self, get_version: Callable[[], Version]) -> helper.ListOfStr:
        return helper.get_modules_architectures_for_version(
            version=get_version(),
            archive_id=self.archive_id,
            http_fetcher=self.http_fetcher,
        )[0]

    def fetch_arches(self, get_version: Callable[[], Version]) -> helper.ListOfStr:
        return helper.get_modules_architectures_for_version(
            version=get_version(),
            archive_id=self.archive_id,
            http_fetcher=self.http_fetcher,
        )[1]

    def fetch_extensions(self, get_version: Callable[[], Version]) -> helper.ListOfStr:
        return QtDownloadListFetcher(
            archive_id=self.archive_id,
            filter_minor=self.filter_minor,
            html_fetcher=self.http_fetcher,
        ).run(list_extensions_ver=get_version())

    def _transform_qt_ver_with_dots(self, qt_ver: str) -> Callable[[], Version]:
        """
        Returns a function that returns a semantic version.
        This allows lazy-evaluation, in the case that qt_ver is the string `latest`.
        Otherwise, if qt_ver is not a valid semantic version, CliInputError will be
        raised immediately.

        @param qt_ver   Either the literal string `latest`, or a semantic version
                        with each part separated with dots.
        """
        assert qt_ver
        if qt_ver == "latest":
            return self.get_latest_version
        version = helper.to_version(qt_ver)
        return lambda: version

    @staticmethod
    def _default_http_fetcher(rest_of_url: str):
        return helper.default_http_fetcher(rest_of_url)


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
        self.version = version
        self.os_name = os_name
        self.target = target
        self.archives = []
        self.base = base
        self.timeout = timeout
        self.logger = getLogger("aqt")
        self._get_archives()

    def _get_archives(self):
        qt_ver_num = self.version.replace(".", "")
        self.qt_ver_base = self.version[0:1]
        # Get packages index
        if self.qt_ver_base == "6" and self.target == "android":
            arch_ext = ["_armv7/", "_x86/", "_x86_64/", "_arm64_v8a/"]
        elif (
            self.qt_ver_base == "5"
            and int(qt_ver_num) >= 5130
            and self.target == "desktop"
        ):
            arch_ext = ["/", "_wasm/"]
        else:
            arch_ext = ["/"]
        for ext in arch_ext:
            archive_path = "{0}{1}{2}/qt{3}_{4}{5}".format(
                self.os_name,
                "_x86/" if self.os_name == "windows" else "_x64/",
                self.target,
                self.qt_ver_base,
                qt_ver_num,
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
        self.version = version
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
        qt_ver_num = self.version.replace(".", "")
        self.qt_ver_base = self.version[0:1]
        if all_extra:
            self.all_extra = True
        else:
            for m in modules if modules is not None else []:
                self.mod_list.append(
                    "qt.qt{}.{}.{}.{}".format(self.qt_ver_base, qt_ver_num, m, arch)
                )
                self.mod_list.append("qt.{}.{}.{}".format(qt_ver_num, m, arch))
        self.timeout = timeout
        self._get_archives(qt_ver_num)
        if not all_archives:
            self.archives = list(filter(lambda a: a.name in subarchives, self.archives))

    def _get_archives(self, qt_ver_num):
        # Get packages index
        if self.arch == "wasm_32":
            arch_ext = "_wasm"
        elif self.arch.startswith("android_") and qt_ver_num[0:1] == "6":
            arch_ext = "{}".format(self.arch[7:])
        else:
            arch_ext = ""
        archive_path = "{0}{1}{2}/qt{3}_{4}{5}/".format(
            self.os_name,
            "_x86/" if self.os_name == "windows" else "_x64/",
            self.target,
            self.qt_ver_base,
            qt_ver_num,
            arch_ext,
        )
        update_xml_url = "{0}{1}Updates.xml".format(self.base, archive_path)
        archive_url = "{0}{1}".format(self.base, archive_path)
        target_packages = []
        target_packages.append(
            "qt.qt{}.{}.{}".format(self.qt_ver_base, qt_ver_num, self.arch)
        )
        target_packages.append("qt.{}.{}".format(qt_ver_num, self.arch))
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

    def _get_archives(self, qt_ver_num):
        archive_path = "{0}{1}{2}/qt{3}_{4}{5}".format(
            self.os_name,
            "_x86/" if self.os_name == "windows" else "_x64/",
            self.target,
            self.qt_ver_base,
            qt_ver_num,
            "_src_doc_examples/",
        )
        archive_url = "{0}{1}".format(self.base, archive_path)
        update_xml_url = "{0}/Updates.xml".format(archive_url)
        target_packages = []
        target_packages.append(
            "qt.qt{}.{}.{}".format(self.qt_ver_base, qt_ver_num, self.flavor)
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

    def _get_archives(self, qt_ver_num):
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
                full_version = packageupdate.find("Version").text
                if not full_version.startswith(self.version):
                    self.logger.warning(
                        "Version {} differ from requested version {} -- skip.".format(
                            full_version, self.version
                        )
                    )
                    continue
                named_version = full_version
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

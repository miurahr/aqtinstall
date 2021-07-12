#!/usr/bin/env python
#
# Copyright (C) 2021 David Dalcino
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
import operator
import posixpath
import random
import re
from logging import getLogger
from typing import (
    Callable,
    Dict,
    Generator,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)
from xml.etree import ElementTree as ElementTree

import bs4
from semantic_version import SimpleSpec as SemanticSimpleSpec
from semantic_version import Version as SemanticVersion
from texttable import Texttable

from aqt.exceptions import ArchiveConnectionError, ArchiveDownloadError, CliInputError
from aqt.helper import Settings, getUrl, xml_to_modules


class SimpleSpec(SemanticSimpleSpec):
    pass


class Version(SemanticVersion):
    """Override semantic_version.Version class
    to accept Qt versions and tools versions
    If the version ends in `-preview`, the version is treated as a preview release.
    """

    def __init__(
        self,
        version_string=None,
        major=None,
        minor=None,
        patch=None,
        prerelease=None,
        build=None,
        partial=False,
    ):
        if version_string is None:
            super(Version, self).__init__(
                version_string=None,
                major=major,
                minor=minor,
                patch=patch,
                prerelease=prerelease,
                build=build,
                partial=partial,
            )
            return
        # test qt versions
        match = re.match(r"^(\d+)\.(\d+)(\.(\d+)|-preview)$", version_string)
        if not match:
            # bad input
            raise ValueError("Invalid version string: '{}'".format(version_string))
        major, minor, end, patch = match.groups()
        is_preview = end == "-preview"
        super(Version, self).__init__(
            major=int(major),
            minor=int(minor),
            patch=int(patch) if patch else 0,
            prerelease=("preview",) if is_preview else None,
        )

    def __str__(self):
        if self.prerelease:
            return "{}.{}-preview".format(self.major, self.minor)
        return super(Version, self).__str__()

    @classmethod
    def permissive(cls, version_string: str):
        """Converts a version string with dots (5.X.Y, etc) into a semantic version.
        If the version omits either the patch or minor versions, they will be filled in with zeros,
        and the remaining version string becomes part of the prerelease component.
        If the version cannot be converted to a Version, a ValueError is raised.

        This is intended to be used on Version tags in an Updates.xml file.

        '1.33.1-202102101246' => Version('1.33.1-202102101246')
        '1.33-202102101246' => Version('1.33.0-202102101246')    # tools_conan
        '2020-05-19-1' => Version('2020.0.0-05-19-1')            # tools_vcredist
        """

        match = re.match(r"^(\d+)(\.(\d+)(\.(\d+))?)?(-(.+))?$", version_string)
        if not match:
            raise ValueError("Invalid version string: '{}'".format(version_string))
        major, dot_minor, minor, dot_patch, patch, hyphen_build, build = match.groups()
        return cls(
            major=int(major),
            minor=int(minor) if minor else 0,
            patch=int(patch) if patch else 0,
            build=(build,) if build else None,
        )


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

    def __format__(self, format_spec) -> str:
        if format_spec == "":
            return "\n".join(
                " ".join(str(version) for version in minor_list)
                for minor_list in self.versions
            )
        elif format_spec == "s":
            return str(self.versions)
        else:
            raise TypeError("Unsupported format.")

    def __bool__(self):
        return len(self.versions) > 0 and len(self.versions[0]) > 0

    def latest(self) -> Optional[Version]:
        if not self:
            return None
        return self.versions[-1][-1]

    def __iter__(self) -> List[Version]:
        for item in self.versions:
            yield item


def get_semantic_version(qt_ver: str, is_preview: bool) -> Optional[Version]:
    """Converts a Qt version string (596, 512, 5132, etc) into a semantic version.
    This makes a lot of assumptions based on established patterns:
    If is_preview is True, the number is interpreted as ver[0].ver[1:], with no patch.
    If the version is 3 digits, then major, minor, and patch each get 1 digit.
    If the version is 4 or more digits, then major gets 1 digit, minor gets 2 digits
    and patch gets all the rest.
    As of May 2021, the version strings at https://download.qt.io/online/qtsdkrepository
    conform to this pattern; they are not guaranteed to do so in the future.
    """
    if not qt_ver or any(not ch.isdigit() for ch in qt_ver):
        return None
    if is_preview:
        return Version(
            major=int(qt_ver[:1]),
            minor=int(qt_ver[1:]),
            patch=0,
            prerelease=("preview",),
        )
    elif len(qt_ver) >= 4:
        return Version(
            major=int(qt_ver[:1]), minor=int(qt_ver[1:3]), patch=int(qt_ver[3:])
        )
    elif len(qt_ver) == 3:
        return Version(
            major=int(qt_ver[:1]), minor=int(qt_ver[1:2]), patch=int(qt_ver[2:])
        )
    elif len(qt_ver) == 2:
        return Version(major=int(qt_ver[:1]), minor=int(qt_ver[1:2]), patch=0)
    raise ValueError("Invalid version string '{}'".format(qt_ver))


class ArchiveId:
    CATEGORIES = ("tools", "qt5", "qt6")
    HOSTS = ("windows", "mac", "linux")
    TARGETS_FOR_HOST = {
        "windows": ["android", "desktop", "winrt"],
        "mac": ["android", "desktop", "ios"],
        "linux": ["android", "desktop"],
    }
    ALL_EXTENSIONS = (
        "wasm",
        "src_doc_examples",
        "preview",
        "wasm_preview",
        "x86_64",
        "x86",
        "armv7",
        "arm64_v8a",
    )

    def __init__(self, category: str, host: str, target: str, extension: str = ""):
        if category not in ArchiveId.CATEGORIES:
            raise ValueError("Category '{}' is invalid".format(category))
        if host not in ArchiveId.HOSTS:
            raise ValueError("Host '{}' is invalid".format(host))
        if target not in ArchiveId.TARGETS_FOR_HOST[host]:
            raise ValueError("Target '{}' is invalid".format(target))
        if extension and extension not in ArchiveId.ALL_EXTENSIONS:
            raise ValueError("Extension '{}' is invalid".format(extension))
        self.category: str = category
        self.host: str = host
        self.target: str = target
        self.extension: str = extension

    def is_preview(self) -> bool:
        return "preview" in self.extension if self.extension else False

    def is_qt(self) -> bool:
        return self.category.startswith("qt")

    def is_tools(self) -> bool:
        return self.category == "tools"

    def is_no_arch(self) -> bool:
        """Returns True if there should be no arch attached to the module names"""
        return self.extension in ("src_doc_examples",)

    def is_major_ver_mismatch(self, qt_version: Version) -> bool:
        """Returns True if the version specifies a version different from the specified category"""
        return self.is_qt() and int(self.category[-1]) != qt_version.major

    def to_url(self, qt_version_no_dots: Optional[str] = None, file: str = "") -> str:
        base = "online/qtsdkrepository/{os}{arch}/{target}/".format(
            os=self.host,
            arch="_x86" if self.host == "windows" else "_x64",
            target=self.target,
        )
        if not qt_version_no_dots:
            return base
        folder = "{category}_{ver}{ext}/".format(
            category=self.category,
            ver=qt_version_no_dots,
            ext="_" + self.extension if self.extension else "",
        )
        return base + folder + file

    def __str__(self) -> str:
        return "{cat}/{host}/{target}{ext}".format(
            cat=self.category,
            host=self.host,
            target=self.target,
            ext="" if not self.extension else "/" + self.extension,
        )


class Table:
    def __init__(self, head: List[str], rows: List[List[str]], max_width: int = 0):
        # max_width is set to 0 by default: this disables wrapping of text table cells
        self.head = head
        self.rows = rows
        self.max_width = max_width

    def __format__(self, format_spec) -> str:
        if format_spec == "":
            table = Texttable(max_width=self.max_width)
            table.set_deco(Texttable.HEADER)
            table.header(self.head)
            table.add_rows(self.rows, header=False)
            return table.draw()
        elif format_spec == "s":
            return str(self)
        else:
            raise ValueError()


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
        tool_name: Optional[str] = None,
        tool_long_listing: Optional[str] = None,
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
            elif tool_long_listing:
                self.request_type = "tool long listing"
                self._action = lambda: self.fetch_tool_long_listing(tool_long_listing)
            else:
                self.request_type = "tools"
                self._action = self.fetch_tools
        elif is_latest_version:
            self.request_type = "latest version"
            self._action = lambda: Versions(self.fetch_latest_version())
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

    def action(self) -> Union[List[str], Versions, Table]:
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
            if isinstance(output, Versions) or isinstance(output, Table):
                print(format(output))
            elif self.archive_id.is_tools():
                print(*output, sep="\n")
            else:
                print(*output, sep=" ")
            return 0
        except CliInputError as e:
            self.logger.error("Command line input error: {}".format(e))
            return 1
        except (ArchiveConnectionError, ArchiveDownloadError) as e:
            self.logger.error("{}".format(e))
            self.print_suggested_follow_up(self.logger.error)
            return 1

    def fetch_modules(self, version: Version) -> List[str]:
        return self.get_modules_architectures_for_version(version=version)[0]

    def fetch_arches(self, version: Version) -> List[str]:
        return self.get_modules_architectures_for_version(version=version)[1]

    def fetch_extensions(self, version: Version) -> List[str]:
        versions_extensions = ListCommand.get_versions_extensions(
            self.fetch_http(self.archive_id.to_url()), self.archive_id.category
        )
        filtered = filter(
            lambda ver_ext: ver_ext[0] == version and ver_ext[1],
            versions_extensions,
        )
        return list(map(lambda ver_ext: ver_ext[1], filtered))

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
        return Versions(iterables)

    def fetch_latest_version(self) -> Optional[Version]:
        return self.fetch_versions().latest()

    def fetch_tools(self) -> List[str]:
        html_doc = self.fetch_http(self.archive_id.to_url())
        return list(ListCommand.iterate_folders(html_doc, "tools"))

    def _fetch_tool_data(
        self, tool_name: str, keys_to_keep: Optional[Iterable[str]] = None
    ) -> Dict[str, Dict[str, str]]:
        # raises ArchiveDownloadError, ArchiveConnectionError
        rest_of_url = self.archive_id.to_url() + tool_name + "/Updates.xml"
        xml = self.fetch_http(rest_of_url)
        modules = xml_to_modules(
            xml,
            predicate=ListCommand._has_nonempty_downloads,
            keys_to_keep=keys_to_keep,
        )
        return modules

    def fetch_tool_modules(self, tool_name: str) -> List[str]:
        tool_data = self._fetch_tool_data(tool_name, keys_to_keep=())
        return list(tool_data.keys())

    def fetch_tool_by_simple_spec(
        self, tool_name: str, simple_spec: SimpleSpec
    ) -> Optional[Dict[str, str]]:
        # Get data for all the tool modules
        all_tools_data = self._fetch_tool_data(tool_name)
        return ListCommand.choose_highest_version_in_spec(all_tools_data, simple_spec)

    def fetch_tool_long_listing(self, tool_name: str) -> Table:
        head = [
            "Tool Variant Name",
            "Version",
            "Release Date",
            "Display Name",
            "Description",
        ]
        keys = ("Version", "ReleaseDate", "DisplayName", "Description")
        tool_data = self._fetch_tool_data(tool_name, keys_to_keep=keys)
        rows = [
            [name, *[content[key] for key in keys]]
            for name, content in tool_data.items()
        ]
        return Table(head, rows)

    @staticmethod
    def choose_highest_version_in_spec(
        all_tools_data: Dict[str, Dict[str, str]], simple_spec: SimpleSpec
    ) -> Optional[Dict[str, str]]:
        # Get versions of all modules. Fail if version cannot be determined.
        try:
            tools_versions = [
                (name, tool_data, Version.permissive(tool_data["Version"]))
                for name, tool_data in all_tools_data.items()
            ]
        except ValueError:
            return None

        # Remove items that don't conform to simple_spec
        tools_versions = filter(
            lambda tool_item: tool_item[2] in simple_spec, tools_versions
        )

        try:
            # Return the conforming item with the highest version.
            # If there are multiple items with the same version, the result will not be predictable.
            return max(tools_versions, key=operator.itemgetter(2))[1]
        except ValueError:
            # There were no tools that fit the simple_spec
            return None

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
        try:
            version = Version(qt_ver)
        except ValueError as e:
            raise CliInputError(e)
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
                get_semantic_version(qt_ver=ver, is_preview="preview" in ext),
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
    ) -> Tuple[List[str], List[str]]:
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
        ) -> Tuple[List[str], List[str]]:
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
                sorted(_modules),
                sorted(arches),
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

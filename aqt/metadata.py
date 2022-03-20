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
import re
import secrets as random
import shutil
from logging import getLogger
from typing import Callable, Dict, Generator, Iterable, Iterator, List, Optional, Tuple, Union
from xml.etree.ElementTree import Element

import bs4
from semantic_version import SimpleSpec as SemanticSimpleSpec
from semantic_version import Version as SemanticVersion
from texttable import Texttable

from aqt.exceptions import ArchiveConnectionError, ArchiveDownloadError, ArchiveListError, CliInputError, EmptyMetadata
from aqt.helper import Settings, get_hash, getUrl, xml_to_modules


class SimpleSpec(SemanticSimpleSpec):
    pass

    @staticmethod
    def usage() -> str:
        return (
            "See documentation at: "
            "https://python-semanticversion.readthedocs.io/en/latest/reference.html#semantic_version.SimpleSpec\n"
            "Examples:\n"
            '* "*": matches everything\n'
            '* "5": matches every version with major=5\n'
            '* "5.6": matches every version beginning with 5.6\n'
            '* "5.*.3": matches versions with major=5 and patch=3'
        )


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
            self.versions: List[List[Version]] = [list(versions_iterator) for _, versions_iterator in versions]

    def __str__(self) -> str:
        return str(self.versions)

    def __format__(self, format_spec) -> str:
        if format_spec == "":
            return "\n".join(" ".join(str(version) for version in minor_list) for minor_list in self.versions)
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

    def __iter__(self) -> Generator[List[Version], None, None]:
        for item in self.versions:
            yield item

    def flattened(self) -> List[Version]:
        """Return a flattened list of all versions"""
        return [version for row in self for version in row]


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
        return Version(major=int(qt_ver[:1]), minor=int(qt_ver[1:3]), patch=int(qt_ver[3:]))
    elif len(qt_ver) == 3:
        return Version(major=int(qt_ver[:1]), minor=int(qt_ver[1:2]), patch=int(qt_ver[2:]))
    elif len(qt_ver) == 2:
        return Version(major=int(qt_ver[:1]), minor=int(qt_ver[1:2]), patch=0)
    raise ValueError("Invalid version string '{}'".format(qt_ver))


class ArchiveId:
    CATEGORIES = ("tools", "qt")
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
    EXTENSIONS_REQUIRED_ANDROID_QT6 = "x86_64", "x86", "armv7", "arm64_v8a"

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
        return self.category == "qt"

    def is_tools(self) -> bool:
        return self.category == "tools"

    def is_no_arch(self) -> bool:
        """Returns True if there should be no arch attached to the module names"""
        return self.extension in ("src_doc_examples",)

    def to_url(self) -> str:
        return "online/qtsdkrepository/{os}{arch}/{target}/".format(
            os=self.host,
            arch="_x86" if self.host == "windows" else "_x64",
            target=self.target,
        )

    def to_folder(self, qt_version_no_dots: str) -> str:
        return "{category}{major}_{ver}{ext}".format(
            category=self.category,
            major=qt_version_no_dots[0],
            ver=qt_version_no_dots,
            ext="_" + self.extension if self.extension else "",
        )

    def __str__(self) -> str:
        return "{cat}/{host}/{target}{ext}".format(
            cat=self.category,
            host=self.host,
            target=self.target,
            ext="" if not self.extension else "/" + self.extension,
        )


class ToolData:
    """A data class hold tool details."""

    head = [
        "Tool Variant Name",
        "Version",
        "Release Date",
        "Display Name",
        "Description",
    ]

    short_head = [
        "Tool Variant Name",
        "Version",
        "Release Date",
    ]

    def __init__(self, tool_data: Dict[str, Dict[str, str]]):
        self.tool_data: Dict[str, Dict[str, str]] = tool_data
        for key in tool_data.keys():
            self.tool_data[key]["Description"] = tool_data[key]["Description"].replace("<br>", "\n")

    def __format__(self, format_spec: str) -> str:
        short = False
        if format_spec == "{:s}":
            return str(self)
        if format_spec == "":
            max_width: int = 0
        elif format_spec == "{:T}":
            short = True
            max_width = 0
        else:
            match = re.match(r"\{?:?(\d+)t\}?", format_spec)
            if match:
                g = match.groups()
                max_width = int(g[0])
            else:
                raise ValueError("Wrong format {}".format(format_spec))
        table = Texttable(max_width=max_width)
        table.set_deco(Texttable.HEADER)
        if short:
            table.header(self.short_head)
            table.add_rows(self._short_rows(), header=False)
        else:
            table.header(self.head)
            table.add_rows(self._rows(), header=False)
        return table.draw()

    def __bool__(self):
        return bool(self.tool_data)

    def _rows(self):
        keys = ("Version", "ReleaseDate", "DisplayName", "Description")
        return [[name, *[content[key] for key in keys]] for name, content in self.tool_data.items()]

    def _short_rows(self):
        keys = ("Version", "ReleaseDate")
        return [[name, *[content[key] for key in keys]] for name, content in self.tool_data.items()]


class QtRepoProperty:
    """
    Describes properties of the Qt repository at https://download.qt.io/online/qtsdkrepository.
    Intended to help decouple the logic of aqt from specific properties of the Qt repository.
    """

    @staticmethod
    def extension_for_arch(architecture: str, is_version_ge_6: bool) -> str:
        if architecture == "wasm_32":
            return "wasm"
        elif architecture.startswith("android_") and is_version_ge_6:
            ext = architecture[len("android_") :]
            if ext in ArchiveId.EXTENSIONS_REQUIRED_ANDROID_QT6:
                return ext
        return ""

    @staticmethod
    def possible_extensions_for_arch(arch: str) -> List[str]:
        """Assumes no knowledge of the Qt version"""

        # ext_ge_6: the extension if the version is greater than or equal to 6.0.0
        # ext_lt_6: the extension if the version is less than 6.0.0
        ext_lt_6, ext_ge_6 = [QtRepoProperty.extension_for_arch(arch, is_ge_6) for is_ge_6 in (False, True)]
        if ext_lt_6 == ext_ge_6:
            return [ext_lt_6]
        return [ext_lt_6, ext_ge_6]


class MetadataFactory:
    """Retrieve metadata of Qt variations, versions, and descriptions from Qt site."""

    def __init__(
        self,
        archive_id: ArchiveId,
        *,
        spec: Optional[SimpleSpec] = None,
        is_latest_version: bool = False,
        modules_query: Optional[Tuple[str, str]] = None,
        extensions_ver: Optional[str] = None,
        architectures_ver: Optional[str] = None,
        archives_query: Optional[List[str]] = None,
        src_doc_examples_query: Optional[Tuple[str, Version, bool]] = None,
        tool_name: Optional[str] = None,
        is_long_listing: bool = False,
    ):
        """
        Construct MetadataFactory.

        :param spec:                When set, the MetadataFactory will filter out all versions of
                                    Qt that don't fit this SimpleSpec.
        :param is_latest_version:   When True, the MetadataFactory will find all versions of Qt
                                    matching filters, and only print the most recent version
        :param modules_query:       [Version of Qt, architecture] for which to list modules
        :param extensions_ver:      Version of Qt for which to list extensions
        :param architectures_ver:   Version of Qt for which to list architectures
        :param archives_query:      [Qt_Version, architecture, *module_names]: used to print list of archives
        :param tool_name:           Name of a tool, without architecture, ie "tools_qtcreator" or "tools_ifw"
        :param is_long_listing:     If true, long listing is used for tools output
        """
        self.logger = getLogger("aqt.metadata")
        self.archive_id = archive_id
        self.spec = spec

        if archive_id.is_tools():
            if tool_name:
                if not tool_name.startswith("tools_"):
                    tool_name = "tools_" + tool_name
                if is_long_listing:
                    self.request_type = "tool long listing"
                    self._action = lambda: self.fetch_tool_long_listing(tool_name)
                else:
                    self.request_type = "tool variant names"
                    self._action = lambda: self.fetch_tool_modules(tool_name)
            else:
                self.request_type = "tools"
                self._action = self.fetch_tools
        elif is_latest_version:
            self.request_type = "latest version"
            self._action = lambda: Versions(self.fetch_latest_version())
        elif modules_query:
            self.request_type = "modules"
            version, arch = modules_query
            self._action = lambda: self.fetch_modules(self._to_version(version), arch)
        elif extensions_ver:
            self.request_type = "extensions"
            self._action = lambda: self.fetch_extensions(self._to_version(extensions_ver))
        elif architectures_ver:
            self.request_type = "architectures"
            self._action = lambda: self.fetch_arches(self._to_version(architectures_ver))
        elif archives_query:
            if len(archives_query) < 2:
                raise CliInputError("The '--archives' flag requires a 'QT_VERSION' and an 'ARCHITECTURE' parameter.")
            self.request_type = "archives for modules" if len(archives_query) > 2 else "archives for qt"
            version, arch, modules = archives_query[0], archives_query[1], archives_query[2:]
            self._action = lambda: self.fetch_archives(self._to_version(version), arch, modules)
        elif src_doc_examples_query:
            cmd_type, version, is_modules_query = src_doc_examples_query
            if is_modules_query:
                self.request_type = f"modules for {cmd_type}"
                self._action = lambda: self.fetch_modules_sde(cmd_type, version)
            else:
                self.request_type = f"archives for {cmd_type}"
                self._action = lambda: self.fetch_archives_sde(cmd_type, version)
        else:
            self.request_type = "versions"
            self._action = self.fetch_versions

    def getList(self) -> Union[List[str], Versions, ToolData]:
        return self._action()

    def fetch_arches(self, version: Version) -> List[str]:
        self.validate_extension(version)
        if self.archive_id.extension == "src_doc_examples":
            return []
        qt_ver_str = self._get_qt_version_str(version)
        modules = self._fetch_module_metadata(self.archive_id.to_folder(qt_ver_str))

        arches = []
        for name in modules.keys():
            ver, arch = name.split(".")[-2:]
            if ver == qt_ver_str:
                arches.append(arch)

        return arches

    def fetch_extensions(self, version: Version) -> List[str]:
        versions_extensions = MetadataFactory.get_versions_extensions(
            self.fetch_http(self.archive_id.to_url(), False), self.archive_id.category
        )
        filtered = filter(
            lambda ver_ext: ver_ext[0] == version and ver_ext[1],
            versions_extensions,
        )
        return list(map(lambda ver_ext: ver_ext[1], filtered))

    def fetch_versions(self) -> Versions:
        def filter_by(ver_ext: Tuple[Optional[Version], str]) -> bool:
            version, extension = ver_ext
            return version and (self.spec is None or version in self.spec) and (self.archive_id.extension == extension)

        def get_version(ver_ext: Tuple[Version, str]):
            return ver_ext[0]

        versions_extensions = MetadataFactory.get_versions_extensions(
            self.fetch_http(self.archive_id.to_url(), False), self.archive_id.category
        )
        versions = sorted(filter(None, map(get_version, filter(filter_by, versions_extensions))))
        iterables = itertools.groupby(versions, lambda version: version.minor)
        return Versions(iterables)

    def fetch_latest_version(self) -> Optional[Version]:
        return self.fetch_versions().latest()

    def fetch_tools(self) -> List[str]:
        html_doc = self.fetch_http(self.archive_id.to_url(), False)
        return list(MetadataFactory.iterate_folders(html_doc, "tools"))

    def fetch_tool_modules(self, tool_name: str) -> List[str]:
        tool_data = self._fetch_module_metadata(tool_name)
        return list(tool_data.keys())

    def fetch_tool_by_simple_spec(self, tool_name: str, simple_spec: SimpleSpec) -> Optional[Dict[str, str]]:
        # Get data for all the tool modules
        all_tools_data = self._fetch_module_metadata(tool_name)
        return self.choose_highest_version_in_spec(all_tools_data, simple_spec)

    def fetch_tool_long_listing(self, tool_name: str) -> ToolData:
        return ToolData(self._fetch_module_metadata(tool_name))

    def validate_extension(self, qt_ver: Version) -> None:
        """
        Checks extension, and raises CliInputError if invalid.

        Rules:
        1. On Qt6 for Android, an extension for processor architecture is required.
        2. On any platform other than Android, or on Qt5, an extension for
        processor architecture is forbidden.
        3. The "wasm" extension only works on desktop targets for Qt 5.13-5.15, or for 6.2+
        """
        if (
            self.archive_id.target == "android"
            and qt_ver.major == 6
            and self.archive_id.extension not in ArchiveId.EXTENSIONS_REQUIRED_ANDROID_QT6
        ):
            raise CliInputError(
                "Qt 6 for Android requires one of the following extensions: "
                f"{ArchiveId.EXTENSIONS_REQUIRED_ANDROID_QT6}. "
                "Please add your extension using the `--extension` flag."
            )
        if self.archive_id.extension in ArchiveId.EXTENSIONS_REQUIRED_ANDROID_QT6 and (
            self.archive_id.target != "android" or qt_ver.major != 6
        ):
            raise CliInputError(f"The extension '{self.archive_id.extension}' is only valid for Qt 6 for Android")
        is_in_wasm_range = qt_ver in SimpleSpec(">=5.13,<6") or qt_ver in SimpleSpec(">=6.2.0")
        if "wasm" in self.archive_id.extension and (self.archive_id.target != "desktop" or not is_in_wasm_range):
            raise CliInputError(
                f"The extension '{self.archive_id.extension}' is only available in Qt 5.13-5.15 and 6.2+ on desktop."
            )

    @staticmethod
    def choose_highest_version_in_spec(
        all_tools_data: Dict[str, Dict[str, str]], simple_spec: SimpleSpec
    ) -> Optional[Dict[str, str]]:
        # Get versions of all modules. Fail if version cannot be determined.
        try:
            tools_versions = [
                (name, tool_data, Version.permissive(tool_data["Version"])) for name, tool_data in all_tools_data.items()
            ]
        except ValueError:
            return None

        # Remove items that don't conform to simple_spec
        tools_versions = filter(lambda tool_item: tool_item[2] in simple_spec, tools_versions)

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
                msg = "There is no latest version of Qt with the criteria '{}'".format(self.describe_filters())
                raise CliInputError(msg)
            return latest_version
        try:
            version = Version(qt_ver)
        except ValueError as e:
            raise CliInputError(e) from e
        return version

    @staticmethod
    def fetch_http(rest_of_url: str, is_check_hash: bool = True) -> str:
        timeout = (Settings.connection_timeout, Settings.response_timeout)
        expected_hash = get_hash(rest_of_url, "sha256", timeout) if is_check_hash else None
        base_urls = Settings.baseurl, random.choice(Settings.fallbacks)
        for i, base_url in enumerate(base_urls):
            try:
                url = posixpath.join(base_url, rest_of_url)
                return getUrl(url=url, timeout=timeout, expected_hash=expected_hash)

            except (ArchiveDownloadError, ArchiveConnectionError) as e:
                if i == len(base_urls) - 1:
                    raise e from e
                else:
                    getLogger("aqt.metadata").debug(
                        f"Connection to '{base_url}' failed. Retrying with fallback '{base_urls[i + 1]}'."
                    )

    @staticmethod
    def iterate_folders(html_doc: str, filter_category: str = "") -> Generator[str, None, None]:
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
    def get_versions_extensions(html_doc: str, category: str) -> Iterator[Tuple[Optional[Version], str]]:
        def folder_to_version_extension(folder: str) -> Tuple[Optional[Version], str]:
            components = folder.split("_", maxsplit=2)
            ext = "" if len(components) < 3 else components[2]
            ver = "" if len(components) < 2 else components[1]
            return (
                get_semantic_version(qt_ver=ver, is_preview="preview" in ext),
                ext,
            )

        return map(
            folder_to_version_extension,
            MetadataFactory.iterate_folders(html_doc, category),
        )

    @staticmethod
    def _has_nonempty_downloads(element: Element) -> bool:
        """Returns True if the element has a nonempty '<DownloadableArchives/>' tag"""
        downloads = element.find("DownloadableArchives")
        update_file = element.find("UpdateFile")
        if downloads is None or update_file is None:
            return False
        uncompressed_size = int(update_file.attrib["UncompressedSize"])
        return downloads.text and uncompressed_size >= Settings.min_module_size

    def _get_qt_version_str(self, version: Version) -> str:
        """Returns a Qt version, without dots, that works in the Qt repo urls and Updates.xml files"""
        # NOTE: The url at `<base>/<host>/<target>/qt5_590/` does not exist; the real one is `qt5_59`
        patch = (
            ""
            if version.prerelease or self.archive_id.is_preview() or version in SimpleSpec("5.9.0")
            else str(version.patch)
        )
        return f"{version.major}{version.minor}{patch}"

    def _fetch_module_metadata(self, folder: str, predicate: Optional[Callable[[Element], bool]] = None):
        rest_of_url = posixpath.join(self.archive_id.to_url(), folder, "Updates.xml")
        xml = self.fetch_http(rest_of_url)
        return xml_to_modules(
            xml,
            predicate=predicate if predicate else MetadataFactory._has_nonempty_downloads,
        )

    def fetch_modules(self, version: Version, arch: str) -> List[str]:
        """Returns list of modules"""
        self.validate_extension(version)
        qt_ver_str = self._get_qt_version_str(version)
        # Example: re.compile(r"^(preview\.)?qt\.(qt5\.)?590\.(.+)$")
        pattern = re.compile(r"^(preview\.)?qt\.(qt" + str(version.major) + r"\.)?" + qt_ver_str + r"\.(.+)$")
        modules_meta = self._fetch_module_metadata(self.archive_id.to_folder(qt_ver_str))

        def to_module_arch(name: str) -> Tuple[Optional[str], Optional[str]]:
            _match = pattern.match(name)
            if not _match:
                return None, None
            module_with_arch = _match.group(3)
            if self.archive_id.is_no_arch() or "." not in module_with_arch:
                return module_with_arch, None
            module, arch = module_with_arch.rsplit(".", 1)
            if module.startswith("addons."):
                module = module[len("addons.") :]
            return module, arch

        modules = set()
        for name in modules_meta.keys():
            module, _arch = to_module_arch(name)
            if _arch == arch:
                modules.add(module)
        return sorted(modules)

    def fetch_modules_sde(self, cmd_type: str, version: Version) -> List[str]:
        """Returns list of modules for src/doc/examples"""
        assert (
            cmd_type in ("doc", "examples") and self.archive_id.target == "desktop"
        ), "Internal misuse of fetch_modules_sde"
        self.validate_extension(version)
        qt_ver_str = self._get_qt_version_str(version)
        modules_meta = self._fetch_module_metadata(self.archive_id.to_folder(qt_ver_str))
        # pattern: Match all names "qt.qt5.12345.doc.(\w+)
        pattern = re.compile(r"^qt\.(qt" + str(version.major) + r"\.)?" + qt_ver_str + r"\." + cmd_type + r"\.(.+)$")

        modules: List[str] = []
        for name in modules_meta:
            _match = pattern.match(name)
            if _match:
                modules.append(_match.group(2))
        return modules

    def fetch_archives_sde(self, cmd_type: str, version: Version) -> List[str]:
        """Returns list of archives for src/doc/examples"""
        assert (
            cmd_type in ("src", "doc", "examples") and self.archive_id.target == "desktop"
        ), "Internal misuse of fetch_archives_sde"
        return self.fetch_archives(version, cmd_type, [])

    def fetch_archives(self, version: Version, arch: str, modules: List[str]) -> List[str]:
        qt_version_str = self._get_qt_version_str(version)
        nonempty = MetadataFactory._has_nonempty_downloads

        def all_modules(element: Element) -> bool:
            _module, _arch = element.find("Name").text.split(".")[-2:]
            return _arch == arch and _module != qt_version_str and nonempty(element)

        def specify_modules(element: Element) -> bool:
            _module, _arch = element.find("Name").text.split(".")[-2:]
            return _arch == arch and _module in modules and nonempty(element)

        def no_modules(element: Element) -> bool:
            name: Optional[str] = element.find("Name").text
            return name and name.endswith(f".{qt_version_str}.{arch}") and nonempty(element)

        predicate = no_modules if not modules else all_modules if "all" in modules else specify_modules
        try:
            mod_metadata = self._fetch_module_metadata(self.archive_id.to_folder(qt_version_str), predicate=predicate)
        except (AttributeError,) as e:
            raise ArchiveListError(f"Downloaded metadata is corrupted. {e}") from e

        # Did we find all requested modules?
        if modules and "all" not in modules:
            requested_set = set(modules)
            actual_set = set([_name.split(".")[-2] for _name in mod_metadata.keys()])
            not_found = sorted(requested_set.difference(actual_set))
            if not_found:
                raise CliInputError(
                    f"The requested modules were not located: {not_found}", suggested_action=suggested_follow_up(self)
                )

        csv_lists = [mod["DownloadableArchives"] for mod in mod_metadata.values()]
        return sorted(set([arc.split("-")[0] for csv in csv_lists for arc in csv.split(", ")]))

    def describe_filters(self) -> str:
        if self.spec is None:
            return str(self.archive_id)
        return "{} with spec {}".format(self.archive_id, self.spec)


def suggested_follow_up(meta: MetadataFactory) -> List[str]:
    """Makes an informed guess at what the user got wrong, in the event of an error."""
    msg = []
    list_cmd = "list-tool" if meta.archive_id.is_tools() else "list-qt"
    base_cmd = "aqt {0} {1.host} {1.target}".format(list_cmd, meta.archive_id)
    versions_msg = f"Please use '{base_cmd}' to show versions of Qt available."
    arches_msg = f"Please use '{base_cmd} --arch <QT_VERSION>' to show architectures available."
    if meta.archive_id.extension:
        msg.append(f"Please use '{base_cmd} --extensions <QT_VERSION>' to list valid extensions.")

    if meta.archive_id.is_tools() and meta.request_type == "tool variant names":
        msg.append(f"Please use '{base_cmd}' to check what tools are available.")
    elif meta.spec is not None:
        msg.append(
            f"Please use '{base_cmd}' to check that versions of {meta.archive_id.category} "
            f"exist within the spec '{meta.spec}'."
        )
    elif meta.request_type in ("architectures", "modules", "extensions"):
        msg.append(f"Please use '{base_cmd}' to show versions of Qt available.")
        if meta.request_type == "modules":
            msg.append(f"Please use '{base_cmd} --arch <QT_VERSION>' to list valid architectures.")
    elif meta.request_type == "archives for modules":
        msg.extend([versions_msg, arches_msg, f"Please use '{base_cmd} --modules <QT_VERSION>' to show modules available."])
    elif meta.request_type == "archives for qt":
        msg.extend([versions_msg, arches_msg])

    return msg


def show_list(meta: MetadataFactory):
    try:
        output = meta.getList()
        if not output:
            raise EmptyMetadata(
                f"No {meta.request_type} available for this request.", suggested_action=suggested_follow_up(meta)
            )
        if isinstance(output, Versions):
            print(format(output))
        elif isinstance(output, ToolData):
            width: int = shutil.get_terminal_size((0, 40)).columns
            if width == 0:  # notty ?
                print(format(output, "{:0t}"))
            elif width < 95:  # narrow terminal
                print(format(output, "{:T}"))
            else:
                print("{0:{1}t}".format(output, width))
        elif meta.archive_id.is_tools():
            print(*output, sep="\n")
        else:
            print(*output, sep=" ")
    except (ArchiveDownloadError, ArchiveConnectionError) as e:
        e.suggested_action = suggested_follow_up(meta)
        raise e from e

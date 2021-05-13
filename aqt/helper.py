#!/usr/bin/env python
#
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

import ast
import configparser
import dataclasses
import json
import logging
import multiprocessing
import os
import re
import sys
import xml.etree.ElementTree as ElementTree
from typing import List, Optional, Dict, Tuple, Iterable, Callable

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from requests import RequestException
from semantic_version import Version, SimpleSpec

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


@dataclasses.dataclass
class ArchiveId:
    category: str  # one of (tools, qt5, qt6)
    host: str  # one of (windows, mac, linux)
    target: str  # one of (desktop, android, ios, winrt)
    extension: Optional[str] = None  # one of ALL_EXTENSIONS

    def is_preview(self) -> bool:
        return "preview" in self.extension if self.extension else False

    def is_qt(self) -> bool:
        return self.category.startswith("qt")

    def is_tools(self) -> bool:
        return self.category == "tools"

    def to_url(
        self, qt_version_no_dots: Optional[str] = None, file: Optional[str] = None
    ) -> str:
        base = "{os}{arch}/{target}/".format(
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
        if not file:
            return base + folder
        return base + folder + file


def _get_meta(url: str):
    return requests.get(url + ".meta4")


def _check_content_type(ct: str) -> bool:
    candidate = ["application/metalink4+xml", "text/plain"]
    return any(ct.startswith(t) for t in candidate)


def altlink(url: str, alt: str, logger=None):
    """Blacklisting redirected(alt) location based on Settings.blacklist configuration.
    When found black url, then try download a url + .meta4 that is a metalink version4
    xml file, parse it and retrieve best alternative url."""
    if logger is None:
        logger = logging.getLogger(__name__)
    blacklist = Settings().blacklist  # type: Optional[List[str]]
    if blacklist is None or not any(alt.startswith(b) for b in blacklist):
        return alt
    try:
        m = _get_meta(url)
    except requests.exceptions.ConnectionError:
        logger.error("Got connection error. Fall back to recovery plan...")
        return alt
    else:
        # Expected response->'application/metalink4+xml; charset=utf-8'
        if not _check_content_type(m.headers["content-type"]):
            logger.error(
                "Unexpected meta4 response;content-type: {}".format(
                    m.headers["content-type"]
                )
            )
            return alt
        try:
            mirror_xml = ElementTree.fromstring(m.text)
            meta_urls = {}
            for f in mirror_xml.iter("{urn:ietf:params:xml:ns:metalink}file"):
                for u in f.iter("{urn:ietf:params:xml:ns:metalink}url"):
                    meta_urls[u.attrib["priority"]] = u.text
            mirrors = [
                meta_urls[i] for i in sorted(meta_urls.keys(), key=lambda x: int(x))
            ]
        except Exception:
            exc_info = sys.exc_info()
            logger.error("Unexpected meta4 file; parse error: {}".format(exc_info[1]))
            return alt
        else:
            # Return first priority item which is not blacklist in mirrors list,
            # if not found then return alt in default
            return next(
                filter(
                    lambda mirror: not any(mirror.startswith(b) for b in blacklist),
                    mirrors,
                ),
                alt,
            )


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
    if any(not ch.isdigit() for ch in qt_ver):
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


def request_http_with_failover(
    base_urls: List[str], rest_of_url: str, timeout=(5, 5)
) -> str:
    """Make an HTTP request, using one or more base urls in case the request fails.
    If all requests fail, then re-raise the requests.exceptions.RequestException
    that was raised by the final HTTP request.
    Any HTTP request that resulted in a status code >= 400 will result in a RequestException.
    """
    for i, base_url in enumerate(base_urls):
        try:
            url = base_url + rest_of_url
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except RequestException as e:
            # Only raise the exception if all urls are exhausted
            if i == len(base_urls) - 1:
                raise e


def xml_to_packages(
    xml_text: str,
    predicate: Callable[[ElementTree.Element], bool],
    keys_to_keep: Iterable[str],
) -> Dict[str, Dict[str, str]]:
    """Converts an XML document to a dict of `PackageUpdate` dicts, indexed by `Name` attribute.
    Only report elements that satisfy `predicate(element)`.
    Only report keys in the list `keys_to_keep`.
    """
    try:
        parsed_xml = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return {}
    packages = {}
    for packageupdate in parsed_xml.iter("PackageUpdate"):
        if predicate and not predicate(packageupdate):
            continue
        name = packageupdate.find("Name").text
        packages[name] = {}
        for key in keys_to_keep:
            packages[name][key] = getattr(packageupdate.find(key), "text", None)
    return packages


def has_empty_downloads(element: ElementTree.Element) -> bool:
    """Returns True if the element has an empty '<DownloadableArchives/>' tag"""
    downloads = element.find("DownloadableArchives")
    return downloads is not None and not downloads.text


def has_nonempty_downloads(element: ElementTree.Element) -> bool:
    """Returns True if the element has an empty '<DownloadableArchives/>' tag"""
    downloads = element.find("DownloadableArchives")
    return downloads is not None and downloads.text


def scrape_html_for_versions_and_tools(
    html_doc: str,
) -> Tuple[Dict[str, Dict[str, List[List[Version]]]], List[str]]:
    """Reads an html file from `https://download.qt.io/online/qtsdkrepository/<os>/<target>/`
    and extracts a list of all the folders reported by that html file.
    Each folder should include an Updates.xml file, but this is not guaranteed.
    This will return a dictionary, where the key is the category (tools, qt5, qt6, etc)
    and the value is a list of folders.
    """

    def table_row_to_folder(tr: Tag) -> str:
        try:
            return tr.find_all("td")[1].a.contents[0].rstrip("/")
        except (AttributeError, IndexError):
            return ""

    def split_components(
        string: str,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        components = string.split("_", maxsplit=2)
        ext = None if len(components) < 3 else components[2]
        ver = None if len(components) < 2 else components[1]
        cat = None if len(components) < 1 else components[0]
        return cat, ver, ext

    soup: BeautifulSoup = BeautifulSoup(html_doc, "html.parser")
    tool_folders: List[str] = []
    expected_extensions = ("qt", *ALL_EXTENSIONS)
    versions: Dict[str, Dict[str, Dict[Tuple[int, int], List[Version]]]] = {
        "qt{}".format(i): {"qt": {}}  # {(6,0): [6.0.0, 6.0.1, ...], (6,1): [6.1.0 ...]}
        for i in range(5, 10)
    }
    for row in soup.body.table.find_all("tr"):
        content: str = table_row_to_folder(row)
        if not content or content == "Parent Directory":
            continue
        category, ver_str, extension = split_components(content)
        if category == "tools":
            tool_folders.append(content)
        elif hasattr(category, "startswith") and category.startswith("qt"):
            is_preview = extension is not None and "preview" in extension
            qt_ver = (
                get_semantic_version(qt_ver=ver_str, is_preview=is_preview)
                if ver_str
                else None
            )
            subsection = str(extension) if extension is not None else "qt"
            if qt_ver is not None and subsection in expected_extensions:
                if subsection not in versions[category]:
                    versions[category][subsection] = {}
                dest: Dict[Tuple[int, int], List[Version]] = versions[category][
                    subsection
                ]
                key = (qt_ver.major, qt_ver.minor)
                if key not in dest.keys():
                    dest[key] = []
                dest[key].append(qt_ver)
    ordered_versions = {}
    for qt_major, qt_major_vals in versions.items():
        ordered_versions[qt_major] = {}
        for category, ver_lists in qt_major_vals.items():
            ordered_versions[qt_major][category] = []
            # Sort ver_lists in ascending order
            for major_minor in sorted(ver_lists.keys()):
                all_for_major_minor = sorted(ver_lists[major_minor])
                ordered_versions[qt_major][category].append(all_for_major_minor)

    return ordered_versions, tool_folders


def filter_folders(
    category: str,
    extension: Optional[str],
    is_latest: bool,
    filter_minor: Optional[int],
    versions: Dict[str, Dict[str, List[List[Version]]]],
    tool_folders: List[str],
) -> str:
    """!
    @param category
    @param extension
    @param is_latest        When true, only print the latest version.
    @param filter_minor     Filter out any versions without this minor version.
    @param versions         Expected to be filtered in ascending order
    @param tool_folders
    @return
    """
    if category == "tools":
        return "\n".join(tool_folders)

    def stringify_ver(ver: Version) -> str:
        if ver.prerelease:
            assert ver.patch == 0 and ver.prerelease == ('preview',)
            return "{}.{}-preview".format(ver.major, ver.minor)
        return str(ver)

    subtype = "qt" if extension is None else extension
    if (
        category in versions.keys()
        and subtype in versions[category].keys()
        and versions[category][subtype]
    ):
        versions_needed = versions[category][subtype]
        if filter_minor is not None:
            versions_needed = [
                row for row in versions_needed if row[0].minor == filter_minor
            ]

        # PRE: data was returned in ascending order
        latest_version = versions_needed[-1][-1]
        if is_latest:
            return stringify_ver(latest_version)
        return "\n".join(
            [
                " ".join([stringify_ver(ver) for ver in major_minor])
                for major_minor in versions_needed
            ]
        )
    return ""


def get_packages_for_version(
    version: str,
    archive_id: ArchiveId,
    http_fetcher: Callable[[str], str],
) -> List[str]:
    match = re.match(r"((\d+)\.\d+(\.\d+)?)(-preview)?$", version)
    qt_ver_str = match.group(1).replace(".", "")
    qt_major = int(match.group(2))
    rest_of_url = archive_id.to_url(qt_version_no_dots=qt_ver_str, file="Updates.xml")
    xml = http_fetcher(rest_of_url)  # raises RequestException

    # We want the names of packages, regardless of architecture/compiler:
    packages = xml_to_packages(
        xml,
        predicate=has_empty_downloads
        if archive_id.extension != "src_doc_examples"
        else has_nonempty_downloads,
        keys_to_keep=(),  # Just want names
    )
    # Example: re.compile(r"^(preview\.)?qt\.(qt5\.)?590\.")
    pattern = re.compile(
        r"^(preview\.)?qt\.(qt" + str(qt_major) + r"\.)?" + qt_ver_str + r"\.(.+)$"
    )

    def to_package_name(name: str) -> Optional[str]:
        _match = pattern.match(name)
        return _match.group(3) if _match else None

    return sorted(filter(None, set(to_package_name(name) for name in packages.keys())))


def list_packages_for_version(
    version: str,
    archive_id: ArchiveId,
    http_fetcher: Callable[[str], str],
) -> int:
    logger = logging.getLogger("aqt")
    try:
        package_names = get_packages_for_version(version, archive_id, http_fetcher)
        if len(package_names) == 0:
            logger.error("No packages available")
            return 1
        print(" ".join(package_names))
        return 0
    except requests.exceptions.RequestException as e:
        logger.error("HTTP request error: {}".format(e))
        return 1


class Settings(object):
    """Class to hold configuration and settings.
    Actual values are stored in 'settings.ini' file.
    It also holds a combinations database.
    """

    # this class is Borg/Singleton
    _shared_state = {
        "_config": None,
        "_combinations": None,
        "_lock": multiprocessing.Lock(),
    }

    def __init__(self, config=None):
        self.__dict__ = self._shared_state
        if self._config is None:
            with self._lock:
                if self._config is None:
                    if config is None:
                        self.inifile = os.path.join(
                            os.path.dirname(__file__), "settings.ini"
                        )
                    else:
                        self.inifile = config
                    self._config = self.configParse(self.inifile)
                    with open(
                        os.path.join(os.path.dirname(__file__), "combinations.json"),
                        "r",
                    ) as j:
                        self._combinations = json.load(j)[0]

    def configParse(self, file_path):
        if not os.path.exists(file_path):
            raise IOError(file_path)
        config = configparser.ConfigParser()
        config.read(file_path)
        return config

    @property
    def qt_combinations(self):
        return self._combinations["qt"]

    @property
    def tools_combinations(self):
        return self._combinations["tools"]

    @property
    def available_versions(self):
        return self._combinations["versions"]

    def available_modules(self, qt_version):
        """Known module names

        :returns: dictionary of qt_version and module names
        :rtype: List[str]
        """
        modules = self._combinations["modules"]
        versions = qt_version.split(".")
        version = "{}.{}".format(versions[0], versions[1])
        result = None
        for record in modules:
            if record["qt_version"] == version:
                result = record["modules"]
        return result

    @property
    def concurrency(self):
        """concurrency configuration.

        :return: concurrency
        :rtype: int
        """
        return self._config.getint("aqt", "concurrency")

    @property
    def blacklist(self):
        """list of sites in a blacklist

        :returns: list of site URLs(scheme and host part)
        :rtype: List[str]
        """
        return ast.literal_eval(self._config.get("mirrors", "blacklist"))

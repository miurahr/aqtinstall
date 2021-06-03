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

import configparser
import dataclasses
import hashlib
import itertools
import json
import logging
import multiprocessing
import os
import random
import re
import sys
import xml.etree.ElementTree as ElementTree
from typing import Callable, Dict, Generator, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from semantic_version import Version

from aqt.exceptions import ArchiveConnectionError, ArchiveDownloadError

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
    extension: str = ""  # one of ALL_EXTENSIONS

    def is_preview(self) -> bool:
        return "preview" in self.extension if self.extension else False

    def is_qt(self) -> bool:
        return self.category.startswith("qt")

    def is_tools(self) -> bool:
        return self.category == "tools"

    def is_no_arch(self) -> bool:
        """Returns True if there should be no arch attached to the module names"""
        return self.extension in ("src_doc_examples",)

    def is_major_ver_mismatch(self, qt_version: str) -> bool:
        """Returns True if the version string specifies a version different from the specified category"""
        return (
            self.is_qt()
            and qt_version
            and len(qt_version) > 0
            and qt_version[0] != self.category[-1]
        )

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


class Versions:
    def __init__(self, it_of_it: Iterable[Tuple[int, Iterable[Version]]]):
        self.versions: List[List[Version]] = [
            list(versions_iterator) for _, versions_iterator in it_of_it
        ]

    def __str__(self):
        return "\n".join(
            " ".join(Versions.stringify_ver(version) for version in minor_list)
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


@dataclasses.dataclass
class Tools:
    tools: List[str]

    def __str__(self):
        return "\n".join(self.tools)

    def __bool__(self):
        return len(self.tools) > 0


@dataclasses.dataclass
class Extensions:
    exts: List[str]

    def __str__(self):
        return " ".join(self.exts)

    def __bool__(self):
        return len(self.exts) > 0


def _get_meta(url: str):
    return requests.get(url + ".meta4")


def _check_content_type(ct: str) -> bool:
    candidate = ["application/metalink4+xml", "text/plain"]
    return any(ct.startswith(t) for t in candidate)


def getUrl(url: str, timeout, logger) -> str:
    with requests.Session() as session:
        adapter = requests.adapters.HTTPAdapter()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        try:
            r = requests.get(url, allow_redirects=False, timeout=timeout)
            if 300 < r.status_code < 309:
                logger.info(
                    "Asked to redirect({}) to: {}".format(
                        r.status_code, r.headers["Location"]
                    )
                )
                newurl = altlink(r.url, r.headers["Location"], logger=logger)
                logger.info("Redirected: {}".format(urlparse(newurl).hostname))
                r = session.get(newurl, stream=True, timeout=timeout)
        except (
            ConnectionResetError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ):
            raise ArchiveConnectionError()
        else:
            if r.status_code != 200:
                logger.error(
                    "Download error when access to {}\n"
                    "Server response code: {}, reason: {}".format(
                        url, r.status_code, r.reason
                    )
                )
                raise ArchiveDownloadError("Download error!")
        result = r.text
    return result


def downloadBinaryFile(url: str, out: str, hash_algo: str, exp: str, timeout, logger):
    with requests.Session() as session:
        adapter = requests.adapters.HTTPAdapter()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        try:
            r = session.get(url, allow_redirects=False, stream=True, timeout=timeout)
            if 300 < r.status_code < 309:
                logger.info(
                    "Asked to redirect({}) to: {}".format(
                        r.status_code, r.headers["Location"]
                    )
                )
                newurl = altlink(r.url, r.headers["Location"], logger=logger)
                logger.info("Redirected: {}".format(urlparse(newurl).hostname))
                r = session.get(newurl, stream=True, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection error: %s" % e.args)
            raise e
        except requests.exceptions.Timeout as e:
            logger.error("Connection timeout: %s" % e.args)
            raise e
        else:
            hash = hashlib.new(hash_algo)
            try:
                with open(out, "wb") as fd:
                    for chunk in r.iter_content(chunk_size=8196):
                        fd.write(chunk)
                        hash.update(chunk)
                    fd.flush()
                if exp is not None:
                    if hash.digest() != exp:
                        raise ArchiveDownloadError(
                            "Download file is corrupted! Detect checksum error.\nExpected {}, Actual {}".format(
                                exp, hash.digest()
                            )
                        )
            except Exception as e:
                exc = sys.exc_info()
                logger.error("Download error: %s" % exc[1])
                raise e


def altlink(url: str, alt: str, logger=None):
    """Blacklisting redirected(alt) location based on Settings.blacklist configuration.
    When found black url, then try download a url + .meta4 that is a metalink version4
    xml file, parse it and retrieve best alternative url."""
    if logger is None:
        logger = logging.getLogger(__name__)
    blacklist = Settings().blacklist  # type: Optional[List[str]]
    if not any(alt.startswith(b) for b in blacklist):
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


class MyConfigParser(configparser.ConfigParser):
    def getlist(self, section: str, option: str, fallback=[]) -> List[str]:
        value = self.get(section, option)
        try:
            result = list(filter(None, (x.strip() for x in value.splitlines())))
        except Exception:
            result = fallback
        return result

    def getlistint(self, section: str, option: str, fallback=[]):
        try:
            result = [int(x) for x in self.getlist(section, option)]
        except Exception:
            result = fallback
        return result


def to_version(qt_ver: Optional[str]) -> Optional[Version]:
    """Converts a Qt version string with dots (5.X.Y, etc) into a semantic version.
    If the version ends in `-preview`, the version is treated as a preview release.
    If the patch value is missing, patch is assumed to be zero.
    If the version cannot be converted to a Version, a ValueError is raised.
    """
    if not qt_ver:
        return None
    match = re.match(r"^(\d+)\.(\d+)(\.(\d+)|-preview)?$", qt_ver)
    if not match:
        raise ValueError("Invalid version string '{}'".format(qt_ver))
    major, minor, end, patch = match.groups()
    is_preview = end == "-preview"
    return Version(
        major=int(major),
        minor=int(minor),
        patch=int(patch) if patch else 0,
        prerelease=("preview",) if is_preview else None,
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


def request_http_with_failover(
    base_urls: List[str], rest_of_url: str, timeout: Tuple[float, float]
) -> str:
    """Make an HTTP request, using one or more base urls in case the request fails.
    If all requests fail, then re-raise the requests.exceptions.RequestException
    that was raised by the final HTTP request.
    Any HTTP request that resulted in a status code >= 400 will result in a RequestException.
    """
    for i, base_url in enumerate(base_urls):
        try:
            url = base_url + "/" + rest_of_url
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except requests.exceptions.RequestException as e:
            # Only raise the exception if all urls are exhausted
            if i == len(base_urls) - 1:
                raise e


def default_http_fetcher(rest_of_url: str) -> str:
    settings = Settings()  # Borg/Singleton ensures we get the right settings
    return request_http_with_failover(
        base_urls=[settings.baseurl, random.choice(settings.fallbacks)],
        rest_of_url=rest_of_url,
        timeout=(settings.connection_timeout, settings.response_timeout),
    )


def xml_to_modules(
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


def _iterate_folders(
    html_doc: str, filter_category: str = ""
) -> Generator[str, None, None]:
    def table_row_to_folder(tr: Tag) -> str:
        try:
            return tr.find_all("td")[1].a.contents[0].rstrip("/")
        except (AttributeError, IndexError):
            return ""

    soup: BeautifulSoup = BeautifulSoup(html_doc, "html.parser")
    for row in soup.body.table.find_all("tr"):
        content: str = table_row_to_folder(row)
        if not content or content == "Parent Directory":
            continue
        if content.startswith(filter_category):
            yield content


def folder_to_version_extension(folder: str) -> Tuple[Optional[Version], str]:
    components = folder.split("_", maxsplit=2)
    ext = "" if len(components) < 3 else components[2]
    ver = "" if len(components) < 2 else components[1]
    return get_semantic_version(qt_ver=ver, is_preview="preview" in ext), ext


def get_extensions_for_version(
    desired_version: Version, archive_id: ArchiveId, html_doc: str
) -> Extensions:
    versions_extensions = map(
        folder_to_version_extension, _iterate_folders(html_doc, archive_id.category)
    )
    filtered = filter(
        lambda ver_ext: ver_ext[0] == desired_version and ver_ext[1],
        versions_extensions,
    )
    return Extensions(exts=list(map(lambda ver_ext: ver_ext[1], filtered)))


def get_versions_for_minor(
    minor_ver: Optional[int], archive_id: ArchiveId, html_doc: str
) -> Versions:
    def filter_by(ver_ext: Tuple[Optional[Version], str]) -> bool:
        version, extension = ver_ext
        return (
            version
            and (minor_ver is None or minor_ver == version.minor)
            and (archive_id.extension == extension)
        )

    def get_version(ver_ext: Tuple[Version, str]):
        return ver_ext[0]

    all_versions_extensions = map(
        folder_to_version_extension, _iterate_folders(html_doc, archive_id.category)
    )
    versions = sorted(
        filter(None, map(get_version, filter(filter_by, all_versions_extensions)))
    )
    iterables = itertools.groupby(versions, lambda version: version.minor)
    return Versions(iterables)


def get_tools(html_doc: str) -> Tools:
    return Tools(tools=list(_iterate_folders(html_doc, "tools")))


def get_modules_architectures_for_version(
    version: Version,
    archive_id: ArchiveId,
    http_fetcher: Callable[[str], str],
) -> Tuple[List[str], List[str]]:
    """Returns [list of modules, list of architectures]"""
    patch = "" if version.prerelease or archive_id.is_preview() else str(version.patch)
    qt_ver_str = "{}{}{}".format(version.major, version.minor, patch)
    # Example: re.compile(r"^(preview\.)?qt\.(qt5\.)?590\.(.+)$")
    pattern = re.compile(
        r"^(preview\.)?qt\.(qt" + str(version.major) + r"\.)?" + qt_ver_str + r"\.(.+)$"
    )

    def to_module_arch(name: str) -> Tuple[Optional[str], Optional[str]]:
        _match = pattern.match(name)
        if not _match:
            return None, None
        module_with_arch = _match.group(3)
        if archive_id.is_no_arch() or "." not in module_with_arch:
            return module_with_arch, None
        module, arch = module_with_arch.rsplit(".", 1)
        return module, arch

    rest_of_url = archive_id.to_url(qt_version_no_dots=qt_ver_str, file="Updates.xml")
    xml = http_fetcher(rest_of_url)  # raises RequestException

    # We want the names of modules, regardless of architecture:
    modules = xml_to_modules(
        xml,
        predicate=has_nonempty_downloads,
        keys_to_keep=(),  # Just want names
    )

    def naive_modules_arches(names: Iterable[str]) -> Tuple[List[str], List[str]]:
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
        return sorted(_modules), sorted(arches)

    return naive_modules_arches(modules.keys())


def list_modules_for_version(
    version: Version,
    archive_id: ArchiveId,
    http_fetcher: Callable[[str], str],
) -> int:
    return _list_modules_architectures_for_version(
        version,
        archive_id,
        http_fetcher,
        lambda mods, arches: mods,
        "No modules available",
    )


def list_architectures_for_version(
    version: Version,
    archive_id: ArchiveId,
    http_fetcher: Callable[[str], str],
) -> int:
    return _list_modules_architectures_for_version(
        version,
        archive_id,
        http_fetcher,
        lambda mods, arches: arches,
        "No architectures available",
    )


def _list_modules_architectures_for_version(
    version: Version,
    archive_id: ArchiveId,
    http_fetcher: Callable[[str], str],
    mux: Callable[[any], List[str]],
    error_msg_if_empty: str,
) -> int:
    logger = logging.getLogger("aqt")
    try:
        result = mux(
            *get_modules_architectures_for_version(version, archive_id, http_fetcher)
        )
        if len(result) == 0:
            logger.error(error_msg_if_empty)
            return 1
        print(" ".join(result))
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
        "config": None,
        "_combinations": None,
        "_lock": multiprocessing.Lock(),
    }

    def __init__(self, file=None):
        self.__dict__ = self._shared_state
        if self.config is None:
            with self._lock:
                if self.config is None:
                    self.config = MyConfigParser()
                    # load default config file
                    with open(
                        os.path.join(os.path.dirname(__file__), "settings.ini"), "r"
                    ) as f:
                        self.config.read_file(f)
                    # load custom file
                    if file is not None:
                        if isinstance(file, str):
                            result = self.config.read(file)
                            if len(result) == 0:
                                raise IOError(
                                    "Fails to load specified config file {}".format(
                                        file
                                    )
                                )
                        else:
                            # passed through command line argparse.FileType("r")
                            self.config.read_file(file)
                            file.close()
                    # load combinations
                    with open(
                        os.path.join(os.path.dirname(__file__), "combinations.json"),
                        "r",
                    ) as j:
                        self._combinations = json.load(j)[0]

    @property
    def qt_combinations(self):
        return self._combinations["qt"]

    @property
    def tools_combinations(self):
        return self._combinations["tools"]

    @property
    def available_versions(self):
        return self._combinations["versions"]

    @property
    def available_offline_installer_version(self):
        res = self._combinations["new_archive"]
        res.extend(self._combinations["versions"])
        return res

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
        return self.config.getint("aqt", "concurrency", fallback=4)

    @property
    def blacklist(self):
        """list of sites in a blacklist

        :returns: list of site URLs(scheme and host part)
        :rtype: List[str]
        """
        return self.config.getlist("mirrors", "blacklist", fallback=[])

    @property
    def baseurl(self):
        return self.config.get("aqt", "baseurl", fallback="https://download.qt.io")

    @property
    def connection_timeout(self):
        return self.config.getfloat("aqt", "connection_timeout", fallback=3.5)

    @property
    def response_timeout(self):
        return self.config.getfloat("aqt", "response_timeout", fallback=3.5)

    @property
    def fallbacks(self):
        return self.config.getlist("mirrors", "fallbacks", fallback=[])

    @property
    def zipcmd(self):
        return self.config.get("aqt", "7zcmd", fallback="7z")

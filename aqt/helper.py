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
import binascii
import hashlib
import logging.config
import os
import posixpath
import secrets
import shutil
import subprocess
import sys
import uuid
from configparser import ConfigParser
from logging import Handler, getLogger
from logging.handlers import QueueListener
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Generator, List, Optional, TextIO, Tuple, Union
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import humanize
import requests
import requests.adapters
from defusedxml import ElementTree

from aqt.exceptions import (
    ArchiveChecksumError,
    ArchiveConnectionError,
    ArchiveDownloadError,
    ArchiveListError,
    ChecksumDownloadFailure,
)


def get_os_name() -> str:
    system = sys.platform.lower()
    if system == "darwin":
        return "mac"
    if system == "linux":
        return "linux"
    if system in ("windows", "win32"):  # Accept both windows and win32
        return "windows"
    raise ValueError(f"Unsupported operating system: {system}")


def get_qt_local_folder_path() -> Path:
    os_name = get_os_name()
    if os_name == "windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "Qt"
    if os_name == "mac":
        return Path.home() / "Library" / "Application Support" / "Qt"
    return Path.home() / ".local" / "share" / "Qt"


def get_qt_account_path() -> Path:
    return get_qt_local_folder_path() / "qtaccount.ini"


def get_qt_installer_name() -> str:
    installer_dict = {
        "windows": "qt-unified-windows-x64-online.exe",
        "mac": "qt-unified-mac-x64-online.dmg",
        "linux": "qt-unified-linux-x64-online.run",
    }
    return installer_dict[get_os_name()]


def get_qt_installer_path() -> Path:
    return get_qt_local_folder_path() / get_qt_installer_name()


def get_default_local_cache_path() -> Path:
    os_name = get_os_name()
    if os_name == "windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "aqt" / "cache"
    if os_name == "mac":
        return Path.home() / "Library" / "Application Support" / "aqt" / "cache"
    return Path.home() / ".local" / "share" / "aqt" / "cache"


def get_default_local_temp_path() -> Path:
    os_name = get_os_name()
    if os_name == "windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "aqt" / "tmp"
    if os_name == "mac":
        return Path.home() / "Library" / "Application Support" / "aqt" / "tmp"
    return Path.home() / ".local" / "share" / "aqt" / "tmp"


def _get_meta(url: str) -> requests.Response:
    return requests.get(url + ".meta4")


def _check_content_type(ct: str) -> bool:
    candidate = ["application/metalink4+xml", "text/plain"]
    return any(ct.startswith(t) for t in candidate)


def getUrl(url: str, timeout: Tuple[float, float], expected_hash: Optional[bytes] = None) -> str:
    """
    Gets a file from `url` via HTTP GET.

    No caller should call this function without providing an expected_hash, unless
    the caller is `get_hash`, which cannot know what the expected hash should be.
    """
    logger = getLogger("aqt.helper")
    with requests.sessions.Session() as session:
        retries = requests.adapters.Retry(
            total=Settings.max_retries_on_connection_error, backoff_factor=Settings.backoff_factor
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        try:
            r = session.get(url, allow_redirects=False, timeout=timeout)
            num_redirects = 0
            while 300 < r.status_code < 309 and num_redirects < 10:
                num_redirects += 1
                logger.debug("Asked to redirect({}) to: {}".format(r.status_code, r.headers["Location"]))
                newurl = altlink(r.url, r.headers["Location"])
                logger.info("Redirected: {}".format(urlparse(newurl).hostname))
                r = session.get(newurl, stream=True, timeout=timeout)
        except (
            ConnectionResetError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as e:
            raise ArchiveConnectionError(f"Failure to connect to {url}: {type(e).__name__}") from e
        else:
            if r.status_code != 200:
                msg = f"Failed to retrieve file at {url}\nServer response code: {r.status_code}, reason: {r.reason}"
                raise ArchiveDownloadError(msg)
        result: str = r.text
        filename = url.split("/")[-1]
        _kwargs = {"usedforsecurity": False} if sys.version_info >= (3, 9) else {}
        if Settings.hash_algorithm == "sha256":
            actual_hash = hashlib.sha256(bytes(result, "utf-8"), **_kwargs).digest()
        elif Settings.hash_algorithm == "sha1":
            actual_hash = hashlib.sha1(bytes(result, "utf-8"), **_kwargs).digest()
        elif Settings.hash_algorithm == "md5":
            actual_hash = hashlib.md5(bytes(result, "utf-8"), **_kwargs).digest()
        else:
            raise ArchiveChecksumError(f"Unknown hash algorithm: {Settings.hash_algorithm}.\nPlease check settings.ini")
        if expected_hash is not None and expected_hash != actual_hash:
            raise ArchiveChecksumError(
                f"Downloaded file {filename} is corrupted! Detect checksum error.\n"
                f"Expect {expected_hash.hex()}: {url}\n"
                f"Actual {actual_hash.hex()}: {filename}"
            )
    return result


def downloadBinaryFile(url: str, out: Path, hash_algo: str, exp: Optional[bytes], timeout: Tuple[float, float]) -> None:
    logger = getLogger("aqt.helper")
    filename = Path(url).name
    with requests.sessions.Session() as session:
        retries = requests.adapters.Retry(
            total=Settings.max_retries_on_connection_error, backoff_factor=Settings.backoff_factor
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        try:
            r = session.get(url, allow_redirects=False, stream=True, timeout=timeout)
            if 300 < r.status_code < 309:
                logger.debug("Asked to redirect({}) to: {}".format(r.status_code, r.headers["Location"]))
                newurl = altlink(r.url, r.headers["Location"])
                logger.info("Redirected: {}".format(urlparse(newurl).hostname))
                r = session.get(newurl, stream=True, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            raise ArchiveConnectionError(f"Connection error: {e.args}") from e
        except requests.exceptions.Timeout as e:
            raise ArchiveConnectionError(f"Connection timeout: {e.args}") from e
        else:
            if sys.version_info >= (3, 9):
                hash = hashlib.new(hash_algo, usedforsecurity=False)
            else:
                hash = hashlib.new(hash_algo)
            try:
                with open(out, "wb") as fd:
                    for chunk in r.iter_content(chunk_size=8196):
                        fd.write(chunk)
                        hash.update(chunk)
                    fd.flush()
            except requests.exceptions.ReadTimeout as e:
                raise ArchiveConnectionError(f"Read timeout: {e.args}") from e
            except Exception as e:
                raise ArchiveDownloadError(f"Download of {filename} has error: {e}") from e
            if exp is not None and hash.digest() != exp:
                raise ArchiveChecksumError(
                    f"Downloaded file {filename} is corrupted! Detect checksum error.\n"
                    f"Expect {exp.hex()}: {url}\n"
                    f"Actual {hash.digest().hex()}: {out.name}"
                )


def retry_on_errors(action: Callable[[], Any], acceptable_errors: Tuple, num_retries: int, name: str) -> Any:
    logger = getLogger("aqt.helper")
    for i in range(num_retries):
        try:
            retry_msg = f": attempt #{1 + i}" if i > 0 else ""
            logger.info(f"{name}{retry_msg}...")
            ret = action()
            if i > 0:
                logger.info(f"Success on attempt #{1 + i}: {name}")
            return ret
        except acceptable_errors as e:
            if i < num_retries - 1:
                continue  # just try again
            raise e from e


def retry_on_bad_connection(function: Callable[[str], Any], base_url: str) -> Any:
    logger = getLogger("aqt.helper")
    fallback_url = secrets.choice(Settings.fallbacks)
    try:
        return function(base_url)
    except ArchiveConnectionError:
        logger.warning(f"Connection to '{base_url}' failed. Retrying with fallback '{fallback_url}'.")
        return function(fallback_url)


def iter_list_reps(_list: List, num_reps: int) -> Generator:
    list_index = 0
    for i in range(num_reps):
        yield _list[list_index]
        list_index += 1
        if list_index >= len(_list):
            list_index = 0


def get_hash(archive_path: str, algorithm: str, timeout: Tuple[float, float]) -> bytes:
    """
    Downloads a checksum and unhexlifies it to a `bytes` object, guaranteed to be the right length.
    Raises ChecksumDownloadFailure if the download failed, or if the checksum was un unexpected length.

    :param archive_path: The path to the file that we want to check, not the path to the checksum.
    :param algorithm:    sha256 is the only safe value to use here.
    :param timeout:      The timeout used by getUrl.
    :return:             A checksum in `bytes`
    """
    logger = getLogger("aqt.helper")
    hash_lengths = {"sha256": 64, "sha1": 40, "md5": 32}
    for base_url in iter_list_reps(Settings.trusted_mirrors, Settings.max_retries_to_retrieve_hash):
        url = posixpath.join(base_url, f"{archive_path}.{algorithm}")
        logger.debug(f"Attempt to download checksum at {url}")
        try:
            r = getUrl(url, timeout)
            # sha256 & md5 files are: "some_hash archive_filename"
            _hash = r.split(" ")[0]
            if len(_hash) == hash_lengths[algorithm]:
                return binascii.unhexlify(_hash)
        except (ArchiveConnectionError, ArchiveDownloadError, binascii.Incomplete, binascii.Error):
            pass
    filename = archive_path.split("/")[-1]
    raise ChecksumDownloadFailure(
        f"Failed to download checksum for the file '{filename}' from mirrors '{Settings.trusted_mirrors}"
    )


def altlink(url: str, alt: str) -> str:
    """
    Blacklisting redirected(alt) location based on Settings. Blacklist configuration.
    When found black url, then try download an url + .meta4 that is a metalink version4
    xml file, parse it and retrieve the best alternative url.
    """
    logger = getLogger("aqt.helper")
    if not any(alt.startswith(b) for b in Settings.blacklist):
        return alt
    try:
        m = _get_meta(url)
    except requests.exceptions.ConnectionError:
        logger.error("Got connection error. Fall back to recovery plan...")
        return alt
    else:
        # Expected response->'application/metalink4+xml; charset=utf-8'
        if not _check_content_type(m.headers["content-type"]):
            logger.error("Unexpected meta4 response;content-type: {}".format(m.headers["content-type"]))
            return alt
        try:
            mirror_xml = ElementTree.fromstring(m.text)
            meta_urls: Dict[str, str] = {}
            for f in mirror_xml.iter("{urn:ietf:params:xml:ns:metalink}file"):
                for u in f.iter("{urn:ietf:params:xml:ns:metalink}url"):
                    meta_urls[u.attrib["priority"]] = u.text
            mirrors = [meta_urls[i] for i in sorted(meta_urls.keys(), key=lambda x: int(x))]
        except Exception:
            exc_info = sys.exc_info()
            logger.error("Unexpected meta4 file; parse error: {}".format(exc_info[1]))
            return alt
        else:
            # Return first priority item which is not blacklist in mirrors list,
            # if not found then return alt in default
            try:
                return next(mirror for mirror in mirrors if not any(mirror.startswith(b) for b in Settings.blacklist))
            except StopIteration:
                return alt


class MyQueueListener(QueueListener):
    def __init__(self, queue) -> None:
        handlers: List[Handler] = []
        super().__init__(queue, *handlers)

    def handle(self, record) -> None:
        """
        Handle a record from subprocess.
        Override logger name then handle at proper logger.
        """
        record = self.prepare(record)
        logger = getLogger("aqt.installer")
        record.name = "aqt.installer"
        logger.handle(record)


def ssplit(data: str) -> Generator[str, None, None]:
    for element in data.split(","):
        yield element.strip()


def xml_to_modules(
    xml_text: str,
    predicate: Callable[[Element], bool],
) -> Dict[str, Dict[str, str]]:
    """Converts an XML document to a dict of `PackageUpdate` dicts, indexed by `Name` attribute.
    Only report elements that satisfy `predicate(element)`.
    Reports all keys available in the PackageUpdate tag as strings.

    :param xml_text: The entire contents of an xml file
    :param predicate: A function that decides which elements to keep or discard
    """
    try:
        parsed_xml = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as perror:
        raise ArchiveListError(f"Downloaded metadata is corrupted. {perror}") from perror
    packages: Dict[str, Dict[str, str]] = {}
    for packageupdate in parsed_xml.iter("PackageUpdate"):
        if not predicate(packageupdate):
            continue
        name = packageupdate.find("Name").text
        packages[name] = {}
        for child in packageupdate:
            if child.tag == "UpdateFile":
                for attr in "CompressedSize", "UncompressedSize":
                    if attr not in child.attrib:
                        continue
                    packages[name][attr] = humanize.naturalsize(child.attrib[attr], gnu=True)
            else:
                packages[name][child.tag] = child.text
    return packages


class MyConfigParser(ConfigParser):
    def getlist(self, section: str, option: str, fallback: List[str] = []) -> List[str]:
        value = self.get(section, option, fallback=None)
        if value is None:
            return fallback
        try:
            result = list(filter(None, (x.strip() for x in value.splitlines())))
        except Exception:
            result = fallback
        return result

    def getlistint(self, section: str, option: str, fallback: List[int] = []) -> List[int]:
        try:
            result = [int(x) for x in self.getlist(section, option)]
        except Exception:
            result = fallback
        return result


class SettingsClass:
    """
    Class to hold configuration and settings.
    Actual values are stored in 'settings.ini' file.
    """

    # this class is Borg
    _shared_state: Dict[str, Any] = {
        "config": None,
        "configfile": None,
        "loggingconf": None,
        "_lock": Lock(),
    }

    def __init__(self) -> None:
        self.config: Optional[ConfigParser]
        self._lock: Lock
        self._initialize()

    def __new__(cls, *p, **k):
        self = object.__new__(cls, *p, **k)
        self.__dict__ = cls._shared_state
        return self

    def _initialize(self) -> None:
        """Initialize configuration if not already initialized."""
        if self.config is None:
            with self._lock:
                if self.config is None:
                    self.config = MyConfigParser()
                    self.configfile = os.path.join(os.path.dirname(__file__), "settings.ini")
                    self.loggingconf = os.path.join(os.path.dirname(__file__), "logging.ini")
                    self.config.read(self.configfile)

                    logging.info(f"Cache folder: {self.qt_installer_cache_path}")
                    logging.info(f"Temp folder: {self.qt_installer_temp_path}")
                    if Path(self.qt_installer_temp_path).exists():
                        shutil.rmtree(self.qt_installer_temp_path)

    def _get_config(self) -> ConfigParser:
        """Safe getter for config that ensures it's initialized."""
        self._initialize()
        assert self.config is not None
        return self.config

    def load_settings(self, file: Optional[Union[str, TextIO]] = None) -> None:
        if self.config is None:
            return

        if file is not None:
            if isinstance(file, str):
                result = self.config.read(file)
                if len(result) == 0:
                    raise IOError("Fails to load specified config file {}".format(file))
                self.configfile = file
            else:
                # passed through command line argparse.FileType("r")
                self.config.read_file(file)
                self.configfile = file.name
                file.close()
        else:
            with open(self.configfile, "r") as f:
                self.config.read_file(f)

    @property
    def qt_installer_cache_path(self) -> str:
        """Path for Qt installer cache."""
        config = self._get_config()
        # If no cache_path or blank, return default without modifying config
        if not config.has_option("qtofficial", "cache_path") or config.get("qtofficial", "cache_path").strip() == "":
            return str(get_default_local_cache_path())
        return config.get("qtofficial", "cache_path")

    @property
    def qt_installer_temp_path(self) -> str:
        """Path for Qt installer cache."""
        config = self._get_config()
        # If no cache_path or blank, return default without modifying config
        if not config.has_option("qtofficial", "temp_path") or config.get("qtofficial", "temp_path").strip() == "":
            return str(get_default_local_temp_path())
        return config.get("qtofficial", "temp_path")

    @property
    def archive_download_location(self):
        return self.config.get("aqt", "archive_download_location", fallback=".")

    @property
    def always_keep_archives(self):
        return self.config.getboolean("aqt", "always_keep_archives", fallback=False)

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
        return self.config.getfloat("requests", "connection_timeout", fallback=3.5)

    @property
    def response_timeout(self):
        return self.config.getfloat("requests", "response_timeout", fallback=10)

    @property
    def max_retries(self):
        """Deprecated: please use `max_retries_on_connection_error` and `max_retries_on_checksum_error` instead!"""
        return self.config.getfloat("requests", "max_retries", fallback=5)

    @property
    def max_retries_on_connection_error(self):
        return self.config.getfloat("requests", "max_retries_on_connection_error", fallback=self.max_retries)

    @property
    def max_retries_on_checksum_error(self):
        return self.config.getint("requests", "max_retries_on_checksum_error", fallback=int(self.max_retries))

    @property
    def max_retries_to_retrieve_hash(self):
        return self.config.getint("requests", "max_retries_to_retrieve_hash", fallback=int(self.max_retries))

    @property
    def hash_algorithm(self):
        return self.config.get("requests", "hash_algorithm", fallback="sha256")

    @property
    def ignore_hash(self):
        return self.config.getboolean("requests", "INSECURE_NOT_FOR_PRODUCTION_ignore_hash", fallback=False)

    @property
    def backoff_factor(self):
        return self.config.getfloat("requests", "retry_backoff", fallback=0.1)

    @property
    def trusted_mirrors(self):
        return self.config.getlist("mirrors", "trusted_mirrors", fallback=[self.baseurl])

    @property
    def fallbacks(self):
        return self.config.getlist("mirrors", "fallbacks", fallback=[])

    @property
    def zipcmd(self):
        return self.config.get("aqt", "7zcmd", fallback="7z")

    @property
    def kde_patches(self):
        return self.config.getlist("kde_patches", "patches", fallback=[])

    @property
    def print_stacktrace_on_error(self):
        return self.config.getboolean("aqt", "print_stacktrace_on_error", fallback=False)

    @property
    def min_module_size(self):
        """
        Some modules in the Qt repository contain only empty directories.
        We have found that these modules are no more than 40 bytes after decompression.
        This setting is used to filter out these empty modules in `list-*` output.
        """
        return self.config.getint("aqt", "min_module_size", fallback=41)

    # Qt Commercial Installer properties
    @property
    def qt_installer_timeout(self) -> int:
        """Timeout for Qt commercial installer operations in seconds."""
        return self._get_config().getint("qtofficial", "installer_timeout", fallback=3600)

    @property
    def qt_installer_operationdoesnotexisterror(self) -> str:
        """Handle OperationDoesNotExistError in Qt installer."""
        return self._get_config().get("qtofficial", "operation_does_not_exist_error", fallback="Ignore")

    @property
    def qt_installer_overwritetargetdirectory(self) -> str:
        """Handle overwriting target directory in Qt installer."""
        return self._get_config().get("qtofficial", "overwrite_target_directory", fallback="No")

    @property
    def qt_installer_stopprocessesforupdates(self) -> str:
        """Handle stopping processes for updates in Qt installer."""
        return self._get_config().get("qtofficial", "stop_processes_for_updates", fallback="Cancel")

    @property
    def qt_installer_installationerrorwithcancel(self) -> str:
        """Handle installation errors with cancel option in Qt installer."""
        return self._get_config().get("qtofficial", "installation_error_with_cancel", fallback="Cancel")

    @property
    def qt_installer_installationerrorwithignore(self) -> str:
        """Handle installation errors with ignore option in Qt installer."""
        return self._get_config().get("qtofficial", "installation_error_with_ignore", fallback="Ignore")

    @property
    def qt_installer_associatecommonfiletypes(self) -> str:
        """Handle file type associations in Qt installer."""
        return self._get_config().get("qtofficial", "associate_common_filetypes", fallback="Yes")

    @property
    def qt_installer_telemetry(self) -> str:
        """Handle telemetry settings in Qt installer."""
        return self._get_config().get("qtofficial", "telemetry", fallback="No")

    @property
    def qt_installer_unattended(self) -> bool:
        """Control whether to use unattended installation flags."""
        return self._get_config().getboolean("qtofficial", "unattended", fallback=True)

    def qt_installer_cleanup(self) -> None:
        """Control whether to use unattended installation flags."""
        import shutil

        shutil.rmtree(self.qt_installer_temp_path)


Settings = SettingsClass()


def setup_logging(env_key="LOG_CFG"):
    config = os.getenv(env_key, None)
    if config is not None and os.path.exists(config):
        Settings.loggingconf = config
    logging.config.fileConfig(Settings.loggingconf)


def safely_run(cmd: List[str], timeout: int) -> None:
    try:
        subprocess.run(cmd, shell=False, timeout=timeout)
    except Exception:
        raise


def safely_run_save_output(cmd: List[str], timeout: int) -> Any:
    try:
        result = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=timeout)
        return result
    except Exception:
        raise


def extract_auth(args: List[str]) -> Tuple[str | None, str | None, List[str] | None]:
    username = None
    password = None
    i = 0
    while i < len(args):
        if args[i] == "--email":
            if i + 1 < len(args):
                username = args[i + 1]
                del args[i : i + 2]
            else:
                del args[i]
            continue
        elif args[i] == "--pw":
            if i + 1 < len(args):
                password = args[i + 1]
                del args[i : i + 2]
            else:
                del args[i]
            continue
        i += 1
    return username, password, args


def download_installer(base_url: str, installer_filename: str, target_path: Path, timeout: Tuple[float, float]) -> None:
    base_path = f"official_releases/online_installers/{installer_filename}"
    url = f"{base_url}/{base_path}"
    try:
        hash = get_hash(base_path, Settings.hash_algorithm, timeout)
        downloadBinaryFile(url, target_path, Settings.hash_algorithm, hash, timeout=timeout)
    except Exception as e:
        raise RuntimeError(f"Failed to download installer: {e}")


def prepare_installer(installer_path: Path, os_name: str) -> Path:
    """
    Prepares the installer for execution. This may involve setting the correct permissions or
    extracting the installer if it's packaged. Returns the path to the installer executable.
    """
    if os_name == "linux":
        os.chmod(installer_path, 0o500)
        return installer_path
    elif os_name == "mac":
        volume_path = Path(f"/Volumes/{str(uuid.uuid4())}")
        subprocess.run(
            ["hdiutil", "attach", str(installer_path), "-mountpoint", str(volume_path)],
            stdout=subprocess.DEVNULL,
            check=True,
        )
        try:
            src_app_name = next(volume_path.glob("*.app")).name
            dst_app_path = installer_path.with_suffix(".app")
            shutil.copytree(volume_path / src_app_name, dst_app_path)
        finally:
            subprocess.run(["hdiutil", "detach", str(volume_path), "-force"], stdout=subprocess.DEVNULL, check=True)
        return dst_app_path / "Contents" / "MacOS" / Path(src_app_name).stem
    else:
        return installer_path

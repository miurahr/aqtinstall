import ast
import configparser
import json
import logging
import multiprocessing
import os
import pathlib
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from typing import List, Optional

import requests


def _get_meta(url: str):
    return requests.get(url + '.meta4')


def _check_content_type(ct: str) -> bool:
    candidate = ['application/metalink4+xml', 'text/plain']
    return any(ct.startswith(t) for t in candidate)


def altlink(url: str, alt: str, logger=None):
    '''Blacklisting redirected(alt) location based on Settings.blacklist configuration.
     When found black url, then try download a url + .meta4 that is a metalink version4
     xml file, parse it and retrieve best alternative url.'''
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
        if not _check_content_type(m.headers['content-type']):
            logger.error("Unexpected meta4 response;content-type: {}".format(m.headers['content-type']))
            return alt
        try:
            mirror_xml = ElementTree.fromstring(m.text)
            meta_urls = {}
            for f in mirror_xml.iter("{urn:ietf:params:xml:ns:metalink}file"):
                for u in f.iter("{urn:ietf:params:xml:ns:metalink}url"):
                    meta_urls[u.attrib['priority']] = u.text
            mirrors = [meta_urls[i] for i in sorted(meta_urls.keys(), key=lambda x: int(x))]
        except Exception:
            exc_info = sys.exc_info()
            logger.error("Unexpected meta4 file; parse error: {}".format(exc_info[1]))
            return alt
        else:
            # Return first priority item which is not blacklist in mirrors list,
            # if not found then return alt in default
            return next(filter(lambda mirror: not any(mirror.startswith(b) for b in blacklist), mirrors), alt)


def versiontuple(v: str):
    return tuple(map(int, (v.split("."))))


class Updater:

    def __init__(self, prefix: pathlib.Path, logger):
        self.logger = logger
        self.prefix = prefix
        self.qmake_path = None
        self.qconfigs = {}
        self._detect_qmake(prefix)

    def _patch_qtcore(self):
        framework_dir = self.prefix.joinpath("lib", "QtCore.framework")
        assert framework_dir.exists(), "Invalid installation prefix"
        for component in ["QtCore", "QtCore_debug"]:
            if framework_dir.joinpath(component).exists():
                qtcore_path = framework_dir.joinpath(component).resolve()
                self.logger.info("Patching {}".format(qtcore_path))
                self._patch_file(qtcore_path, bytes(str(self.prefix), "ascii"))

    def _patch_file(self, file: pathlib.Path, newpath: bytes):
        PREFIX_VAR = b"qt_prfxpath="
        st = file.stat()
        data = file.read_bytes()
        idx = data.find(PREFIX_VAR)
        if idx > 0:
            return
        assert len(newpath) < 256, "Qt Prefix path is too long(255)."
        data = data[:idx] + PREFIX_VAR + newpath + data[idx + len(newpath):]
        file.write_bytes(data)
        os.chmod(str(file), st.st_mode)

    def _detect_qmake(self, prefix):
        ''' detect Qt configurations from qmake
        '''
        for qmake_path in [prefix.joinpath('bin', 'qmake'), prefix.joinpath('bin', 'qmake.exe')]:
            if qmake_path.exists():
                result = subprocess.run([str(qmake_path), '-query'], stdout=subprocess.PIPE)
                if result.returncode == 0:
                    self.qmake_path = qmake_path
                    for line in result.stdout.splitlines():
                        vals = line.decode('UTF-8').split(':')
                        self.qconfigs[vals[0]] = vals[1]
                break

    def patch_qt(self, target):
        ''' patch works '''
        self.logger.info("Patching qmake")
        mac_exceptions = ['ios', 'android', 'wasm_32',
                          'android_x86_64', 'android_arm64_v8a', 'android_x86', 'android_armv7']
        if target.os_name == 'mac' and target.arch not in mac_exceptions:
            self._patch_qtcore()
        if self.qmake_path is not None:
            self._patch_file(self.qmake_path, bytes(str(self.prefix), 'UTF-8'))


class Settings(object):
    """Class to hold configuration and settings.
    Actual values are stored in 'settings.ini' file.
    It also holds a combinations database.
    """
    # this class is Borg/Singleton
    _shared_state = {
        '_config': None,
        '_combinations': None,
        '_lock': multiprocessing.Lock()
    }

    def __init__(self, config=None):
        self.__dict__ = self._shared_state
        if self._config is None:
            with self._lock:
                if self._config is None:
                    if config is None:
                        self.inifile = os.path.join(os.path.dirname(__file__), 'settings.ini')
                    else:
                        self.inifile = config
                    self._config = self.configParse(self.inifile)
                    with open(os.path.join(os.path.dirname(__file__), 'combinations.json'), 'r') as j:
                        self._combinations = json.load(j)[0]

    def configParse(self, file_path):
        if not os.path.exists(file_path):
            raise IOError(file_path)
        config = configparser.ConfigParser()
        config.read(file_path)
        return config

    @property
    def qt_combinations(self):
        return self._combinations['qt']

    @property
    def tools_combinations(self):
        return self._combinations['tools']

    @property
    def available_versions(self):
        return self._combinations['versions']

    def available_modules(self, qt_version):
        """Known module names

        :returns: dictionary of qt_version and module names
        :rtype: List[str]
        """
        modules = self._combinations['modules']
        versions = qt_version.split('.')
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

#!/usr/bin/env python3
#
# Copyright (C) 2018 Linus Jahn <lnj@kaidan.im>
# Copyright (C) 2019,2020 Hiroshi Miura <miurahr@linux.com>
# Copyright (C) 2020, Aurélien Gâteau
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

import concurrent.futures
import os
import pathlib
import subprocess
import sys
import time
from logging import getLogger

import py7zr
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from aqt.archives import QtPackage
from aqt.helper import altlink, versiontuple
from aqt.qtpatch import Updater
from aqt.settings import Settings


class ExtractionError(Exception):
    pass


class QtInstaller:
    """
    Installer class to download packages and extract it.
    """
    def __init__(self, qt_archives, logging=None, command=None, target_dir=None):
        self.qt_archives = qt_archives
        if logging:
            self.logger = logging
        else:
            self.logger = getLogger('aqt')
        self.command = command
        if target_dir is None:
            self.base_dir = os.getcwd()
        else:
            self.base_dir = target_dir
        self.settings = Settings()

    def retrieve_archive(self, package: QtPackage):
        archive = package.archive
        url = package.url
        name = package.name
        start_time = time.perf_counter()
        self.logger.info("Downloading {}...".format(name))
        self.logger.debug("Download URL: {}".format(url))
        session = requests.Session()
        retry = Retry(connect=5, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        try:
            r = session.get(url, allow_redirects=False, stream=True)
            if r.status_code == 302:
                newurl = altlink(r.url, r.headers['Location'], logger=self.logger)
                self.logger.info('Redirected URL: {}'.format(newurl))
                r = session.get(newurl, stream=True)
        except requests.exceptions.ConnectionError as e:
            self.logger.error("Connection error: %s" % e.args)
            raise e
        else:
            try:
                with open(archive, 'wb') as fd:
                    for chunk in r.iter_content(chunk_size=8196):
                        fd.write(chunk)
                        fd.flush()
                if self.command is None:
                    with open(archive, 'rb') as fd:
                        self.extract_archive(fd)
            except Exception as e:
                exc = sys.exc_info()
                self.logger.error("Download error: %s" % exc[1])
                raise e
            else:
                if self.command is not None:
                    self.extract_archive_ext(archive)
        os.unlink(archive)
        self.logger.info("Finish installation of {} in {}".format(archive, time.perf_counter() - start_time))

    def extract_archive(self, archive):
        szf = py7zr.SevenZipFile(archive)
        szf.extractall(path=self.base_dir)
        szf.close()

    def extract_archive_ext(self, archive):
        if self.base_dir is not None:
            command_args = [self.command, 'x', '-aoa', '-bd', '-y', '-o{}'.format(self.base_dir), archive]
        else:
            command_args = [self.command, 'x', '-aoa', '-bd', '-y', archive]
        try:
            proc = subprocess.run(command_args, stdout=subprocess.PIPE, check=True)
            self.logger.debug(proc.stdout)
        except subprocess.CalledProcessError as cpe:
            self.logger.error("Extraction error: %d" % cpe.returncode)
            if cpe.stdout is not None:
                self.logger.error(cpe.stdout)
            if cpe.stderr is not None:
                self.logger.error(cpe.stderr)
            raise cpe

    def get_arch_dir(self, arch):
        if arch.startswith('win64_mingw'):
            arch_dir = arch[6:] + '_64'
        elif arch.startswith('win32_mingw'):
            arch_dir = arch[6:] + '_32'
        elif arch.startswith('win'):
            arch_dir = arch[6:]
        else:
            arch_dir = arch
        return arch_dir

    def make_conf_files(self, qt_version, arch):
        """Make Qt configuration files, qt.conf and qtconfig.pri"""
        arch_dir = self.get_arch_dir(arch)
        try:
            # prepare qt.conf
            with open(os.path.join(self.base_dir, qt_version, arch_dir, 'bin', 'qt.conf'), 'w') as f:
                f.write("[Paths]\n")
                f.write("Prefix=..\n")
            # update qtconfig.pri only as OpenSource
            with open(os.path.join(self.base_dir, qt_version, arch_dir, 'mkspecs', 'qconfig.pri'), 'r+') as f:
                lines = f.readlines()
                f.seek(0)
                f.truncate()
                for line in lines:
                    if line.startswith('QT_EDITION ='):
                        line = 'QT_EDITION = OpenSource\n'
                    if line.startswith('QT_LICHECK ='):
                        line = 'QT_LICHECK =\n'
                    f.write(line)
        except IOError as e:
            self.logger.error("Configuration file generation error: %s\n", e.args, exc_info=True)
            raise e

    def install(self):
        with concurrent.futures.ThreadPoolExecutor(self.settings.concurrency) as executor:
            futures = [executor.submit(self.retrieve_archive, ar) for ar in self.qt_archives.get_archives()]
            done, not_done = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_EXCEPTION)
            if len(not_done) > 0:
                self.logger.error("Installation error detected.")
                exit(1)
            try:
                for feature in done:
                    feature.result()
            except Exception:
                exit(1)

    def finalize(self):
        target = self.qt_archives.get_target_config()
        self.make_conf_files(target.version, target.arch)
        prefix = pathlib.Path(self.base_dir) / target.version / target.arch
        updater = Updater(prefix, self.logger)
        if versiontuple(target.version) < (5, 14, 2):
            updater.patch_qt(target)

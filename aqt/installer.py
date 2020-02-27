#!/usr/bin/env python3
#
# Copyright (C) 2018 Linus Jahn <lnj@kaidan.im>
# Copyright (C) 2019,2020 Hiroshi Miura <miurahr@linux.com>
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
import subprocess
import sys
import time
from logging import getLogger

import requests

import py7zr

from aqt.archives import QtPackage
from aqt.helper import altlink


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

    def retrieve_archive(self, package: QtPackage):
        archive = package.archive
        url = package.url
        self.logger.info("Downloading {}...".format(url))
        try:
            r = requests.get(url, allow_redirects=False, stream=True)
            if r.status_code == 302:
                newurl = altlink(r.url)
                self.logger.info('Redirected to new URL: {}'.format(newurl))
                r = requests.get(newurl, stream=True)
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
        self.logger.info("Finish installation of {} in {}".format(archive, time.process_time()))

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

    def make_conf_files(self, qt_version, arch_dir):
        """Make Qt configuration files, qt.conf and qtconfig.pri"""
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
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.retrieve_archive, ar) for ar in self.qt_archives.get_archives()]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        # finalize
        qt_version, target, arch = self.qt_archives.get_target_config()
        if qt_version != "Tools":  # tools installation
            if arch.startswith('win64_mingw'):
                arch_dir = arch[6:] + '_64'
            elif arch.startswith('win32_mingw'):
                arch_dir = arch[6:] + '_32'
            elif arch.startswith('win'):
                arch_dir = arch[6:]
            else:
                arch_dir = arch
            self.make_conf_files(qt_version, arch_dir)
        self.logger.info("Finished installation")

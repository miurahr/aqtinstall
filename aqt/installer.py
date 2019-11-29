#!/usr/bin/env python3
#
# Copyright (C) 2018 Linus Jahn <lnj@kaidan.im>
# Copyright (C) 2019 Hiroshi Miura <miurahr@linux.com>
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

import functools
import os
import sys
from logging import getLogger
from multiprocessing.dummy import Pool
from operator import and_
from subprocess import run

import requests

from aqt.helper import altlink

if sys.version_info > (3, 5):
    import py7zr

NUM_PROCESS = 3


class BadPackageFile(Exception):
    pass


class QtInstaller:
    """
    Installer class to download packages and extract it.
    """

    def __init__(self, qt_archives, logging=None):
        self.qt_archives = qt_archives
        if logging:
            self.logger = logging
        else:
            self.logger = getLogger('aqt')

    def retrieve_archive(self, package, path=None, command=None):
        archive = package.archive
        url = package.url
        self.logger.info("-Downloading {}...".format(url))
        try:
            r = requests.get(url, allow_redirects=False, stream=True)
            if r.status_code == 302:
                newurl = altlink(r.url)
                # newurl = r.headers['Location']
                self.logger.info('Redirected to new URL: {}'.format(newurl))
                r = requests.get(newurl, stream=True)
        except requests.exceptions.ConnectionError as e:
            self.logger.warning("Caught download error: %s" % e.args)
            return False
        else:
            with open(archive, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=8196):
                    fd.write(chunk)
            self.logger.info("-Extracting {}...".format(archive))

            if sys.version_info > (3, 5):
                if not py7zr.is_7zfile(archive):
                    raise BadPackageFile
            if command is None:
                py7zr.SevenZipFile(archive).extractall(path=path)
            else:
                if path is not None:
                    run([command, 'x', '-aoa', '-bd', '-y', '-o{}'.format(path), archive])
                else:
                    run([command, 'x', '-aoa', '-bd', '-y', archive])
            os.unlink(archive)
        return True

    def install(self, command=None, target_dir=None):
        qt_version, target, arch = self.qt_archives.get_target_config()
        if target_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = target_dir
        archives = self.qt_archives.get_archives()
        p = Pool(NUM_PROCESS)
        ret_arr = p.map(functools.partial(self.retrieve_archive, command=command, path=base_dir), archives)
        ret = functools.reduce(and_, ret_arr)
        if not ret:  # fails to install
            self.logger.error("Failed to install.")
            exit(1)
        if qt_version == "Tools":  # tools installation
            return
        # finalize
        if arch.startswith('win64_mingw'):
            arch_dir = arch[6:] + '_64'
        elif arch.startswith('win32_mingw'):
            arch_dir = arch[6:] + '_32'
        elif arch.startswith('win'):
            arch_dir = arch[6:]
        else:
            arch_dir = arch
        self.make_conf_files(base_dir, qt_version, arch_dir)

    def make_conf_files(self, base_dir, qt_version, arch_dir):
        """Make Qt configuration files, qt.conf and qtconfig.pri"""
        try:
            # prepare qt.conf
            with open(os.path.join(base_dir, qt_version, arch_dir, 'bin', 'qt.conf'), 'w') as f:
                f.write("[Paths]\n")
                f.write("Prefix=..\n")
            # update qtconfig.pri only as OpenSource
            with open(os.path.join(base_dir, qt_version, arch_dir, 'mkspecs', 'qconfig.pri'), 'r+') as f:
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

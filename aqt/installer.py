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

import os
import subprocess
import threading
from logging import getLogger

import requests

import py7zr
from aqt.helper import altlink


class BadPackageFile(Exception):
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
        # Limit the number of threads.
        self.pool = threading.BoundedSemaphore(3)
        self.ex_pool = threading.BoundedSemaphore(4)

    def retrieve_archive(self, package):
        archive = package.archive
        url = package.url
        try:
            self.pool.acquire(blocking=True)
            r = requests.get(url, allow_redirects=False, stream=True)
            if r.status_code == 302:
                newurl = altlink(r.url)
                # newurl = r.headers['Location']
                self.logger.info('Redirected to new URL: {}'.format(newurl))
                r = requests.get(newurl, stream=True)
        except requests.exceptions.ConnectionError as e:
            self.logger.warning("Caught download error: %s" % e.args)
            self.pool.release()
            return None
        else:
            try:
                with open(archive, 'wb') as fd:
                    for chunk in r.iter_content(chunk_size=8196):
                        fd.write(chunk)
            except Exception as e:
                self.logger.warning("Caught download error: %s" % e.args)
                self.pool.release()
                return None
            else:
                self.pool.release()

    def extract_archive(self, archive):
        self.ex_pool.acquire(blocking=True)
        py7zr.SevenZipFile(archive).extractall(path=self.base_dir)
        os.unlink(archive)
        self.ex_pool.release()

    def extract_archive_ext(self, archive):
        if self.base_dir is not None:
            with subprocess.Popen([self.command, 'x', '-aoa', '-bd', '-y', '-o{}'.format(self.base_dir), archive],
                                  stdout=subprocess.PIPE) as proc:
                self.logger.debug(proc.stdout.read())
        else:
            with subprocess.Popen([self.command, 'x', '-aoa', '-bd', '-y', archive], stdout=subprocess.PIPE) as proc:
                self.logger.debug(proc.stdout.read())
        os.unlink(archive)

    def install(self):
        qt_version, target, arch = self.qt_archives.get_target_config()
        if self.command is None:
            extractor = self.extract_archive
        else:
            extractor = self.extract_archive_ext
        archives = self.qt_archives.get_archives()
        # retrieve files from download site
        download_threads = []
        extract_processes = []
        completed_downloads = []
        for pkg in archives:
            self.logger.info("Downloading {}...".format(pkg.url))
            t = threading.Thread(target=self.retrieve_archive, args=(pkg,))
            download_threads.append((t, pkg.archive))
            completed_downloads.append(False)
            t.start()
        while True:
            all_done = True
            for i, (t, a) in enumerate(download_threads):
                if not completed_downloads[i]:
                    t.join(0.05)
                    if not t.is_alive():
                        completed_downloads[i] = True
                        self.logger.info("Extracting {}...".format(a))
                        p = threading.Thread(target=extractor, args=(a,))
                        extract_processes.append(p)
                        p.start()
                    else:
                        all_done = False
            if all_done:
                break
        for p in extract_processes:
            p.join()
        self.logger.info("Done extraction.")

        # finalize
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

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
import sys
import threading
import time
from logging import getLogger

import requests

import py7zr
from aqt.archives import QtPackage
from aqt.helper import altlink


class DownloadFailure(Exception):
    pass


class ExtractionFailure(Exception):
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
        self.ex_pool = threading.BoundedSemaphore(6)

    def retrieve_archive(self, package: QtPackage, results: dict):
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
            self.logger.error("Caught download error: %s" % e.args)
            self.pool.release()
            results[archive] = False
        else:
            try:
                with open(archive, 'wb') as fd:
                    for chunk in r.iter_content(chunk_size=8196):
                        fd.write(chunk)
            except Exception:
                exc = sys.exc_info()
                self.logger.error("Caught extraction error: %s" % exc[1])
                self.pool.release()
                results[archive] = False
            else:
                self.pool.release()
                results[archive] = True

    def extract_archive(self, archive, results: dict):
        self.ex_pool.acquire(blocking=True)
        try:
            szf = py7zr.SevenZipFile(archive)
            szf.extractall(path=self.base_dir)
            os.unlink(archive)
        except Exception:
            exc = sys.exc_info()
            self.logger.error("Caught extraction error: %s" % exc[1])
            results[archive] = False
        else:
            results[archive] = True
        self.ex_pool.release()

    def extract_archive_ext(self, archive, results: dict):
        if self.base_dir is not None:
            command_args = [self.command, 'x', '-aoa', '-bd', '-y', '-o{}'.format(self.base_dir), archive]
        else:
            command_args = [self.command, 'x', '-aoa', '-bd', '-y', archive]
        try:
            proc = subprocess.run(command_args, stdout=subprocess.PIPE, check=True)
            self.logger.debug(proc.stdout)
        except subprocess.CalledProcessError as cpe:
            self.logger.warning("Caught extraction error: %d" % cpe.returncode)
            if cpe.stdout is not None:
                self.logger.error(cpe.stdout)
            if cpe.stderr is not None:
                self.logger.error(cpe.stderr)
            results[archive] = False
        else:
            results[archive] = True
        os.unlink(archive)

    def install(self):
        qt_version, target, arch = self.qt_archives.get_target_config()
        if self.command is None:
            extractor = self.extract_archive
        else:
            extractor = self.extract_archive_ext
        archives = self.qt_archives.get_archives()
        # retrieve files from download site
        download_threads = {}
        download_results = {}
        extract_threads = {}
        extract_results = {}
        completed_downloads = {}
        completed_extracts = {}
        for pkg in archives:
            self.logger.info("Downloading {}...".format(pkg.url))
            t = threading.Thread(target=self.retrieve_archive, args=(pkg, download_results))
            a = pkg.archive
            download_threads[a] = t
            completed_downloads[a] = False
            extract_threads[a] = None
            completed_extracts[a] = False
            t.start()
        while True:
            all_done = True
            for a in download_threads:
                if not completed_downloads[a]:
                    # check download completion
                    t = download_threads[a]
                    t.join(0.005)
                    if not t.is_alive():
                        # download is completed, check result
                        if not download_results[a]:
                            self.logger.error("Failed to download {}".format(a))
                            raise DownloadFailure()
                        completed_downloads[a] = True
                        # start extraction
                        self.logger.info("Extracting {}...".format(a))
                        p = threading.Thread(target=extractor, args=(a, extract_results))
                        p.start()
                        extract_threads[a] = p
                    else:
                        all_done = False
                elif extract_threads[a] is None or completed_extracts[a]:
                    # not started or already done
                    pass
                else:
                    # check extraction status
                    p = extract_threads[a]
                    p.join(0.005)
                    if not p.is_alive():
                        if extract_results[a]:
                            completed_extracts[a] = True
                        else:
                            self.logger.error("Failed to extract {}".format(a))
                            raise ExtractionFailure()
                    else:
                        # still running decompression
                        pass
            if all_done:
                break
            time.sleep(0.5)
        for a in extract_threads:
            if not completed_extracts[a]:
                p = extract_threads[a]
                p.join()
                if not extract_results[a]:
                    self.logger.error("Failed to extract {}".format(a))
                    raise ExtractionFailure()
                else:
                    completed_extracts[a] = True
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

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

from aqt.helper import altlink, versiontuple
from aqt.qtpatch import Updater


class ExtractionError(Exception):
    pass


def install(qt_archive, base_dir, command):
    name = qt_archive.name
    url = qt_archive.url
    archive = qt_archive.archive
    start_time = time.perf_counter()
    logger = getLogger('aqt')
    logger.info("Downloading {}...".format(name))
    logger.debug("Download URL: {}".format(url))
    session = requests.Session()
    retry = Retry(connect=5, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    try:
        r = session.get(url, allow_redirects=False, stream=True)
        if r.status_code == 302:
            newurl = altlink(r.url, r.headers['Location'], logger=logger)
            logger.info('Redirected URL: {}'.format(newurl))
            r = session.get(newurl, stream=True)
    except requests.exceptions.ConnectionError as e:
        logger.error("Connection error: %s" % e.args)
        raise e
    else:
        try:
            with open(archive, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=8196):
                    fd.write(chunk)
                    fd.flush()
            if command is None:
                with py7zr.SevenZipFile(archive, 'r') as szf:
                    szf.extractall(path=base_dir)
        except Exception as e:
            exc = sys.exc_info()
            logger.error("Download error: %s" % exc[1])
            raise e
        else:
            if command is not None:
                if base_dir is not None:
                    command_args = [command, 'x', '-aoa', '-bd', '-y', '-o{}'.format(base_dir), archive]
                else:
                    command_args = [command, 'x', '-aoa', '-bd', '-y', archive]
                try:
                    proc = subprocess.run(command_args, stdout=subprocess.PIPE, check=True)
                    logger.debug(proc.stdout)
                except subprocess.CalledProcessError as cpe:
                    logger.error("Extraction error: %d" % cpe.returncode)
                    if cpe.stdout is not None:
                        logger.error(cpe.stdout)
                    if cpe.stderr is not None:
                        logger.error(cpe.stderr)
                    raise cpe
    os.unlink(archive)
    logger.info("Finish installation of {} in {}".format(archive, time.perf_counter() - start_time))


def finisher(target, base_dir, logger):
    """Make Qt configuration files, qt.conf and qtconfig.pri"""
    qt_version = target.version
    arch = target.arch
    if arch.startswith('win64_mingw'):
        arch_dir = arch[6:] + '_64'
    elif arch.startswith('win32_mingw'):
        arch_dir = arch[6:] + '_32'
    elif arch.startswith('win'):
        arch_dir = arch[6:]
    else:
        arch_dir = arch
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
        raise e
    prefix = pathlib.Path(base_dir) / target.version / target.arch
    updater = Updater(prefix, logger)
    if versiontuple(target.version) < (5, 14, 2):
        updater.patch_qt(target)


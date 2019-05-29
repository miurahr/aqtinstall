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
import logging
import os
import platform
import requests
import sys
import traceback
import aqt.metalink
from six import StringIO
from multiprocessing.dummy import Pool
from operator import and_
if sys.version_info.major == 3:
    from subprocess import run
else:
    from subprocess import call as run


NUM_PROCESS = 3


class QtInstaller:
    """
    Installer class to download packages and extract it.
    """

    def __init__(self, qt_archives):
        self.qt_archives = qt_archives

    @staticmethod
    def retrieve_archive(package, path=None):
        archive = package.archive
        url = package.url
        print("-Downloading {}...".format(url))
        try:
            if package.has_mirror:
                r = aqt.metalink.get(url, stream=True)
            else:
                r = requests.get(url, stream=True)
        except requests.exceptions.ConnectionError as e:
            print("Caught download error: %s" % e.args)
            return False
        else:
            with open(archive, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=8196):
                    fd.write(chunk)
            sys.stdout.write("\033[K")
            print("-Extracting {}...".format(archive))
            if platform.system() == 'Windows':
                if path is not None:
                    run([r'C:\Program Files\7-Zip\7z.exe', 'x', '-aoa', '-y', '-o{}'.format(path), archive])
                else:
                    run([r'C:\Program Files\7-Zip\7z.exe', 'x', '-aoa', '-y', archive])
            else:
                if path is not None:
                    run([r'7zr', 'x', '-aoa', '-y', '-o{}'.format(path), archive])
                else:
                    run([r'7zr', 'x', '-aoa', '-y', archive])
            os.unlink(archive)
        return True

    @staticmethod
    def get_base_dir(qt_version, target_dir=None):
        if target_dir is not None:
            return os.path.join(target_dir, 'Qt{}'.format(qt_version))
        else:
            return os.path.join(os.getcwd(), 'Qt{}'.format(qt_version))

    def install(self, target_dir=None):
        qt_version, target, arch = self.qt_archives.get_target_config()
        base_dir = self.get_base_dir(qt_version, target_dir)
        archives = self.qt_archives.get_archives()
        p = Pool(NUM_PROCESS)
        ret_arr = p.map(functools.partial(self.retrieve_archive, path=base_dir), archives)
        ret = functools.reduce(and_, ret_arr)
        if ret:
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
                # prepare qtconfig.pri
                with open(os.path.join(base_dir, qt_version, arch_dir, 'mkspecs', 'qconfig.pri'), 'r+') as f:
                    lines = f.readlines()
                    f.seek(0)
                    f.truncate()
                    for line in lines:
                        if 'QT_EDITION' in line:
                            line = 'QT_EDITION = OpenSource'
                        f.write(line)
            except IOError as e:
                print("Configuration file generation error: %s" % e.args)
                exc_buffer = StringIO()
                traceback.print_exc(file=exc_buffer)
                logging.error('Error happened when writing configuration files:\n%s', exc_buffer.getvalue())
                raise e
        else:
            exit(1)

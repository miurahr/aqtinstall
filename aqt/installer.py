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

import logging
import os
import platform
import sys
import traceback
import aqt.requests as requests
from six import StringIO
from multiprocessing.dummy import Pool
if sys.version_info.major == 3:
    from subprocess import run
else:
    from subprocess import call as run


NUM_PROCESS = 3


class QtInstaller:
    def __init__(self, qt_archives):
        self.qt_archives = qt_archives

    @staticmethod
    def retrieve_archive(package):
        archive = package.get_archive()
        url = package.get_url()
        sys.stdout.write("\033[K")
        print("-Downloading {}...".format(url))
        try:
            r = requests.get(url, stream=True)
        except requests.exceptions.ConnectionError as e:
            print("Caught download error: %s" % e.args)
            exc_buffer = StringIO()
            traceback.print_exc(file=exc_buffer)
            logging.error('Uncaught exception in worker process:\n%s', exc_buffer.getvalue())
            raise e
        else:
            with open(archive, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=8196):
                    fd.write(chunk)
            sys.stdout.write("\033[K")
            print("-Extracting {}...".format(archive))
            if platform.system() == 'Windows':
                run([r'C:\Program Files\7-Zip\7z.exe', 'x', '-aoa', '-y', archive])
            else:
                run([r'7zr', 'x', '-aoa', '-y', archive])
            os.unlink(archive)

    @staticmethod
    def get_base_dir(qt_version):
        return os.path.join(os.getcwd(), 'Qt{}'.format(qt_version))

    def install(self):
        qt_version, target, arch = self.qt_archives.get_target_config()
        if arch.startswith('win'):
            arch_dir = arch[6:]
        else:
            arch_dir = arch
        base_dir = self.get_base_dir(qt_version)
        if not os.path.exists(base_dir):
            os.mkdir(base_dir)
        elif not os.path.isdir(base_dir):
            os.unlink(base_dir)
            os.mkdir(base_dir)
        os.chdir(base_dir)

        archives = self.qt_archives.get_archives()
        p = Pool(NUM_PROCESS)
        p.map(self.retrieve_archive, archives)

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

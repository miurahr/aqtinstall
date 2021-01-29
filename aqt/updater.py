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

import os
import pathlib
import subprocess


class Updater:

    def __init__(self, prefix: pathlib.Path, logger):
        self.logger = logger
        self.prefix = prefix
        self.qmake_path = None
        self.qconfigs = {}
        self._detect_qmake(prefix)

    def _patch_qtcore(self, lib_dir, components, encoding):
        for component in components:
            if lib_dir.joinpath(component).exists():
                qtcore_path = lib_dir.joinpath(component).resolve()
                self.logger.info("Patching {}".format(qtcore_path))
                newpath = bytes(str(self.prefix), encoding)
                self._patch_binfile(qtcore_path, b"qt_prfxpath=", newpath)

    def _patch_binfile(self, file: pathlib.Path, key: bytes, newpath: bytes):
        """Patch binary file with key/value"""
        st = file.stat()
        data = file.read_bytes()
        idx = data.find(key)
        if idx > 0:
            return
        assert len(newpath) < 256, "Qt Prefix path is too long(255)."
        data = data[:idx] + key + newpath + data[idx + len(newpath):]
        file.write_bytes(data)
        os.chmod(str(file), st.st_mode)

    def _patch_pkgconfig(self, file: pathlib.Path):
        for pcfile in file.glob("*.pc"):
            self.logger.info("Patching {}".format(pcfile))
            self._patch_textfile(pcfile, "prefix=/home/qt/work/install", 'prefix={}'.format(str(self.prefix)))

    def _patch_textfile(self, file: pathlib.Path, old: str, new: str):
        st = file.stat()
        data = file.read_text("UTF-8")
        data = data.replace(old, new)
        file.write_text(data, "UTF-8")
        os.chmod(str(file), st.st_mode)

    def _detect_qmake(self, prefix):
        """ detect Qt configurations from qmake
        """
        for qmake_path in [prefix.joinpath('bin', 'qmake'), prefix.joinpath('bin', 'qmake.exe')]:
            if not qmake_path.exists():
                return
            try:
                result = subprocess.run([str(qmake_path), '-query'], stdout=subprocess.PIPE)
            except subprocess.SubprocessError:
                return
            else:
                if result.returncode == 0:
                    self.qmake_path = qmake_path
                    for line in result.stdout.splitlines():
                        vals = line.decode('UTF-8').split(':')
                        self.qconfigs[vals[0]] = vals[1]

    def _versiontuple(self, v: str):
        return tuple(map(int, (v.split("."))))

    def qtpatch(self, target):
        """ patch works """
        if target.os_name == 'linux':
            self.logger.info("Patching pkgconfig configurations")
            self._patch_pkgconfig(self.prefix.joinpath("lib", "pkgconfig"))

        if target.arch not in ['ios', 'android', 'wasm_32', 'android_x86_64', 'android_arm64_v8a', 'android_x86',
                               'android_armv7']:
            if target.os_name == 'mac':
                self.logger.info("Patching QtCore")
                self._patch_qtcore(self.prefix.joinpath("lib", "QtCore.framework"), ["QtCore", "QtCore_debug"], "UTF-8")
            elif target.os_name == 'linux':
                self.logger.info("Patching libQt(5|6)Core")
                self._patch_qtcore(self.prefix.joinpath("lib"), ["libQt5Core.so", "libQt6Core.so"], "UTF-8")
            elif target.os_name == 'windows':
                self.logger.info("Patching Qt(5|6)Core.dll")
                self._patch_qtcore(self.prefix.joinpath("bin"), ["Qt5Cored.dll", "Qt5Core.dll", "Qt6Core.dll",
                                                                 "Qt6Cored.dll"], "UTF-8")
            else:
                # no need to patch Qt5Core
                pass

        if self.qmake_path is not None:
            self.logger.info("Patching qmake")
            self._patch_binfile(self.qmake_path, key=b"qt_prfxpath=", newpath=bytes(str(self.prefix), 'UTF-8'))

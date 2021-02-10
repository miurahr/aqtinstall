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

    def _detect_qmake(self) -> bool:
        """detect Qt configurations from qmake."""
        for qmake_path in [self.prefix.joinpath('bin', 'qmake'), self.prefix.joinpath('bin', 'qmake.exe')]:
            if not qmake_path.exists():
                return False
            try:
                result = subprocess.run([str(qmake_path), '-query'], stdout=subprocess.PIPE)
            except subprocess.SubprocessError:
                return False
            if result.returncode == 0:
                self.qmake_path = qmake_path
                for line in result.stdout.splitlines():
                    vals = line.decode('UTF-8').split(':')
                    self.qconfigs[vals[0]] = vals[1]
                return True
            else:
                return False

    def _versiontuple(self, v: str):
        return tuple(map(int, (v.split("."))))

    def patch_qmake(self):
        """Patch to qmake binary"""
        if self._detect_qmake():
            self.logger.info("Patching qmake binary")
            self._patch_binfile(self.qmake_path, key=b"qt_prfxpath=", newpath=bytes(str(self.prefix), 'UTF-8'))

    def patch_qmake_script(self, base_dir, qt_version, os_name):
        self.logger.info("Patching qmake script")
        if os_name == 'linux':
            self._patch_textfile(self.prefix / 'bin' / 'qmake',
                                 '/home/qt/work/install/bin',
                                 '{}/{}/{}/bin'.format(base_dir, qt_version, 'gcc_64'))
        elif os_name == 'mac':
            self._patch_textfile(self.prefix / 'bin' / 'qmake',
                         '/Users/qt/work/install/bin',
                         '{}/{}/{}/bin'.format(base_dir, qt_version, 'clang_64'))
        elif os_name == 'windows':
            self._patch_textfile(self.prefix / 'bin' / 'qmake.bat',
                                 '/Users/qt/work/install/bin',
                                 '{}\\{}\\{}\\bin'.format(base_dir, qt_version, 'mingw81_64'))
        else:
            pass

    def qtpatch(self, target):
        """ patch to QtCore"""
        if target.os_name == 'mac':
            self.logger.info("Patching QtCore")
            self._patch_qtcore(self.prefix.joinpath("lib", "QtCore.framework"), ["QtCore", "QtCore_debug"], "UTF-8")
        elif target.os_name == 'linux':
            self.logger.info("Patching pkgconfig configurations")
            self._patch_pkgconfig(self.prefix.joinpath("lib", "pkgconfig"))
            self.logger.info("Patching libQt(5|6)Core")
            self._patch_qtcore(self.prefix.joinpath("lib"), ["libQt5Core.so", "libQt6Core.so"], "UTF-8")
        elif target.os_name == 'windows':
            self.logger.info("Patching Qt(5|6)Core.dll")
            self._patch_qtcore(self.prefix.joinpath("bin"), ["Qt5Cored.dll", "Qt5Core.dll", "Qt6Core.dll",
                                                             "Qt6Cored.dll"], "UTF-8")
        else:
            # no need to patch Qt5Core
            pass

    def make_qtconf(self, base_dir, qt_version, arch_dir):
        """Prepare qt.conf"""
        with open(os.path.join(base_dir, qt_version, arch_dir, 'bin', 'qt.conf'), 'w') as f:
            f.write("[Paths]\n")
            f.write("Prefix=..\n")

    def set_license(self, base_dir, qt_version, arch_dir):
        """Update qtconfig.pri as OpenSource"""
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

    @classmethod
    def update(cls, target, base_dir, logger):
        """
        Make Qt configuration files, qt.conf and qtconfig.pri.
        And update pkgconfig and patch Qt5Core and qmake
        """
        qt_version = target.version
        arch = target.arch
        if arch is None:
            arch_dir = ''
        elif arch.startswith('win64_mingw'):
            arch_dir = arch[6:] + '_64'
        elif arch.startswith('win32_mingw'):
            arch_dir = arch[6:] + '_32'
        elif arch.startswith('win'):
            arch_dir = arch[6:]
        else:
            arch_dir = arch
        try:
            prefix = pathlib.Path(base_dir) / target.version / target.arch
            updater = Updater(prefix, logger)
            updater.set_license(base_dir, qt_version, arch_dir)
            if target.arch not in ['ios', 'android', 'wasm_32', 'android_x86_64', 'android_arm64_v8a', 'android_x86',
                                   'android_armv7']:  # desktop version
                updater.make_qtconf(base_dir, qt_version, arch_dir)
                updater.qtpatch(target)
                updater.patch_qmake()
            elif qt_version.startswith('5.'):  # qt5 non-desktop
                updater.patch_qmake()
            else:  # qt6 non-desktop
                updater.patch_qmake_script(base_dir, qt_version, target.os_name)
        except IOError as e:
            raise e

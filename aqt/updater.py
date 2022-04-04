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
import logging
import os
import pathlib
import re
import subprocess
from logging import getLogger
from typing import Union

import patch

from aqt.archives import TargetConfig
from aqt.exceptions import UpdaterError
from aqt.helper import Settings
from aqt.metadata import SimpleSpec, Version


def default_desktop_arch_dir(host: str, version: Union[Version, str]) -> str:
    version: Version = version if isinstance(version, Version) else Version(version)
    if host == "linux":
        return "gcc_64"
    elif host == "mac":
        return "macos" if version in SimpleSpec(">=6.1.2") else "clang_64"
    else:  # Windows
        # This is a temporary solution. This arch directory cannot exist for many versions of Qt.
        # TODO: determine this dynamically
        return "mingw81_64"


def dir_for_version(ver: Version) -> str:
    return "5.9" if ver == Version("5.9.0") else f"{ver.major}.{ver.minor}.{ver.patch}"


def unpatched_path(os_name: str, final_component: str) -> str:
    return ("/home/qt/work/install" if os_name == "linux" else "/Users/qt/work/install") + "/" + final_component


class Updater:
    def __init__(self, prefix: pathlib.Path, logger):
        self.logger = logger
        self.prefix = prefix
        self.qmake_path = None
        self.qconfigs = {}

    def _patch_binfile(self, file: pathlib.Path, key: bytes, newpath: bytes):
        """Patch binary file with key/value"""
        st = file.stat()
        data = file.read_bytes()
        idx = data.find(key)
        if idx < 0:
            return
        assert len(newpath) < 256, "Qt Prefix path is too long(255)."
        oldlen = data[idx + len(key) :].find(b"\0")
        assert oldlen >= 0
        value = newpath + b"\0" * (oldlen - len(newpath))
        data = data[: idx + len(key)] + value + data[idx + len(key) + len(value) :]
        file.write_bytes(data)
        os.chmod(str(file), st.st_mode)

    def _append_string(self, file: pathlib.Path, val: str):
        """Append string to file"""
        st = file.stat()
        data = file.read_text("UTF-8")
        data += val
        file.write_text(data, "UTF-8")
        os.chmod(str(file), st.st_mode)

    def _patch_textfile(self, file: pathlib.Path, old: str, new: str):
        st = file.stat()
        data = file.read_text("UTF-8")
        data = data.replace(old, new)
        file.write_text(data, "UTF-8")
        os.chmod(str(file), st.st_mode)

    def _detect_qmake(self) -> bool:
        """detect Qt configurations from qmake."""
        for qmake_path in [
            self.prefix.joinpath("bin", "qmake"),
            self.prefix.joinpath("bin", "qmake.exe"),
        ]:
            if not qmake_path.exists():
                continue
            try:
                result = subprocess.run([str(qmake_path), "-query"], stdout=subprocess.PIPE)
            except (subprocess.SubprocessError, IOError, OSError):
                return False
            if result.returncode == 0:
                self.qmake_path = qmake_path
                for line in result.stdout.splitlines():
                    vals = line.decode("UTF-8").split(":")
                    self.qconfigs[vals[0]] = vals[1]
                return True
        return False

    def patch_pkgconfig(self, oldvalue, os_name):
        for pcfile in self.prefix.joinpath("lib", "pkgconfig").glob("*.pc"):
            self.logger.info("Patching {}".format(pcfile))
            self._patch_textfile(
                pcfile,
                "prefix={}".format(oldvalue),
                "prefix={}".format(str(self.prefix)),
            )
            if os_name == "mac":
                self._patch_textfile(
                    pcfile,
                    "-F{}".format(os.path.join(oldvalue, "lib")),
                    "-F{}".format(os.path.join(str(self.prefix), "lib")),
                )

    def patch_libtool(self, oldvalue, os_name):
        for lafile in self.prefix.joinpath("lib").glob("*.la"):
            self.logger.info("Patching {}".format(lafile))
            self._patch_textfile(
                lafile,
                "libdir='={}'".format(oldvalue),
                "libdir='={}'".format(os.path.join(str(self.prefix), "lib")),
            )
            self._patch_textfile(
                lafile,
                "libdir='{}'".format(oldvalue),
                "libdir='{}'".format(os.path.join(str(self.prefix), "lib")),
            )
            self._patch_textfile(
                lafile,
                "-L={}".format(oldvalue),
                "-L={}".format(os.path.join(str(self.prefix), "lib")),
            )
            self._patch_textfile(
                lafile,
                "-L{}".format(oldvalue),
                "-L{}".format(os.path.join(str(self.prefix), "lib")),
            )
            if os_name == "mac":
                self._patch_textfile(
                    lafile,
                    "-F={}".format(oldvalue),
                    "-F={}".format(os.path.join(str(self.prefix), "lib")),
                )
                self._patch_textfile(
                    lafile,
                    "-F{}".format(oldvalue),
                    "-F{}".format(os.path.join(str(self.prefix), "lib")),
                )

    def patch_qmake(self):
        """Patch to qmake binary"""
        if self._detect_qmake():
            self.logger.info("Patching {}".format(str(self.qmake_path)))
            self._patch_binfile(
                self.qmake_path,
                key=b"qt_prfxpath=",
                newpath=bytes(str(self.prefix), "UTF-8"),
            )
            self._patch_binfile(
                self.qmake_path,
                key=b"qt_epfxpath=",
                newpath=bytes(str(self.prefix), "UTF-8"),
            )
            self._patch_binfile(
                self.qmake_path,
                key=b"qt_hpfxpath=",
                newpath=bytes(str(self.prefix), "UTF-8"),
            )

    def patch_qmake_script(self, base_dir, qt_version: str, os_name):
        arch_dir = default_desktop_arch_dir(os_name, qt_version)
        sep = "\\" if os_name == "windows" else "/"
        patched = sep.join([base_dir, qt_version, arch_dir, "bin"])
        unpatched = unpatched_path(os_name, "bin")
        qmake_path = self.prefix / "bin" / ("qmake.bat" if os_name == "windows" else "qmake")
        self.logger.info(f"Patching {qmake_path}")
        self._patch_textfile(qmake_path, unpatched, patched)

    def patch_qtcore(self, target):
        """patch to QtCore"""
        if target.os_name == "mac":
            lib_dir = self.prefix.joinpath("lib", "QtCore.framework")
            components = ["QtCore", "QtCore_debug"]
        elif target.os_name == "linux":
            lib_dir = self.prefix.joinpath("lib")
            components = ["libQt5Core.so"]
        elif target.os_name == "windows":
            lib_dir = self.prefix.joinpath("bin")
            components = ["Qt5Cored.dll", "Qt5Core.dll"]
        else:
            return
        for component in components:
            if lib_dir.joinpath(component).exists():
                qtcore_path = lib_dir.joinpath(component).resolve()
                self.logger.info("Patching {}".format(qtcore_path))
                newpath = bytes(str(self.prefix), "UTF-8")
                self._patch_binfile(qtcore_path, b"qt_prfxpath=", newpath)

    def make_qtconf(self, base_dir, qt_version, arch_dir):
        """Prepare qt.conf"""
        with open(os.path.join(base_dir, qt_version, arch_dir, "bin", "qt.conf"), "w") as f:
            f.write("[Paths]\n")
            f.write("Prefix=..\n")

    def make_qtenv2(self, base_dir, qt_version, arch_dir):
        """Prepare qtenv2.bat"""
        with open(os.path.join(base_dir, qt_version, arch_dir, "bin", "qtenv2.bat"), "w") as f:
            f.write("@echo off\n")
            f.write("echo Setting up environment for Qt usage...\n")
            f.write("set PATH={};%PATH%\n".format(os.path.join(base_dir, qt_version, arch_dir, "bin")))
            f.write("cd /D {}\n".format(os.path.join(base_dir, qt_version, arch_dir)))
            f.write("echo Remember to call vcvarsall.bat to complete environment setup!\n")

    def set_license(self, base_dir, qt_version, arch_dir):
        """Update qtconfig.pri as OpenSource"""
        with open(os.path.join(base_dir, qt_version, arch_dir, "mkspecs", "qconfig.pri"), "r+") as f:
            lines = f.readlines()
            f.seek(0)
            f.truncate()
            for line in lines:
                if line.startswith("QT_EDITION ="):
                    line = "QT_EDITION = OpenSource\n"
                if line.startswith("QT_LICHECK ="):
                    line = "QT_LICHECK =\n"
                f.write(line)

    def patch_target_qt_conf(self, base_dir, qt_version, arch_dir, os_name):
        target_qt_conf = self.prefix / "bin" / "target_qt.conf"
        old_targetprefix = f'Prefix={unpatched_path(os_name, "target")}'
        new_hostprefix = f"HostPrefix=../../{default_desktop_arch_dir(os_name, qt_version)}"
        new_targetprefix = "Prefix={}".format(str(pathlib.Path(base_dir).joinpath(qt_version, arch_dir, "target")))
        new_hostdata = "HostData=../{}".format(arch_dir)
        self._patch_textfile(target_qt_conf, old_targetprefix, new_targetprefix)
        self._patch_textfile(target_qt_conf, "HostPrefix=../../", new_hostprefix)
        self._patch_textfile(target_qt_conf, "HostData=target", new_hostdata)

    @classmethod
    def update(cls, target: TargetConfig, base_dir: str):
        """
        Make Qt configuration files, qt.conf and qtconfig.pri.
        And update pkgconfig and patch Qt5Core and qmake
        """
        logger = getLogger("aqt.updater")
        arch = target.arch
        version = Version(target.version)
        os_name = target.os_name
        version_dir = dir_for_version(version)
        if arch is None:
            arch_dir = ""
        elif arch.startswith("win64_mingw"):
            arch_dir = arch[6:] + "_64"
        elif arch.startswith("win32_mingw"):
            arch_dir = arch[6:] + "_32"
        elif arch.startswith("win"):
            m = re.match(r"win\d{2}_(msvc\d{4})_(winrt_x\d{2})", arch)
            if m:
                a, b = m.groups()
                arch_dir = b + "_" + a
            else:
                arch_dir = arch[6:]
        elif os_name == "mac" and arch == "clang_64":
            arch_dir = default_desktop_arch_dir(os_name, version)
        else:
            arch_dir = arch
        try:
            prefix = pathlib.Path(base_dir) / version_dir / arch_dir
            updater = Updater(prefix, logger)
            updater.set_license(base_dir, version_dir, arch_dir)
            if target.arch not in [
                "ios",
                "android",
                "wasm_32",
                "android_x86_64",
                "android_arm64_v8a",
                "android_x86",
                "android_armv7",
            ]:  # desktop version
                updater.make_qtconf(base_dir, version_dir, arch_dir)
                updater.patch_qmake()
                if target.os_name == "linux":
                    updater.patch_pkgconfig("/home/qt/work/install", target.os_name)
                    updater.patch_libtool("/home/qt/work/install/lib", target.os_name)
                elif target.os_name == "mac":
                    updater.patch_pkgconfig("/Users/qt/work/install", target.os_name)
                    updater.patch_libtool("/Users/qt/work/install/lib", target.os_name)
                elif target.os_name == "windows":
                    updater.make_qtenv2(base_dir, version_dir, arch_dir)
                if version < Version("5.14.0"):
                    updater.patch_qtcore(target)
            elif version in SimpleSpec(">=5.0,<6.0"):
                updater.patch_qmake()
            else:  # qt6 non-desktop
                updater.patch_qmake_script(base_dir, version_dir, target.os_name)
                updater.patch_target_qt_conf(base_dir, version_dir, arch_dir, target.os_name)
        except IOError as e:
            raise UpdaterError(f"Updater caused an IO error: {e}") from e

    @classmethod
    def patch_kde(cls, src_dir):
        logger = logging.getLogger("aqt")
        PATCH_URL_BASE = "https://raw.githubusercontent.com/miurahr/kde-qt-patch/main/patches/"
        for p in Settings.kde_patches:
            logger.info("Apply patch: " + p)
            patchfile = patch.fromurl(PATCH_URL_BASE + p)
            patchfile.apply(strip=True, root=os.path.join(src_dir, "qtbase"))

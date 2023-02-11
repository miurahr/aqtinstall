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
import re
import stat
import subprocess
from logging import getLogger
from pathlib import Path
from typing import Dict, List, Optional, Union

import patch

from aqt.archives import TargetConfig
from aqt.exceptions import UpdaterError
from aqt.helper import Settings
from aqt.metadata import ArchiveId, MetadataFactory, QtRepoProperty, SimpleSpec, Version

dir_for_version = QtRepoProperty.dir_for_version


def unpatched_paths() -> List[str]:
    return [
        "/home/qt/work/install/",
        "/Users/qt/work/install/",
        "\\home\\qt\\work\\install\\",
        "\\Users\\qt\\work\\install\\",
    ]


class Updater:
    def __init__(self, prefix: Path, logger):
        self.logger = logger
        self.prefix = prefix
        self.qmake_path: Optional[Path] = None
        self.qconfigs: Dict[str, str] = {}

    def _patch_binfile(self, file: Path, key: bytes, newpath: bytes):
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

    def _append_string(self, file: Path, val: str):
        """Append string to file"""
        st = file.stat()
        data = file.read_text("UTF-8")
        data += val
        file.write_text(data, "UTF-8")
        os.chmod(str(file), st.st_mode)

    def _patch_textfile(self, file: Path, old: Union[str, re.Pattern], new: str, *, is_executable: bool = False):
        st = file.stat()
        file_mode = st.st_mode | (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH if is_executable else 0)
        data = file.read_text("UTF-8")
        if isinstance(old, re.Pattern):
            data = old.sub(new, data)
        else:
            data = data.replace(old, new)
        file.write_text(data, "UTF-8")
        os.chmod(str(file), file_mode)

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
            if self.qmake_path is None:
                return
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

    def patch_qmake_script(self, base_dir, qt_version: str, os_name: str, desktop_arch_dir: str):
        sep = "\\" if os_name == "windows" else "/"
        patched = sep.join([base_dir, qt_version, desktop_arch_dir, "bin"])
        qmake_path = self.prefix / "bin" / ("qmake.bat" if os_name == "windows" else "qmake")
        self.logger.info(f"Patching {qmake_path}")
        for unpatched in unpatched_paths():
            self._patch_textfile(qmake_path, f"{unpatched}bin", patched, is_executable=True)

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

    def set_license(self, base_dir: str, qt_version: str, arch_dir: str):
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

    def patch_target_qt_conf(self, base_dir: str, qt_version: str, arch_dir: str, os_name: str, desktop_arch_dir: str):
        target_qt_conf = self.prefix / "bin" / "target_qt.conf"
        new_hostprefix = f"HostPrefix=../../{desktop_arch_dir}"
        new_targetprefix = "Prefix={}".format(str(Path(base_dir).joinpath(qt_version, arch_dir, "target")))
        new_hostdata = "HostData=../{}".format(arch_dir)
        new_host_lib_execs = "./bin" if os_name == "windows" else "./libexec"
        old_host_lib_execs = re.compile(r"^HostLibraryExecutables=[^\n]*$", flags=re.MULTILINE)

        self._patch_textfile(target_qt_conf, old_host_lib_execs, f"HostLibraryExecutables={new_host_lib_execs}")
        for unpatched in unpatched_paths():
            self._patch_textfile(target_qt_conf, f"Prefix={unpatched}target", new_targetprefix)
        self._patch_textfile(target_qt_conf, "HostPrefix=../../", new_hostprefix)
        self._patch_textfile(target_qt_conf, "HostData=target", new_hostdata)

    def patch_qdevice_file(self, base_dir: str, qt_version: str, arch_dir: str, os_name: str):
        """Qt 6.4.1+ specific, but it should not hurt anything if `mkspecs/qdevice.pri` does not exist"""

        qdevice = Path(base_dir) / qt_version / arch_dir / "mkspecs/qdevice.pri"
        if not qdevice.exists():
            return

        old_line = re.compile(r"^DEFAULT_ANDROID_NDK_HOST =[^\n]*$", flags=re.MULTILINE)
        new_line = f"DEFAULT_ANDROID_NDK_HOST = {'darwin' if os_name == 'mac' else os_name}-x86_64"
        self._patch_textfile(qdevice, old_line, new_line)

    @classmethod
    def update(cls, target: TargetConfig, base_path: Path, installed_desktop_arch_dir: Optional[str]):
        """
        Make Qt configuration files, qt.conf and qtconfig.pri.
        And update pkgconfig and patch Qt5Core and qmake

        :param installed_desktop_arch_dir:  This is the path to a desktop Qt  installation, like `Qt/6.3.0/mingw_win64`.
                                            This may or may not contain an actual desktop Qt installation.
                                            If it does not, the Updater will patch files in a mobile Qt installation
                                            that point to this directory, and this installation will be non-functional
                                            until the user installs a desktop Qt in this directory.
        """
        logger = getLogger("aqt.updater")
        arch = target.arch
        version = Version(target.version)
        os_name = target.os_name
        version_dir = dir_for_version(version)
        arch_dir = QtRepoProperty.get_arch_dir_name(os_name, arch, version)
        base_dir = str(base_path)
        try:
            prefix = base_path / version_dir / arch_dir
            updater = Updater(prefix, logger)
            updater.set_license(base_dir, version_dir, arch_dir)
            if target.arch not in [
                "ios",
                "android",
                "wasm_32",
                "wasm_singlethread",
                "wasm_multithread",
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
            else:  # qt6 mobile or wasm
                if installed_desktop_arch_dir is not None:
                    desktop_arch_dir = installed_desktop_arch_dir
                else:
                    # Use MetadataFactory to check what the default architecture should be
                    meta = MetadataFactory(ArchiveId("qt", os_name, "desktop"))
                    desktop_arch_dir = meta.fetch_default_desktop_arch(version)

                updater.patch_qmake_script(base_dir, version_dir, target.os_name, desktop_arch_dir)
                updater.patch_target_qt_conf(base_dir, version_dir, arch_dir, target.os_name, desktop_arch_dir)
                updater.patch_qdevice_file(base_dir, version_dir, arch_dir, target.os_name)
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

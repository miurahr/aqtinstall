#!/usr/bin/env python
#
# Copyright (C) 2021 Hiroshi Miura <miurahr@linux.com>
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
#
# --------------------------------------------------------------------------------
# Original license of component
# MIT License
#
# Copyright (c) 2019 Adrien Gavignet
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# --------------------------------------------------------------------------------
import binascii
import hashlib
import os
import re
import shutil
import stat
import subprocess
from logging import getLogger

from semantic_version import Version, SimpleSpec

from aqt.helper import BLOCKSIZE, downloadBinaryFile, getUrl

WORKING_DIR = os.getcwd()
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
DEFAULT_INSTALL_SCRIPT = os.path.join(CURRENT_DIR, "install-qt.qs")


class DeployCuteCI:
    """
    Class in charge of Qt deployment
    """

    def __init__(self, version_str, os_name, arch, base, timeout, debug=False):
        self.logger = getLogger("aqt")
        self.version = Version(version_str)
        self.timeout = timeout
        self.os_name = os_name
        self.debug = debug
        if os_name == "linux":
            tag = "x64"
            ext = "run"
        elif os_name == "mac":
            tag = "x64"
            ext = "dmg"
        elif arch == "win64_msvc2017_64":
            tag = "x86-msvc2017_64"
            ext = "exe"
        elif arch == "win32_msvc2017":
            tag = "x86-msvc2017"
            ext = "exe"
        elif arch == "win64_msvc2015_64":
            tag = "x86-msvc2015_64"
            ext = "exe"
        elif arch == "win32_msvc2015":
            tag = "x86-msvc2015"
            ext = "exe"
        elif arch == "win32_mingw49":
            tag = "x86-mingw492"
            ext = "exe"
        elif arch == "win32_mingw530":
            tag = "x86-mingw530"
            ext = "exe"
        if self.version in SimpleSpec(">5.1,<5.9"):
            folder = "new_archive"
        else:
            folder = "archive"
        self.installer_url = "{0}/{1}/qt/{2}.{3}/{4}/qt-opensource-{5}-{6}-{7}.{8}".format(
            base, folder, self.version.major, self.version.minor, version_str, os_name, tag, version_str, ext
        )
        self.md5sums_url = (
            self.installer_url[: self.installer_url.rfind("/")] + "/" + "md5sums.txt"
        )

    def _get_version(self, path):
        # qt-opensource-windows-x86-5.12.2.exe
        # qt-opensource-mac-x64-5.12.2.dmg
        # qt-opensource-linux-x64-5.12.2.run
        basename = os.path.basename(path)
        res = re.search(r"-(\d+\.\d+.\d+)\.", basename)
        if res is None:
            raise Exception(
                "Cannot get version from `{}` filename (expects name like: `qt-opensource-linux-x64-5.12.2.run`)".format(
                    basename
                )
            )
        res.group(1)
        return res.group(1)

    def get_archive_name(self):
        return self.installer_url[self.installer_url.rfind("/") + 1 :]

    def _get_md5(self, archive, timeout):
        expected_md5 = None
        r_text = getUrl(self.md5sums_url, timeout)
        for line in r_text.split("\n"):
            rec = line.split(" ")
            if archive in rec:
                expected_md5 = rec[0]
        return binascii.unhexlify(expected_md5)

    def check_archive(self):
        archive = self.get_archive_name()
        if os.path.exists(archive):
            timeout = (3.5, 3.5)
            expected_md5 = self._get_md5(archive, timeout)
            if expected_md5 is not None:
                checksum = hashlib.md5()
                with open(archive, "rb") as f:
                    data = f.read(BLOCKSIZE)
                    while len(data) > 0:
                        checksum.update(data)
                        data = f.read(BLOCKSIZE)
                if (
                    checksum.hexdigest() == expected_md5
                    and os.stat(archive).st_mode & stat.S_IEXEC
                ):
                    return True
        return False

    def download_installer(self, response_timeout: int = 30):
        """
        Download Qt if possible, also verify checksums.

        :raises Exception: in case of failure
        """
        url = self.installer_url
        archive = self.get_archive_name()
        timeout = (3.5, response_timeout)
        self.logger.info("Download Qt %s", url)
        #
        expected_md5 = self._get_md5(archive, timeout)
        downloadBinaryFile(url, archive, "md5", expected_md5, timeout)
        os.chmod(archive, os.stat(archive).st_mode | stat.S_IEXEC)
        return archive

    def _run_dmg(self, dmg, args, env):
        try:
            subprocess.run(["hdiutil", "attach", dmg], check=True)
        except subprocess.CalledProcessError as cpe:
            if cpe.stdout is not None:
                self.logger.error(cpe.stdout)
            if cpe.stderr is not None:
                self.logger.error(cpe.stderr)
            raise cpe
        #
        attach_path = "/Volumes/" + os.path.splitext(os.path.basename(dmg))[0]
        self._run_cmd(attach_path + "/Qt Installer.app", args, env)  # FIXME
        #
        try:
            subprocess.run(["hdiutil", "detach", attach_path], check=True)
        except subprocess.CalledProcessError as cpe:
            if cpe.stdout is not None:
                self.logger.error(cpe.stdout)
            if cpe.stderr is not None:
                self.logger.error(cpe.stderr)
            raise cpe

    def _run_cmd(self, cmd, args, env):
        self.logger.info("Running installer %s %s", cmd, args)
        try:
            subprocess.run(cmd, timeout=self.timeout, env=env, check=True)
        except subprocess.CalledProcessError as cpe:
            if cpe.returncode == 3:
                pass
            self.logger.error("Installer error: %d" % cpe.returncode)
            if cpe.stdout is not None:
                self.logger.error(cpe.stdout)
            if cpe.stderr is not None:
                self.logger.error(cpe.stderr)
            raise cpe
        except subprocess.TimeoutExpired as te:
            self.logger.error("Installer timeout expired: {}".format(self.timeout))
            if te.stdout is not None:
                self.logger.error(te.stdout)
            if te.stderr is not None:
                self.logger.error(te.stderr)
            raise te

    def run_installer(self, archive, packages, destdir, keep_tools):
        """
        Install Qt.

        :param list: packages to install
        :param str destdir: install directory
        :param keep_tools: if True, keep Qt Tools after installation
        :raises Exception: in case of failure
        """
        env = os.environ.copy()
        env["PACKAGES"] = ",".join(packages)
        env["DESTDIR"] = destdir
        env["QT_QPA_PLATFORM"] = "offscreen"
        install_script = os.path.join(CURRENT_DIR, "install-qt.qs")
        installer_path = os.path.join(WORKING_DIR, archive)
        args = [installer_path, "--script", install_script]
        if self.debug:
            args.extend(["--verbose"])
        else:
            if self.os_name == "linux":
                if self.version in SimpleSpec(">5.3,<5.7"):
                    args.extend(["--platform", "minimal"])
                else:
                    args.extend(["--silent"])
            else:
                if self.version in SimpleSpec(">5.3,<5.6"):
                    args.extend(["--platform", "minimal"])
                else:
                    args.extend(["--silent"])
        if self.os_name == "mac":
            self._run_dmg(installer_path, args, env)
        else:
            self._run_cmd(installer_path, args, env)
        if not keep_tools:
            self.logger.info("Cleaning destdir")
            files = os.listdir(destdir)
            for name in files:
                fullpath = os.path.join(destdir, name)
                if re.match(r"\d+\.\d+.\d+", name):
                    # Qt stands in X.Y.Z dir, skip it
                    self.logger.info("Keep %s", fullpath)
                    continue
                if os.path.isdir(fullpath):
                    shutil.rmtree(fullpath)
                else:
                    os.remove(fullpath)
                self.logger.info("Remove %s", fullpath)

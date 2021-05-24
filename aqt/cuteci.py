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

import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
from logging import getLogger

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from aqt.exceptions import ArchiveDownloadError
from aqt.helper import altlink, downloadBinaryFile, getUrl

WORKING_DIR = os.getcwd()
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
DEFAULT_INSTALL_SCRIPT = os.path.join(CURRENT_DIR, "install-qt.qs")
BLOCKSIZE = 1048576


class DeployCuteCI:
    """
    Class in charge of Qt deployment
    """

    def __init__(self, version, os_name, base, timeout):
        self.major_minor = version[: version.rfind(".")]
        self.timeout = timeout
        if os_name == "linux":
            arch = "x64"
            ext = "run"
        elif os_name == "mac":
            arch = "x64"
            ext = "dmg"
        else:
            arch = "x86"
            ext = "exe"
        if self.major_minor in [
            "5.11",
            "5.10",
            "5.8",
            "5.7",
            "5.6",
            "5.5",
            "5.4",
            "5.3",
            "5.2",
        ]:
            folder = "new_archive"
        else:
            folder = "archive"
        self.installer_url = "{0}/{1}/qt/{2}/{3}/qt-opensource-{4}-{5}-{6}.{7}".format(
            base, folder, self.major_minor, version, os_name, arch, version, ext
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
        r_text = getUrl(self.md5sums_url, timeout, self.logger)
        for line in r_text.split("\n"):
            rec = line.split(" ")
            if archive in rec:
                expected_md5 = rec[0]
        return expected_md5

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
        logger = getLogger("aqt")
        url = self.installer_url
        archive = self.get_archive_name()
        timeout = (3.5, response_timeout)
        logger.info("Download Qt %s", url)
        #
        expected_md5 = self._get_md5(archive, timeout)
        downloadBinaryFile(url, archive, "md5", expected_md5, timeout, logger)
        with requests.Session() as session:
            retry = Retry(connect=5, backoff_factor=0.5)
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            try:
                r = session.get(
                    url, allow_redirects=False, stream=True, timeout=timeout
                )
                if r.status_code == 302:
                    newurl = altlink(r.url, r.headers["Location"], logger=logger)
                    logger.info("Redirected URL: {}".format(newurl))
                    r = session.get(newurl, stream=True, timeout=timeout)
            except requests.exceptions.ConnectionError as e:
                logger.error("Connection error: %s" % e.args)
                raise e
            except requests.exceptions.Timeout as e:
                logger.error("Connection timeout: %s" % e.args)
                raise e
            else:
                checksum = hashlib.md5()
                try:
                    with open(archive, "wb") as fd:
                        for chunk in r.iter_content(chunk_size=8196):
                            fd.write(chunk)
                            checksum.update(chunk)
                    if expected_md5 is not None:
                        if checksum.hexdigest() != expected_md5:
                            raise ArchiveDownloadError(
                                "Download file is corrupted! Check sum error."
                            )
                except Exception as e:
                    exc = sys.exc_info()
                    logger.error("Download error: %s" % exc[1])
                    raise e
        os.chmod(archive, os.stat(archive).st_mode | stat.S_IEXEC)
        return archive

    def run_installer(self, archive, packages, destdir, keep_tools):
        """
        Install Qt.

        :param list: packages to install
        :param str destdir: install directory
        :param keep_tools: if True, keep Qt Tools after installation
        :param bool verbose: enable verbosity
        :raises Exception: in case of failure
        """
        logger = getLogger("aqt")
        env = os.environ.copy()
        env["PACKAGES"] = ",".join(packages)
        env["DESTDIR"] = destdir
        install_script = os.path.join(CURRENT_DIR, "install-qt.qs")
        installer_path = os.path.join(WORKING_DIR, archive)
        cmd = [installer_path, "--script", install_script, "--verbose"]
        if self.major_minor in ["5.11", "5.10"]:
            cmd.extend(["--platform", "minimal"])
        logger.info("Running installer %s", cmd)
        try:
            subprocess.run(cmd, timeout=self.timeout, env=env, check=True)
        except subprocess.CalledProcessError as cpe:
            if cpe.returncode == 3:
                pass
            logger.error("Installer error: %d" % cpe.returncode)
            if cpe.stdout is not None:
                logger.error(cpe.stdout)
            if cpe.stderr is not None:
                logger.error(cpe.stderr)
            raise cpe
        except subprocess.TimeoutExpired as te:
            logger.error("Installer timeout expired: {}" % self.timeout)
            if te.stdout is not None:
                logger.error(te.stdout)
            if te.stderr is not None:
                logger.error(te.stderr)
            raise te
        if not keep_tools:
            logger.info("Cleaning destdir")
            files = os.listdir(destdir)
            for name in files:
                fullpath = os.path.join(destdir, name)
                if re.match(r"\d+\.\d+.\d+", name):
                    # Qt stands in X.Y.Z dir, skip it
                    logger.info("Keep %s", fullpath)
                    continue
                if os.path.isdir(fullpath):
                    shutil.rmtree(fullpath)
                else:
                    os.remove(fullpath)
                logger.info("Remove %s", fullpath)

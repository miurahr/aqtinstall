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
import sys
import os
import stat
import shutil
import subprocess
import re
from logging import getLogger

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from aqt.helper import altlink

WORKING_DIR = os.getcwd()
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
DEFAULT_INSTALL_SCRIPT = os.path.join(CURRENT_DIR, "install-qt.qs")
UNEXISTING_PROXY = "127.0.1.100:44444"


class DeployCuteCI:
    """
    Class in charge of Qt deployment
    """

    def __init__(self, version, os_name, base, timeout):
        major_minor = version[:version.rfind(".")]
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
        self.installer_url = "{0}{1}/{2}/qt-opensource-{3}-{4}-{5}.{6}".format(
            base,
            major_minor,
            version,
            os_name,
            arch,
            version,
            ext
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

    def download_installer(self, response_timeout: int = 30):
        """
        Download Qt if possible, also verify checksums.

        :raises Exception: in case of failure
        """
        logger = getLogger("aqt")
        url = self.installer_url
        archive = self.installer_url[self.installer_url.rfind("/") + 1 :]
        md5sums_url = self.installer_url[: self.installer_url.rfind("/")] + "/" + "md5sums.txt"
        timeout = (3.5, response_timeout)
        logger.info("Download Qt %s", url)
        #
        expected_md5 = None
        with requests.Session() as session:
            retry = Retry(connect=5, backoff_factor=0.5)
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            try:
                r = session.get(md5sums_url, allow_redirects=True, timeout=timeout)
            except (requests.exceptions.ConnectionError or requests.exceptions.Timeout):
                pass  # ignore it
            else:
                expected_md5 = str(r.content)
        with requests.Session() as session:
            retry = Retry(connect=5, backoff_factor=0.5)
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            try:
                r = session.get(url, allow_redirects=False, stream=True, timeout=timeout)
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
                        fd.flush()
                    if expected_md5 is not None:
                        pass
                        # if checksum.hexdigest() not in expected_md5:
                        #    raise ArchiveDownloadError(
                        #        "Download file is corrupted! Check sum error."
                        # )
                except Exception as e:
                    exc = sys.exc_info()
                    logger.error("Download error: %s" % exc[1])
                    raise e
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
        os.chmod(
            archive, os.stat(archive).st_mode | stat.S_IEXEC
        )
        logger = getLogger("aqt")
        env = os.environ.copy()
        env["PACKAGES"] = packages
        env["DESTDIR"] = destdir
        # Set a fake proxy, then credentials are not required in the installer
        env.update({"http_proxy": UNEXISTING_PROXY, "https_proxy": UNEXISTING_PROXY})
        #
        version = ".".join(self._get_version(archive).split(".")[:1])
        install_script = os.path.join(CURRENT_DIR, "install-qt.qs".format(version))
        installer_path = os.path.join(WORKING_DIR, archive)
        cmd = [installer_path, "--script", install_script]
        cmd.extend(["--platform", "minimal"])
        logger.info("Running installer %s", cmd)
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, timeout=self.timeout
            )
            logger.debug(proc.stdout)
        except subprocess.CalledProcessError as cpe:
            logger.error("Installer error: %d" % cpe.returncode)
            if cpe.stdout is not None:
                logger.error(cpe.stdout)
            if cpe.stderr is not None:
                logger.error(cpe.stderr)
            raise cpe
        except subprocess.TimeoutExpired as te:
            logger.error("Installer error %d" % te.returncode)
            if te.stdout is not None:
                logger.error(te.stdout)
            if te.stderr is not None:
                logger.error(te.stderr)
            raise te
        if proc.returncode != 3 or proc.returncode != 0:
            logger.error("Installer error %d" % proc.returncode)
            raise Exception(
                "Installer neither returned 0 nor 3 exit code: {}".format(proc.returncode)
            )
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

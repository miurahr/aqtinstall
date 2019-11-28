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

import asyncio
import os
from logging import getLogger

import aiohttp

import aiofiles
import py7zr
from aqt.settings import Settings


class BadPackageFile(Exception):
    pass


class QtInstaller:
    """
    Installer class to download packages and extract it.
    """

    def __init__(self, qt_archives, logging=None):
        self.qt_archives = qt_archives
        if logging:
            self.logger = logging
        else:
            self.logger = getLogger('aqt')
        self.settings = Settings()

    async def retrieve_archive(self, archive, session):
        package = archive.archive
        url = archive.url
        self.logger.info("Downloading {}...".format(url))
        async with session.get(url) as resp:
            if resp.status != 200:
                return False
            async with aiofiles.open(package, 'wb') as fd:
                while True:
                    chunk = await resp.content.read(4096)
                    if not chunk:
                        await fd.flush()
                        break
                    await fd.write(chunk)
            self.logger.debug("Finished downloading {}".format(url))
            return True

    def extract_archive(self, archive, path):
        package = archive.archive
        self.logger.info("Extracing {}...".format(package))
        try:
            sevenzip = py7zr.SevenZipFile(package)
            sevenzip.extractall(path=path)
            sevenzip.close()
            os.unlink(package)
        except Exception:
            return False
        self.logger.debug("Finished extraction {}".format(package))
        return True

    async def install(self, target_dir=None):
        if target_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = target_dir
        archives = self.qt_archives.get_archives()
        tasks = []
        self.logger.debug("Start aiohttp session")
        semaphore = asyncio.Semaphore(self.settings.concurrency)
        timeout = aiohttp.ClientTimeout(total=self.settings.total_timeout)
        conn = aiohttp.TCPConnector(limit_per_host=self.settings.limit_per_host, ssl=True)
        async with semaphore:
            async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
                for archive in archives:
                    task = asyncio.ensure_future(self.retrieve_archive(archive, session))
                    tasks.append(task)
                self.logger.debug("Await retrieve_archive gathering")
                rets = await asyncio.gather(*tasks)
        self.logger.debug("--------------Start extractions")
        for archive in archives:
            self.extract_archive(archive, base_dir)
        return rets

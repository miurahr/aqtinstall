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
from aqt.helper import aio7zr, aio_is_7zip, aiounlink
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

    async def retrieve_archive(self, package, session, path=None):
        archive = package.archive
        url = package.url
        print("-Downloading {}...".format(url))
        async with session.get(url) as resp:
            async with aiofiles.open(archive, 'wb') as fd:
                while True:
                    chunk = await resp.content.read(4096)
                    if not chunk:
                        break
                    await fd.write(chunk)
        print("-Extracting {}...".format(archive))
        if not aio_is_7zip(archive):
            raise BadPackageFile
        await aio7zr(archive, path)
        await aiounlink(archive)
        return True

    async def _bound_retrieve_archive(self, semaphore, archive, session, path):
        async with semaphore:
            return await self.retrieve_archive(archive, session, path)

    async def install(self, target_dir=None):
        if target_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = target_dir
        archives = self.qt_archives.get_archives()
        tasks = []
        semaphore = asyncio.Semaphore(self.settings.concurrency)
        timeout = aiohttp.ClientTimeout(total=self.settings.total_timeout)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit_per_host=self.settings.limit_per_host,
                                                                        ssl=True),
                                         timeout=timeout) as session:
            for archive in archives:
                task = asyncio.ensure_future(self._bound_retrieve_archive(semaphore, archive, session, path=base_dir))
                tasks.append(task)
            rets = await asyncio.gather(*tasks)
        return rets

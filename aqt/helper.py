import asyncio
import functools
import os
import xml.etree.ElementTree as ElementTree
from logging import getLogger

import aiohttp

import py7zr
from aqt.settings import Settings


def async_wrap(func):
    @functools.wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        partial_func = functools.partial(func, *args, **kwargs)
        return loop.run_in_executor(executor, partial_func)

    return run


aiounlink = async_wrap(os.unlink)


async def aio7zr(archive, path):
    logger = getLogger('aqt')
    logger.debug("Start uncompress 7zip archive {}".format(archive))
    loop = asyncio.get_event_loop()
    sevenzip = py7zr.SevenZipFile(archive)
    partial_py7zr = functools.partial(sevenzip.extractall, path=path)
    loop.run_in_executor(None, partial_py7zr)
    loop.run_in_executor(None, sevenzip.close)
    logger.debug("Finish uncompress 7zip archive {}".format(archive))


async def altlink(url):
    settings = Settings()
    blacklist = settings.blacklist
    mirrors = {}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=True)) as session:
        async with session.get(url + '.meta4') as resp:
            assert resp.status == 200
            mirror_xml = ElementTree.fromstring(await resp.text())
            for f in mirror_xml.iter("{urn:ietf:params:xml:ns:metalink}file"):
                for u in f.iter("{urn:ietf:params:xml:ns:metalink}url"):
                    pri = u.attrib['priority']
                    mirrors[pri] = u.text
    logger = getLogger('aqt')
    if len(mirrors) == 0:
        # no alternative
        return url
    if blacklist is not None:
        for ind in range(len(mirrors)):
            mirror = mirrors[str(ind + 1)]
            black = False
            for b in blacklist:
                if mirror.startswith(b):
                    black = True
                    continue
            if black:
                continue
            logger.debug("select mirror: {}".format(mirror))
            return mirror
    else:
        for ind in range(len(mirrors)):
            mirror = mirrors[str(ind + 1)]
            logger.debug("select mirror: {}".format(mirror))
            return mirror

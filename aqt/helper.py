import asyncio
import functools
import os
import xml.etree.ElementTree as ElementTree

import aiohttp

import py7zr


def async_wrap(func):
    @asyncio.coroutine
    @functools.wraps(func)
    def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        partial_func = functools.partial(func, *args, **kwargs)
        return loop.run_in_executor(executor, partial_func)

    return run


aiounlink = async_wrap(os.unlink)


@asyncio.coroutine
def aio7zr(archive, path):
    loop = asyncio.get_event_loop()
    sevenzip = py7zr.SevenZipFile(archive)
    partial_py7zr = functools.partial(sevenzip.extractall, path=path)
    loop.run_in_executor(None, partial_py7zr)


@asyncio.coroutine
def aio_is_7zip(archive):
    loop = asyncio.get_event_loop()
    partial = functools.partial(py7zr.is_7zfile, archive)
    result = loop.run_in_executor(None, partial)
    return result


async def altlink(url, blacklist=None):
    mirrors = {}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=True)) as session:
        async with session.get(url + '.meta4') as resp:
            assert resp.status == 200
            mirror_xml = ElementTree.fromstring(await resp.text())
            for f in mirror_xml.iter("{urn:ietf:params:xml:ns:metalink}file"):
                for u in f.iter("{urn:ietf:params:xml:ns:metalink}url"):
                    pri = u.attrib['priority']
                    mirrors[pri] = u.text

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
            return mirror
    else:
        for ind in range(len(mirrors)):
            mirror = mirrors[str(ind + 1)]
            return mirror

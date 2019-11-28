import xml.etree.ElementTree as ElementTree
from logging import getLogger

import aiohttp

from aqt.settings import Settings


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

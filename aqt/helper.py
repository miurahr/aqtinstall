import xml.etree.ElementTree as ElementTree

import requests

from aqt.settings import Settings


def altlink(url, priority=None):
    '''Download .meta4 metalink version4 xml file and parse it.'''

    mirrors = {}
    url = url
    settings = Settings()
    blacklist = settings.blacklist
    try:
        m = requests.get(url + '.meta4')
    except requests.exceptions.ConnectionError:
        return
    else:
        mirror_xml = ElementTree.fromstring(m.text)
        for f in mirror_xml.iter("{urn:ietf:params:xml:ns:metalink}file"):
            for u in f.iter("{urn:ietf:params:xml:ns:metalink}url"):
                pri = u.attrib['priority']
                mirrors[pri] = u.text

    if len(mirrors) == 0:
        # no alternative
        return url
    if priority is None:
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
    else:
        return mirrors[str(priority)]

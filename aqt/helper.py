import logging
import sys
import xml.etree.ElementTree as ElementTree
from typing import List, Optional

import requests

from aqt.settings import Settings


def _get_meta(url: str):
    return requests.get(url + '.meta4')


def _check_content_type(ct: str) -> bool:
    candidate = ['application/metalink4+xml', 'text/plain']
    return any(ct.startswith(t) for t in candidate)


def altlink(url: str, alt: str, logger=None):
    '''Blacklisting redirected(alt) location based on Settings.blacklist configuration.
     When found black url, then try download a url + .meta4 that is a metalink version4
     xml file, parse it and retrieve best alternative url.'''
    if logger is None:
        logger = logging.getLogger(__name__)
    blacklist = Settings().blacklist  # type: Optional[List[str]]
    if blacklist is None or not any(alt.startswith(b) for b in blacklist):
        return alt
    try:
        m = _get_meta(url)
    except requests.exceptions.ConnectionError:
        logger.error("Got connection error. Fall back to recovery plan...")
        return alt
    else:
        # Expected response->'application/metalink4+xml; charset=utf-8'
        if not _check_content_type(m.headers['content-type']):
            logger.error("Unexpected meta4 response;content-type: {}".format(m.headers['content-type']))
            return alt
        try:
            mirror_xml = ElementTree.fromstring(m.text)
            meta_urls = {}
            for f in mirror_xml.iter("{urn:ietf:params:xml:ns:metalink}file"):
                for u in f.iter("{urn:ietf:params:xml:ns:metalink}url"):
                    meta_urls[u.attrib['priority']] = u.text
            mirrors = [meta_urls[i] for i in sorted(meta_urls.keys(), key=lambda x: int(x))]
        except Exception:
            exc_info = sys.exc_info()
            logger.error("Unexpected meta4 file; parse error: {}".format(exc_info[1]))
            return alt
        else:
            # Return first priority item which is not blacklist in mirrors list,
            # if not found then return alt in default
            return next(filter(lambda mirror: not any(mirror.startswith(b) for b in blacklist), mirrors), alt)


def versiontuple(v: str):
    return tuple(map(int, (v.split("."))))

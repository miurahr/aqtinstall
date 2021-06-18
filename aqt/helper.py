#!/usr/bin/env python
#
# Copyright (C) 2019-2021 Hiroshi Miura <miurahr@linux.com>
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

import hashlib
import logging
import sys
import xml.etree.ElementTree as ElementTree
from typing import List, Optional
from urllib.parse import urlparse

import requests
import requests.adapters

import aqt.settings as Settings
from aqt.exceptions import ArchiveConnectionError, ArchiveDownloadError


def _get_meta(url: str):
    return requests.get(url + ".meta4")


def _check_content_type(ct: str) -> bool:
    candidate = ["application/metalink4+xml", "text/plain"]
    return any(ct.startswith(t) for t in candidate)


def getUrl(url: str, timeout, logger) -> str:
    with requests.Session() as session:
        adapter = requests.adapters.HTTPAdapter()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        try:
            r = requests.get(url, allow_redirects=False, timeout=timeout)
            if 300 < r.status_code < 309:
                logger.info(
                    "Asked to redirect({}) to: {}".format(
                        r.status_code, r.headers["Location"]
                    )
                )
                newurl = altlink(r.url, r.headers["Location"], logger=logger)
                logger.info("Redirected: {}".format(urlparse(newurl).hostname))
                r = session.get(newurl, stream=True, timeout=timeout)
        except (
            ConnectionResetError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ):
            raise ArchiveConnectionError()
        else:
            if r.status_code != 200:
                logger.error(
                    "Download error when access to {}\n"
                    "Server response code: {}, reason: {}".format(
                        url, r.status_code, r.reason
                    )
                )
                raise ArchiveDownloadError("Download error!")
        result = r.text
    return result


def downloadBinaryFile(url: str, out: str, hash_algo: str, exp: str, timeout, logger):
    with requests.Session() as session:
        adapter = requests.adapters.HTTPAdapter()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        try:
            r = session.get(url, allow_redirects=False, stream=True, timeout=timeout)
            if 300 < r.status_code < 309:
                logger.info(
                    "Asked to redirect({}) to: {}".format(
                        r.status_code, r.headers["Location"]
                    )
                )
                newurl = altlink(r.url, r.headers["Location"], logger=logger)
                logger.info("Redirected: {}".format(urlparse(newurl).hostname))
                r = session.get(newurl, stream=True, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection error: %s" % e.args)
            raise e
        except requests.exceptions.Timeout as e:
            logger.error("Connection timeout: %s" % e.args)
            raise e
        else:
            hash = hashlib.new(hash_algo)
            try:
                with open(out, "wb") as fd:
                    for chunk in r.iter_content(chunk_size=8196):
                        fd.write(chunk)
                        hash.update(chunk)
                    fd.flush()
                if exp is not None:
                    if hash.digest() != exp:
                        raise ArchiveDownloadError(
                            "Download file is corrupted! Detect checksum error.\nExpected {}, Actual {}".format(
                                exp, hash.digest()
                            )
                        )
            except Exception as e:
                exc = sys.exc_info()
                logger.error("Download error: %s" % exc[1])
                raise e


def altlink(url: str, alt: str, logger=None):
    """Blacklisting redirected(alt) location based on Settings.blacklist configuration.
    When found black url, then try download a url + .meta4 that is a metalink version4
    xml file, parse it and retrieve best alternative url."""
    if logger is None:
        logger = logging.getLogger(__name__)
    blacklist = Settings.blacklist()  # type: Optional[List[str]]
    if not any(alt.startswith(b) for b in blacklist):
        return alt
    try:
        m = _get_meta(url)
    except requests.exceptions.ConnectionError:
        logger.error("Got connection error. Fall back to recovery plan...")
        return alt
    else:
        # Expected response->'application/metalink4+xml; charset=utf-8'
        if not _check_content_type(m.headers["content-type"]):
            logger.error(
                "Unexpected meta4 response;content-type: {}".format(
                    m.headers["content-type"]
                )
            )
            return alt
        try:
            mirror_xml = ElementTree.fromstring(m.text)
            meta_urls = {}
            for f in mirror_xml.iter("{urn:ietf:params:xml:ns:metalink}file"):
                for u in f.iter("{urn:ietf:params:xml:ns:metalink}url"):
                    meta_urls[u.attrib["priority"]] = u.text
            mirrors = [
                meta_urls[i] for i in sorted(meta_urls.keys(), key=lambda x: int(x))
            ]
        except Exception:
            exc_info = sys.exc_info()
            logger.error("Unexpected meta4 file; parse error: {}".format(exc_info[1]))
            return alt
        else:
            # Return first priority item which is not blacklist in mirrors list,
            # if not found then return alt in default
            return next(
                filter(
                    lambda mirror: not any(mirror.startswith(b) for b in blacklist),
                    mirrors,
                ),
                alt,
            )

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

import requests
import xml.etree.ElementTree as ElementTree


def get(url, stream=False):
    r = requests.get(url, stream=stream, allow_redirects=False)
    if r.status_code == 302:
        # tsinghua.edu.cn is problematic and it prohibit service to specific geo location.
        # we will use another redirected location for that.
        newurl = r.headers['Location']
        blacklist = ['https://mirrors.tuna.tsinghua.edu.cn', 'http://mirrors.tuna.tsinghua.edu.cn']
        for b in blacklist:
            if newurl.startswith(b):
                mml = Metalink(url)
                newurl = mml.altlink(blacklist=blacklist)
                break
        print('**** newurl ***** {}'.format(newurl))
        r = requests.get(newurl, stream=stream)
    return r


class Metalink:
    '''Download .meta4 metalink version4 xml file and parse it.'''

    def __init__(self, url, candidate=None):
        self.mirrors = {}
        self.url = url
        self.candidate = candidate
        m = requests.get(url + '.meta4')
        mirror_xml = ElementTree.fromstring(m.text)
        for f in mirror_xml.iter("{urn:ietf:params:xml:ns:metalink}file"):
            for u in f.iter("{urn:ietf:params:xml:ns:metalink}url"):
                pri = u.attrib['priority']
                self.mirrors[pri] = u.text

    def altlink(self, priority=None, blacklist=None):
        if len(self.mirrors) == 0:
            # no alternative
            if self.candidate is not None:
                return self.candidate
            else:
                return self.url
        if priority is None:
            if blacklist is not None:
                for ind in range(len(self.mirrors)):
                    mirror = self.mirrors[str(ind + 1)]
                    black = False
                    for b in blacklist:
                        if mirror.startswith(b):
                            black = True
                            continue
                    if black:
                        continue
                    return mirror
            else:
                for ind in range(len(self.mirrors)):
                    mirror = self.mirrors[str(ind + 1)]
                    if mirror == self.candidate:
                        continue
                    return mirror
        else:
            return self.mirrors[str(priority)]

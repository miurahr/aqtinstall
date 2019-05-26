#!/usr/bin/env python
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
from . import exceptions


__all__ = ['get', 'exceptions']


def get(url, stream=False):
    r = requests.get(url, stream=stream, allow_redirects=False)
    if r.status_code == 302:
        # asked redirect

        if r.headers['Location'].startswith('http://mirrors.tuna.tsinghua.edu.cn'):
            # tsinghua.edu.cn is problematic and it prohibit service to specific geo location.
            # we will use another redirected location for that.
            # MIRRORLIST = 'https://download.qt.io/static/mirrorlist/'
            # r2 = requests.get(MIRRORLIST)
            newurl = r.headers['Location']  # fixme
        else:
            newurl = r.headers['Location']
        r = requests.get(newurl, stream=stream)
    return r

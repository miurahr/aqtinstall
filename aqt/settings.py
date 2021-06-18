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

import configparser
import json
import os
from typing import List


class MyConfigParser(configparser.ConfigParser):
    def getlist(self, section: str, option: str, fallback=[]) -> List[str]:
        value = self.get(section, option)
        try:
            result = list(filter(None, (x.strip() for x in value.splitlines())))
        except Exception:
            result = fallback
        return result

    def getlistint(self, section: str, option: str, fallback=[]):
        try:
            result = [int(x) for x in self.getlist(section, option)]
        except Exception:
            result = fallback
        return result


configurations = {}
combinations = {}


def load_settings(file=None):
    global configurations, combinations
    configurations = MyConfigParser()
    # load default config file
    with open(os.path.join(os.path.dirname(__file__), "settings.ini"), "r") as f:
        configurations.read_file(f)
    # load custom file
    if file is not None:
        if isinstance(file, str):
            result = configurations.read(file)
            if len(result) == 0:
                raise IOError("Fails to load specified config file {}".format(file))
        else:
            # passed through command line argparse.FileType("r")
            configurations.read_file(file)
            file.close()
    # load combinations
    with open(
        os.path.join(os.path.dirname(__file__), "combinations.json"),
        "r",
    ) as j:
        combinations = json.load(j)[0]


def qt_combinations():
    return combinations["qt"]


def tools_combinations():
    return combinations["tools"]


def available_versions():
    return combinations["versions"]


def available_offline_installer_version():
    res = combinations["new_archive"]
    res.extend(combinations["versions"])
    return res


def available_modules(qt_version):
    """Known module names

    :returns: dictionary of qt_version and module names
    :rtype: List[str]
    """
    modules = combinations["modules"]
    versions = qt_version.split(".")
    version = "{}.{}".format(versions[0], versions[1])
    result = None
    for record in modules:
        if record["qt_version"] == version:
            result = record["modules"]
    return result


def concurrency():
    """concurrency configuration.

    :return: concurrency
    :rtype: int
    """
    return configurations.getint("aqt", "concurrency", fallback=4)


def blacklist():
    """list of sites in a blacklist

    :returns: list of site URLs(scheme and host part)
    :rtype: List[str]
    """
    return configurations.getlist("mirrors", "blacklist", fallback=[])


def baseurl():
    return configurations.get("aqt", "baseurl", fallback="https://download.qt.io")


def connection_timeout():
    return configurations.getfloat("aqt", "connection_timeout", fallback=3.5)


def response_timeout():
    return configurations.getfloat("aqt", "response_timeout", fallback=3.5)


def fallbacks():
    return configurations.getlist("mirrors", "fallbacks", fallback=[])


def zipcmd():
    return configurations.get("aqt", "7zcmd", fallback="7z")

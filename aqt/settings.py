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


class Settings:

    def __init__(self):
        self.configurations = MyConfigParser()
        # load default config file
        with open(os.path.join(os.path.dirname(__file__), "settings.ini"), "r") as f:
            self.configurations.read_file(f)
        # load combinations
        with open(
            os.path.join(os.path.dirname(__file__), "combinations.json"),
            "r",
        ) as j:
            self.combinations = json.load(j)[0]

    def load_settings(self, file):
        # load custom file
        if file is not None:
            if isinstance(file, str):
                result = self.configurations.read(file)
                if len(result) == 0:
                    raise IOError("Fails to load specified config file {}".format(file))
            else:
                # passed through command line argparse.FileType("r")
                self.configurations.read_file(file)
                file.close()

    @property
    def qt_combinations(self):
        return self.combinations["qt"]

    @property
    def tools_combinations(self):
        return self.combinations["tools"]

    @property
    def available_versions(self):
        return self.combinations["versions"]

    @property
    def available_offline_installer_version(self):
        res = self.combinations["new_archive"]
        res.extend(self.combinations["versions"])
        return res

    def available_modules(self, qt_version):
        """Known module names

        :returns: dictionary of qt_version and module names
        :rtype: List[str]
        """
        modules = self.combinations["modules"]
        versions = qt_version.split(".")
        version = "{}.{}".format(versions[0], versions[1])
        result = None
        for record in modules:
            if record["qt_version"] == version:
                result = record["modules"]
        return result

    @property
    def concurrency(self):
        """concurrency configuration.

        :return: concurrency
        :rtype: int
        """
        return self.configurations.getint("aqt", "concurrency", fallback=4)

    @property
    def blacklist(self):
        """list of sites in a blacklist

        :returns: list of site URLs(scheme and host part)
        :rtype: List[str]
        """
        return self.configurations.getlist("mirrors", "blacklist", fallback=[])

    @property
    def baseurl(self):
        return self.configurations.get("aqt", "baseurl", fallback="https://download.qt.io")

    @property
    def connection_timeout(self):
        return self.configurations.getfloat("aqt", "connection_timeout", fallback=3.5)

    @property
    def response_timeout(self):
        return self.configurations.getfloat("aqt", "response_timeout", fallback=3.5)

    @property
    def fallbacks(self):
        return self.configurations.getlist("mirrors", "fallbacks", fallback=[])

    @property
    def zipcmd(self):
        return self.configurations.get("aqt", "7zcmd", fallback="7z")


Settings = Settings()

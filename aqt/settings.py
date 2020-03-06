#!/usr/bin/env python3
#
# Copyright (C) 2018 Linus Jahn <lnj@kaidan.im>
# Copyright (C) 2019-2020 Hiroshi Miura <miurahr@linux.com>
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

import ast
import configparser
import json
import os
import threading


class Settings(object):
    """Class to hold configuration and settings.
    Actual values are stored in 'settings.ini' file.
    It also holds a combinations database.
    """
    # this class is Borg/Singleton
    _shared_state = {
        '_config': None,
        '_combinations': None,
        '_lock': threading.Lock()
    }

    def __init__(self, config=None):
        self.__dict__ = self._shared_state
        if self._config is None:
            with self._lock:
                if self._config is None:
                    if config is None:
                        self.inifile = os.path.join(os.path.dirname(__file__), 'settings.ini')
                    else:
                        self.inifile = config
                    self._config = self.configParse(self.inifile)
                    with open(os.path.join(os.path.dirname(__file__), 'combinations.json'), 'r') as j:
                        self._combinations = json.load(j)[0]

    def configParse(self, file_path):
        if not os.path.exists(file_path):
            raise IOError(file_path)
        config = configparser.ConfigParser()
        config.read(file_path)
        return config

    @property
    def qt_combinations(self):
        return self._combinations['qt']

    @property
    def tools_combinations(self):
        return self._combinations['tools']

    @property
    def available_versions(self):
        return self._combinations['versions']

    def available_modules(self, qt_version):
        """Known module names

        :returns: dictionary of qt_version and module names
        :rtype: List[str]
        """
        modules = self._combinations['modules']
        versions = qt_version.split('.')
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
        return self._config.getint("aqt", "concurrency")

    @property
    def blacklist(self):
        """list of sites in a blacklist

        :returns: list of site URLs(scheme and host part)
        :rtype: List[str]
        """
        return ast.literal_eval(self._config.get("mirrors", "blacklist"))

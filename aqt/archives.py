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

import xml.etree.ElementTree as ElementTree
from logging import getLogger

import requests


class QtPackage:
    name = ""
    url = ""
    archive = ""
    desc = ""
    mirror = None

    def __init__(self, name, archive_url, archive, package_desc, has_mirror=False):
        self.name = name
        self.url = archive_url
        self.archive = archive
        self.desc = package_desc
        self.has_mirror = has_mirror


class QtArchives:
    """Hold Qt archive packages list"""

    BASE_URL = 'https://download.qt.io/online/qtsdkrepository/'
    archives = []
    base = None
    has_mirror = False
    version = None
    target = None
    arch = None
    mirror = None

    def __init__(self, os_name, target, version, arch, mirror=None, logging=None):
        self.version = version
        self.target = target
        self.arch = arch
        self.mirror = mirror
        if mirror is not None:
            self.has_mirror = True
            self.base = mirror + '/online/qtsdkrepository/'
        else:
            self.has_mirror = False
            self.base = self.BASE_URL
        if logging:
            self.logger = logging
        else:
            self.logger = getLogger('aqt')
        self._get_archives(os_name)

    def _get_archives(self, os_name):
        qt_ver_num = self.version.replace(".", "")

        if os_name == 'windows':
            archive_url = self.base + os_name + '_x86/' + self.target + '/' + 'qt5_' + qt_ver_num + '/'
        else:
            archive_url = self.base + os_name + '_x64/' + self.target + '/' + 'qt5_' + qt_ver_num + '/'

        # Get packages index
        update_xml_url = "{0}Updates.xml".format(archive_url)
        try:
            r = requests.get(update_xml_url)
        except requests.exceptions.ConnectionError as e:
            self.logger.error('Download error: %s\n' % e.args, exc_info=True)
            raise e
        else:
            self.update_xml = ElementTree.fromstring(r.text)
            for packageupdate in self.update_xml.iter("PackageUpdate"):
                name = packageupdate.find("Name").text
                if name.split(".")[-1] != self.arch:
                    continue
                if name.split(".")[-2] == "debug_info":
                    continue
                if packageupdate.find("DownloadableArchives").text is None:
                    continue
                if name == "qt.qt5.{}.{}".format(qt_ver_num, self.arch) or name == "qt.{}.{}".format(qt_ver_num, self.arch):
                    # basic packages
                    pass
                else:
                    # optional packages: FIXME: check option whether install or not
                    pass
                downloadable_archives = packageupdate.find("DownloadableArchives").text.split(", ")
                full_version = packageupdate.find("Version").text
                package_desc = packageupdate.find("Description").text
                for archive in downloadable_archives:
                    package_url = archive_url + name + "/" + full_version + archive
                    self.archives.append(QtPackage(name, package_url, archive, package_desc,
                                                   has_mirror=self.has_mirror))

        if len(self.archives) == 0:
            print("Error while parsing package information!")
            exit(1)

    def get_archives(self):
        return self.archives

    def get_target_config(self):
        return self.version, self.target, self.arch


class ToolArchives(QtArchives):
    """Hold tool archive package list
        when installing mingw tool, argument would be
        ToolArchive(windows, desktop, 4.9.1-3, mingw)
        when installing ifw tool, argument would be
        ToolArchive(linux, desktop, 3.1.1, ifw)
    """

    def __init__(self, os_name, tool_name, version, arch, mirror=None, logging=None):
        self.tool_name = tool_name
        super(ToolArchives, self).__init__(os_name, 'desktop', version, arch, mirror, logging)

    def _get_archives(self, os_name):
        if os_name == 'windows':
            archive_url = self.base + os_name + '_x86/' + self.target + '/'
        else:
            archive_url = self.base + os_name + '_x64/' + self.target + '/'
        update_xml_url = "{0}{1}/Updates.xml".format(archive_url, self.tool_name)
        try:
            r = requests.get(update_xml_url)
        except requests.exceptions.ConnectionError as e:
            self.logger.error('Download error: %s\n' % e.args, exc_info=True)
            raise e
        else:
            self.update_xml = ElementTree.fromstring(r.text)
            for packageupdate in self.update_xml.iter("PackageUpdate"):
                name = packageupdate.find("Name").text
                downloadable_archives = packageupdate.find("DownloadableArchives").text.split(", ")
                full_version = packageupdate.find("Version").text
                if full_version != self.version:
                    continue
                if "-" in full_version:
                    split_version = full_version.split("-")
                    named_version = split_version[0] + "-" + split_version[1]
                else:
                    named_version = full_version
                package_desc = packageupdate.find("Description").text
                for archive in downloadable_archives:
                    package_url = archive_url + self.tool_name + "/" + name + "/" + named_version + archive
                    self.archives.append(QtPackage(name, package_url, archive, package_desc,
                                                   has_mirror=(self.mirror is not None)))

    def get_target_config(self):
        return "Tools", self.target, self.arch

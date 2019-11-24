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

import asyncio
import xml.etree.ElementTree as ElementTree
from logging import getLogger

import aiohttp
from aiohttp import ClientError

from aqt.helper import altlink


class QtPackage:
    """
      Hold package information.
    """
    name = ""
    url = ""
    archive = ""
    desc = ""
    mirror = None
    has_mirror = False

    def __init__(self, name, archive_url, archive, package_desc, has_mirror=False):
        self.name = name
        self.url = archive_url
        self.archive = archive
        self.desc = package_desc
        self.has_mirror = has_mirror


class QtArchives:
    """Hold Qt archive packages list."""

    __slots__ = ['archives', 'base', 'has_mirror', 'version', 'qt_ver_num', 'target', 'arch', 'mod_list',
                 'mirror', 'os_name', 'logger', 'update_xml', 'mirror_update_xml', 'archive_path_len']

    BASE_URL = 'https://download.qt.io/online/qtsdkrepository/'

    def __init__(self, os_name, target, version, arch, modules=None, mirror=None, logging=None):
        self.archives = []
        self.version = version
        self.qt_ver_num = self.version.replace(".", "")
        self.target = target
        self.arch = arch
        self.mirror = mirror
        self.os_name = os_name
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
        self.mod_list = []
        for m in modules if modules is not None else []:
            fqmn = "qt.qt5.{}.{}.{}".format(self.qt_ver_num, m, arch)
            self.mod_list.append(fqmn)
        self.update_xml = None
        self._get_archives()

    def asyncrun(self, arg):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(arg)
        loop.run_until_complete(asyncio.sleep(0.250))
        return result

    async def get_update_xml(self, url):
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=True)) as client:
            try:
                new_url = url
                resp = await client.get(url, allow_redirects=False)
                if resp.status == 302:
                    new_url = await altlink(resp.headers['Location'])
                    resp = await client.get(new_url)
            except ClientError as e:
                self.logger.error('Download error: %s\n' % e.args, exc_info=True)
                raise e
            else:
                self.update_xml = ElementTree.fromstring(await resp.text())
            if not self.has_mirror:
                self.base = new_url[:-(self.archive_path_len + 11)]

    def _get_archives(self):
        qt_ver_num = self.version.replace(".", "")

        # Get packages index
        archive_path = "{0}{1}{2}/qt5_{3}{4}".format(self.os_name,
                                                     '_x86/' if self.os_name == 'windows' else '_x64/',
                                                     self.target, qt_ver_num,
                                                     '_wasm/' if self.arch == 'wasm_32' else '/')
        self.archive_path_len = len(archive_path)
        update_xml_url = "{0}{1}Updates.xml".format(self.base, archive_path)
        self.logger.debug("- Start retrieving Update.xml from {}...".format(update_xml_url))
        self.asyncrun(self.get_update_xml(update_xml_url))
        self.logger.debug("- Finish retrieving Update.xml from {}".format(update_xml_url))
        archive_url = "{0}{1}".format(self.base, archive_path)
        target_packages = ["qt.qt5.{}.{}".format(qt_ver_num, self.arch), "qt.{}.{}".format(qt_ver_num, self.arch)]
        target_packages.extend(self.mod_list)
        for packageupdate in self.update_xml.iter("PackageUpdate"):
            name = packageupdate.find("Name").text
            if packageupdate.find("DownloadableArchives").text is None:
                continue
            if name in target_packages:
                downloadable_archives = packageupdate.find("DownloadableArchives").text.split(", ")
                full_version = packageupdate.find("Version").text
                package_desc = packageupdate.find("Description").text
                for archive in downloadable_archives:
                    package_url = archive_url + name + "/" + full_version + archive
                    self.archives.append(QtPackage(name, package_url, archive, package_desc,
                                                   has_mirror=self.has_mirror))
        if len(self.archives) == 0:
            self.logger.error("Error while parsing package information!")
            exit(1)

    def get_archives(self):
        """
          It returns an archive package list.

         :return package list
         :rtype: List[QtPackage]
         """
        return self.archives

    def get_target_config(self):
        """Get target configuration

        :return: configured target and its version with arch
        :rtype: tuple(version, target, arch)
        """
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
        super(ToolArchives, self).__init__(os_name, 'desktop', version, arch, mirror=mirror, logging=logging)

    def _get_archives(self):
        if self.os_name == 'windows':
            archive_path = self.os_name + '_x86/' + self.target + '/' + self.tool_name
        else:
            archive_path = self.os_name + '_x64/' + self.target + '/' + self.tool_name
        self.archive_path_len = len(archive_path)
        update_xml_url = "{0}{1}/Updates.xml".format(self.base, archive_path)
        self.asyncrun(self.get_update_xml(update_xml_url))
        archive_url = "{0}{1}".format(self.base, archive_path)
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
                package_url = archive_url + "/" + name + "/" + named_version + archive
                self.archives.append(QtPackage(name, package_url, archive, package_desc,
                                               has_mirror=(self.mirror is not None)))
        if len(self.archives) == 0:
            self.logger.error("Error while parsing package information!")
            exit(1)

    def get_target_config(self):
        """Get target configuration.

        :return tuple of three parameter, "Tools", target and arch
        """
        return "Tools", self.target, self.arch

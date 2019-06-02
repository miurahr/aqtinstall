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

import logging
import requests
import traceback
import xml.etree.ElementTree as ElementTree
from six import StringIO


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
    BASE_URL = 'https://download.qt.io/online/qtsdkrepository/'
    archives = []
    base = None

    def __init__(self, os_name, qt_version, target, arch, mirror=None):
        self.qt_version = qt_version
        self.target = target
        self.arch = arch
        if mirror is not None:
            self.has_mirror = True
            self.base = mirror + '/online/qtsdkrepository/'
        else:
            self.base = self.BASE_URL
        qt_ver_num = qt_version.replace(".", "")

        # install mingw runtime package
        if arch in ['win64_mingw73', 'win32_mingw73', 'win64_mingw53', 'win32_mingw53']:
            archive_url = self.base + 'windows_x86/desktop/tools_mingw/'
            update_xml_url = "{0}Updates.xml".format(archive_url)
            try:
                r = requests.get(update_xml_url)
            except requests.exceptions.ConnectionError as e:
                print("Caught download error: %s" % e.args)
                exc_buffer = StringIO()
                traceback.print_exc(file=exc_buffer)
                logging.error('Download error:\n%s', exc_buffer.getvalue())
                raise e
            else:
                self.update_xml = ElementTree.fromstring(r.text)
                for packageupdate in self.update_xml.iter("PackageUpdate"):
                    name = packageupdate.find("Name").text
                    if name.split(".")[-1] != arch:
                        continue
                    downloadable_archives = packageupdate.find("DownloadableArchives").text.split(", ")
                    full_version = packageupdate.find("Version").text
                    split_version = full_version.split["-"]
                    named_version = split_version[0] + "-" + split_version[1]
                    package_desc = packageupdate.find("Description").text
                    for archive in downloadable_archives:
                        # ex. 7.3.0-1x86_64-7.3.0-release-posix-seh-rt_v5-rev0.7z
                        package_url = archive_url + name + "/" + named_version + archive
                        self.archives.append(QtPackage(name, package_url, archive, package_desc,
                                                       has_mirror=(mirror is not None)))
        # Ordinary packages
        if os_name == 'windows':
            archive_url = self.base + os_name + '_x86/' + target + '/' + 'qt5_' + qt_ver_num + '/'
        else:
            archive_url = self.base + os_name + '_x64/' + target + '/' + 'qt5_' + qt_ver_num + '/'

        # Get packages index
        update_xml_url = "{0}Updates.xml".format(archive_url)
        try:
            r = requests.get(update_xml_url)
        except requests.exceptions.ConnectionError as e:
            print("Caught download error: %s" % e.args)
            exc_buffer = StringIO()
            traceback.print_exc(file=exc_buffer)
            logging.error('Download error:\n%s', exc_buffer.getvalue())
            raise e
        else:
            self.update_xml = ElementTree.fromstring(r.text)
            for packageupdate in self.update_xml.iter("PackageUpdate"):
                name = packageupdate.find("Name").text
                if name.split(".")[-1] != arch:
                    continue
                if name.split(".")[-2] == "debug_info":
                    continue
                if packageupdate.find("DownloadableArchives").text is None:
                    continue
                if name == "qt.qt5.{}.{}".format(qt_ver_num, arch) or name == "qt.{}.{}".format(qt_ver_num, arch):
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
                                                   has_mirror=(mirror is not None)))

        if len(self.archives) == 0:
            print("Error while parsing package information!")
            exit(1)

    def get_archives(self):
        return self.archives

    def get_target_config(self):
        return self.qt_version, self.target, self.arch

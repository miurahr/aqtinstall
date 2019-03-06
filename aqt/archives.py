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

from six.moves import urllib
import xml.etree.ElementTree as ElementTree


class QtPackage:
    name = ""
    url = ""
    archive = ""
    desc = ""

    def __init__(self, name, archive_url, archive, package_desc):
        self.name = name
        self.url = archive_url
        self.archive = archive
        self.desc = package_desc

    def get_name(self):
        return self.name

    def get_url(self):
        return self.url

    def get_archive(self):
        return self.archive

    def get_desc(self):
        return self.desc


class QtArchives:
    BASE_URL = 'https://download.qt.io/online/qtsdkrepository/'
    archives = []

    def __init__(self, os_name, qt_version, target, arch):
        qt_ver_num = qt_version.replace(".", "")
        if os_name == 'windows':
            archive_url = self.BASE_URL + os_name + '_x86/' + target + '/' + 'qt5_' + qt_ver_num + '/'
        else:
            archive_url = self.BASE_URL + os_name + '_x64/' + target + '/' + 'qt5_' + qt_ver_num + '/'

        # Get packages index
        update_xml_url = "{0}Updates.xml".format(archive_url)
        proxies = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxies)
        urllib.request.install_opener(opener)
        content = urllib.request.urlopen(update_xml_url).read()
        self.update_xml = ElementTree.fromstring(content)
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
                self.archives.append(QtPackage(name, package_url, archive, package_desc))

        if len(self.archives) == 0:
            print("Error while parsing package information!")
            exit(1)

    def get_archives(self):
        return self.archives


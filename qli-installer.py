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
#

import argparse
import os
import platform
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ElementTree

from argparse import RawTextHelpFormatter
from multiprocessing.dummy import Pool


BASE_URL = "https://download.qt.io/online/qtsdkrepository/"
NUM_PROCESS = 3


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
    archives = []

    def __init__(self, os_name, qt_version, target, arch):
        qt_ver_num = qt_version.replace(".", "")
        archive_url = BASE_URL
        if os_name == "windows":
            archive_url += os_name + "_x86/"
        else:
            archive_url += os_name + "_x64/"
        archive_url += target + "/" + "qt5_" + qt_ver_num + "/"
        # Get packages index
        update_xml_url = archive_url + "Updates.xml"
        content = urllib.request.urlopen(update_xml_url).read()
        self.update_xml = ElementTree.fromstring(content)
        for packageupdate in self.update_xml.iter("PackageUpdate"):
            if packageupdate.find("DownloadableArchives").text is None:
                continue
            name = packageupdate.find("Name").text
            downloadable_archives = packageupdate.find("DownloadableArchives").text.split(", ")
            full_version = packageupdate.find("Version").text
            package_desc = packageupdate.find("Description").text
            for archive in downloadable_archives:
                package_url = archive_url + name + "/" + full_version + archive
                self.archives.append(QtPackage(name, package_url, archive, package_desc))

        if len(self.archives)==0:
            print("Error while parsing package information!")
            exit(1)

    def get_archives(self):
        return self.archives


class QtInstaller:
    def __init__(self, qt_archives):
        self.qt_archives = qt_archives

    def retrieve_archive(self, package):
        archive = package.get_archive()
        url = package.get_url()
        sys.stdout.write("\033[K")
        print("-Downloading {}...".format(url))
        urllib.request.urlretrieve(url, archive)
        sys.stdout.write("\033[K")
        print("-Extracting {}...".format(archive))
        if platform.system() is 'Windows':
            subprocess.run([r'C:\Program Files\7-Zip\7z.exe', 'x', '-aoa', '-y', archive])
        else:
            subprocess.run([r'7z', 'x', '-aoa', '-y', archive])
        os.unlink(archive)

    def get_base_dir(self, qt_version):
        return os.path.join(os.getcwd(), 'Qt{}'.format(qt_version))

    def install(self, qt_version, arch):
        if arch.startswith('win'):
            arch_dir = arch[6:]
        else:
            arch_dir = arch
        base_dir = self.get_base_dir(qt_version)
        if not os.path.exists(base_dir):
            os.mkdir(base_dir)
        elif not os.path.isdir(base_dir):
            os.unlink(base_dir)
            os.mkdir(base_dir)
        os.chdir(base_dir)

        p = Pool(NUM_PROCESS)
        archives = self.qt_archives.get_archives()
        p.map(self.retrieve_archive, archives)

        try:
            # prepare qt.conf
            with open(os.path.join(base_dir, qt_version, arch_dir, 'bin', 'qt.conf'), 'w') as f:
                f.write("[Paths]\n")
                f.write("Prefix=..\n")
            # prepare qtconfig.pri
            with open(os.path.join(base_dir, qt_version, arch_dir, 'mkspecs', 'qconfig.pri'), 'r+') as f:
                lines = f.readlines()
                f.seek(0)
                f.truncate()
                for line in lines:
                    if 'QT_EDITION' in line:
                        line = 'QT_EDITION = OpenSource'
                    f.write(line)
        except:
            pass

def show_help():
    print("Usage: {} <qt-version> <host> <target> [<arch>]\n".format(sys.argv[0]))
    print("qt-version:   Qt version in the format of \"5.X.Y\"")
    print("host systems: linux, mac, windows")
    print("targets:      desktop, android, ios")
    print("arch: ")
    print("  target linux/desktop:   gcc_64")
    print("  target mac/desktop:     clang_64")
    print("  target mac/ios:         ios")
    print("  windows/desktop:        win64_msvc2017_64, win64_msvc2015_64")
    print("                          in32_msvc2015, win32_mingw53")
    print("  android:                android_x86, android_armv7")
    exit(1)

def main():
    parser = argparse.ArgumentParser(description='Install Qt SDK.', formatter_class=RawTextHelpFormatter, add_help=True)
    parser.add_argument("qt_version", help="Qt version in the format of \"5.X.Y\"")
    parser.add_argument('host', choices=['linux', 'mac', 'windows'], help="host os name")
    parser.add_argument('target', choices=['desktop', 'android', 'ios'], help="target sdk")
    parser.add_argument('arch', nargs='?', help="\ntarget linux/desktop: gcc_64"
                                                "\ntarget mac/desktop:   clang_64"
                                                "\ntarget mac/ios:       ios"
                                                "\nwindows/desktop:      win64_msvc2017_64, win64_msvc2015_64"
                                                "\n                      in32_msvc2015, win32_mingw53"
                                                "\nandroid:              android_x86, android_armv7")
    args = parser.parse_args()
    arch = args.arch
    if arch is None:
        if os_name == "linux" and target == "desktop":
            arch = "gcc_64"
        elif os_name == "mac" and target == "desktop":
            arch = "clang_64"
        elif os_name == "mac" and target == "ios":
            arch = "ios"
    if arch == "":
        print("Please supply a target architecture.")
        args.print_help()
        exit(1)

    qt_version = args.qt_version
    os_name = args.host
    target = args.target

    archives = QtArchives(os_name, qt_version, target, arch)
    installer = QtInstaller(archives)
    installer.install(qt_version, arch)

    sys.stdout.write("\033[K")
    print("Finished installation")


if __name__ == "__main__":
        sys.exit(main())

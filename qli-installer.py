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

class QtArchives:
    full_version = ""
    archives = []
    archives_url = ""

    def __init__(self, os_name, qt_version, target, arch):
        qt_ver_num = qt_version.replace(".", "")
        # Build repo URL
        packages_url = BASE_URL
        if os_name == "windows":
            packages_url += os_name + "_x86/"
        else:
            packages_url += os_name + "_x64/"
        packages_url += target + "/"
        packages_url += "qt5_" + qt_ver_num + "/"
        # Get packages index
        update_xml_url = packages_url + "Updates.xml"
        content = urllib.request.urlopen(update_xml_url).read()
        self.update_xml = ElementTree.fromstring(content)
        for packageupdate in self.update_xml.findall("PackageUpdate"):
            name = packageupdate.find("Name").text
            if name == "qt.qt5.{}.{}".format(qt_ver_num, arch) or name == "qt.{}.{}".format(qt_ver_num, arch):
                self.full_version = packageupdate.find("Version").text
                self.archives = packageupdate.find("DownloadableArchives").text.split(", ")
                self.package_desc = packageupdate.find("Description").text
                if ".qt5." in name:
                    self.archives_url = packages_url + "qt.qt5.{}.{}/".format(qt_ver_num, arch)
                else:
                    self.archives_url = packages_url + "qt.{}.{}/".format(qt_ver_num, arch)
                break

        if not self.full_version or not self.archives:
            print("Error while parsing package information!")
            exit(1)

    def get_package_desc(self):
        return self.package_desc

    def get_archives_url(self):
        return self.archives_url

    def get_base_url(self):
        return self.archives_url + self.full_version
    
    def get_archives(self):
        return self.archives


class QtInstaller:
    def __init__(self, qt_archives):
        self.qt_archives = qt_archives
        self.url_base = qt_archives.get_base_url()

    def retrieve_archive(self, archive):
        sys.stdout.write("\033[K")
        print("Downloading {}...".format(archive), end="\r")
        urllib.request.urlretrieve(self.url_base + archive, archive)
        sys.stdout.write("\033[K")
        print("Extracting {}...".format(archive), end="\r")
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

        p = Pool(4)
        archives = self.qt_archives.get_archives()
        p.map(self.retrieve_archive, archives)

        f = open(os.path.join(base_dir, qt_version, arch_dir, 'bin', 'qt.conf'), 'w')
        f.write("[Paths]\n")
        f.write("Prefix=..\n")
        f.close()


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

    qt_version = args.qt_version
    os_name = args.host
    target = args.target

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

    qt_archives = QtArchives(os_name, qt_version, target, arch)
    installer = QtInstaller(qt_archives)

    # show teaser
    print("****************************************")
    print("Installing {}".format(qt_archives.get_package_desc()))
    print("****************************************")
    print("HOST:      ", os_name)
    print("TARGET:    ", target)
    print("ARCH:      ", arch)
    print("Source URL:", qt_archives.get_archives_url())
    print("****************************************")
    print("Install to: ", installer.get_base_dir(qt_version))

    # start install
    installer.install(qt_version, arch)

    sys.stdout.write("\033[K")
    print("Finished installation")

main()

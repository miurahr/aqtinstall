#!/usr/bin/env python3
#
# Copyright (C) 2018 Linus Jahn <lnj@kaidan.im>
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

import sys
import os

if len(sys.argv) < 3 or len(sys.argv) > 4:
    print("Usage: {} <host> <target> [<arch>]\n".format(sys.argv[0]))
    print("host systems: linux, mac, windows")
    print("targets:      desktop, android, ios")
    exit(1)

base_url = "https://download.qt.io/online/qtsdkrepository/"
# one of: "linux", "mac", "windows"
os_name = sys.argv[1]
# one of: "desktop", "android", "ios"
target = sys.argv[2]

qt_major = "5"
qt_minor = "11"
qt_patch = "2"
qt_extra = "0" # needed for buid num
qt_version = "{}.{}.{}".format(qt_major, qt_minor, qt_patch)
qt_ver_num = "{}{}{}".format(qt_major, qt_minor, qt_patch)
qt_build_date = ""
if os_name == "linux" and target == "desktop":
    qt_build_date = "201809141941"
elif os_name == "linux" and target == "android":
    qt_build_date = "201809142008"
elif os_name == "mac" and target == "desktop":
    qt_build_date = "201809141947"
elif os_name == "mac" and target == "ios":
    qt_build_date = "201809142015"
elif os_name == "mac" and target == "android":
    qt_build_date = "201809142012"
elif os_name == "windows" and target == "desktop":
    qt_build_date = "201809141946"
elif os_name == "windows" and target == "android":
    qt_build_date = "201809142114"

qt_build_num = "{}-{}-{}".format(qt_version, qt_extra, qt_build_date)

# Target architectures:
#
# linux/desktop:   "gcc_64"
# mac/desktop:     "clang_64"
# mac/ios:         "ios"
# windows/desktop: "win64_msvc2017_64", "win64_msvc2015_64",
#                  "win32_msvc2015", "win32_mingw53"
# */android:       "android_x86", "android_armv7"
arch = ""
if len(sys.argv) == 4:
    arch = sys.argv[3]
elif os_name == "linux" and target == "desktop":
    arch = "gcc_64"
elif os_name == "mac" and target == "desktop":
    arch = "clang_64"
elif os_name == "mac" and target == "ios":
    arch = "ios"

if arch == "":
    print("Please supply a target architecture.")
    exit(1)

print("****************************************")
print("Installing Qt {}".format(qt_version))
print("****************************************")
print("HOST:   {}".format(os_name))
print("TARGET: {}".format(target))
print("ARCH:   {}".format(arch))
print("****************************************")

# These are the base packages we need on every configuration
packages = [
    "qtbase",
    "qtconnectivity",
    "qtwebchannel",
    "qtmultimedia",
    "qttranslations",
    "qtgraphicaleffects",
    "qtsvg",
    "qtdeclarative",
    "qtwebsockets",
    "qtimageformats",
    "qttools",
    "qtxmlpatterns",
    "qtsensors",
    "qtlocation",
    "qtserialport",
    "qtquickcontrols",
    "qtquickcontrols2",
    "qt3d",
    "qtcanvas3d",
    "qtwebview",
    "qtserialbus",
    "qtscxml",
    "qtgamepad",
    "qtspeech"
]
# Add extra packages
if os_name == "linux" and target == "desktop":
    packages.append("qtx11extras")
    packages.append("qtwayland")
elif os_name == "mac" and (target == "ios" or target == "desktop"):
    packages.append("qtmacextras")
elif os_name == "windows" and target == "desktop":
    packages.append("qtwinextras")
elif target == "android":
    packages.append("qtandroidextras")

# Build repo URL
packages_url = base_url
if os_name == "windows":
    packages_url += os_name + "_x86/"
else:
    packages_url += os_name + "_x64/"
packages_url += target + "/"
packages_url += "qt5_" + qt_ver_num + "/"
packages_url += "qt.qt5.{}.{}/".format(qt_ver_num, arch)

pkg_name = qt_build_num + "{}" # qt package name will be inserted here
if os_name == "linux":
    if target == "desktop":
        pkg_name += "-Linux-RHEL_7_4-GCC-Linux-RHEL_7_4-X86_64"
    elif target == "android":
        if arch == "android_x86":
            pkg_name += "-Linux-RHEL_7_4-GCC-Android-Android_ANY-X86"
        elif arch == "android_armv7":
            pkg_name += "-Linux-RHEL_7_4-GCC-Android-Android_ANY-ARMv7"
elif os_name == "mac":
    if target == "desktop":
        pkg_name += "-MacOS-MacOS_10_12-Clang-MacOS-MacOS_10_12-X86_64"
    elif target == "ios":
        pkg_name += "-MacOS-MacOS_10_12-Clang-IOS-IOS_ANY-Multi"
    elif target == "android":
        if arch == "android_x86":
            pkg_name += "-MacOS-MacOS_10_12-GCC-Android-Android_ANY-X86"
        elif arch == "android_armv7":
            pkg_name += "-MacOS-MacOS_10_12-GCC-Android-Android_ANY-ARMv7"
elif os_name == "windows":
    if target == "desktop":
        if arch == "win64_msvc2017_64":
            pkg_name += "-Windows-Windows_10-MSVC2017-Windows-Windows_10-X86_64"
        elif arch == "win64_msvc2015_64":
            pkg_name += "-Windows-Windows_10-MSVC2015-Windows-Windows_10-X86_64"
        elif arch == "win32_msvc2015":
            pkg_name += "-Windows-Windows_10-MSVC2015-Windows-Windows_10-X86"
        elif arch == "win32_mingw53":
            pkg_name += "-Windows-Windows_7-Mingw53-Windows-Windows_7-X86"
    elif target == "android":
        if arch == "android_x86":
            pkg_name += "-Windows-Windows_7-Mingw53-Android-Android_ANY-X86"
        elif arch == "android_armv7":
            pkg_name += "-Windows-Windows_7-Mingw53-Android-Android_ANY-ARMv7"
pkg_name += ".7z"

packages_url += pkg_name

for package in packages:
    package_name = pkg_name.format(package)
    package_url = packages_url.format(package)

    print("Downloading {}...".format(package), end="\r")
    sys.stdout.write("\033[K")
    os.system("wget -q -O package.7z " + package_url)

    print("Extracting {}...".format(package), end="\r")
    sys.stdout.write("\033[K")
    os.system("7z x package.7z 1>/dev/null")
    os.system("rm package.7z")

print("Finished installation")

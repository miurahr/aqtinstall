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

import argparse
import os
import platform
import sys

from aqt.archives import QtArchives
from aqt.installer import QtInstaller


class Cli():

    __slot__ = ['parser']

    COMBINATION = [
        {'os_name': 'linux',   'target': 'desktop', 'arch': 'gcc_64'},
        {'os_name': 'linux',   'target': 'android', 'arch': 'android_x86'},
        {'os_name': 'linux',   'target': 'android', 'arch': 'android_armv7'},
        {'os_name': 'mac',     'target': 'desktop', 'arch': 'clang_64'},
        {'os_name': 'mac',     'target': 'ios',     'arch': 'ios'},
        {'os_name': 'windows', 'target': 'desktop', 'arch': 'win64_msvc2017_64'},
        {'os_name': 'windows', 'target': 'desktop', 'arch': 'win32_msvc2017'},
        {'os_name': 'windows', 'target': 'desktop', 'arch': 'win64_msvc2015_64'},
        {'os_name': 'windows', 'target': 'desktop', 'arch': 'win32_msvc2015'},
        {'os_name': 'windows', 'target': 'desktop', 'arch': 'win64_mingw73'},
        {'os_name': 'windows', 'target': 'desktop', 'arch': 'win32_mingw73'},
        {'os_name': 'windows', 'target': 'desktop', 'arch': 'win64_mingw53'},
        {'os_name': 'windows', 'target': 'desktop', 'arch': 'win32_mingw53'},
        {'os_name': 'windows', 'target': 'winrt',   'arch': 'win64_msvc2017_winrt_x64'},
        {'os_name': 'windows', 'target': 'winrt',   'arch': 'win64_msvc2017_winrt_x86'},
        {'os_name': 'windows', 'target': 'winrt',   'arch': 'win64_msvc2017_winrt_armv7'},
        {'os_name': 'windows', 'target': 'android', 'arch': 'android_x86'},
        {'os_name': 'windows', 'target': 'android', 'arch': 'android_armv7'},
    ]

    def check_arg_combination(self, qt_version, os_name, target, arch):
        for c in self.COMBINATION:
            if c['os_name'] == os_name and c['target'] == target and c['arch'] == arch:
                return True
        return False

    def run_install(self, args):
        arch = args.arch
        target = args.target
        os_name = args.host
        output_dir = args.outputdir
        mirror = args.base
        use_py7zr = args.internal
        sevenzip = None
        if not use_py7zr:
            sevenzip = args.external
            if sevenzip is None:
                if platform.system() == 'Windows':
                    sevenzip = r'C:\Program Files\7-Zip\7z.exe'
                else:
                    sevenzip = r'7zr'
            elif os.path.exists(sevenzip):
                pass
            else:
                print('Specified external 7zip command is not exist.')
                exit(1)
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
        if not self.check_arg_combination(qt_version, os_name, target, arch):
            print("Specified target combination is not valid: {} {} {}".format(os_name, target, arch))
            exit(1)
        if mirror is not None:
            if not mirror.startswith('http://') or mirror.startswith('https://') or mirror.startswith('ftp://'):
                args.print_help()
                exit(1)
        if output_dir is not None:
            QtInstaller(QtArchives(os_name, qt_version, target, arch,  mirror=mirror)).install(command=sevenzip,
                                                                                               target_dir=output_dir)
        else:
            QtInstaller(QtArchives(os_name, qt_version, target, arch, mirror=mirror)).install(command=sevenzip)

        sys.stdout.write("\033[K")
        print("Finished installation")

    def run_list(self, args):
        print('List Qt packages for %s' % args.qt_version)

    def show_help(self, args):
        print("show help")
        self.parser.print_help()

    def __init__(self):
        parser = argparse.ArgumentParser(prog='aqt', description='Installer for Qt SDK.',
                                         formatter_class=argparse.RawTextHelpFormatter, add_help=True)
        subparsers = parser.add_subparsers(title='subcommands', description='Valid subcommands',
                                           help='subcommand for aqt Qt installer')
        install_parser = subparsers.add_parser('install')
        install_parser.set_defaults(func=self.run_install)
        install_parser.add_argument("qt_version", help="Qt version in the format of \"5.X.Y\"")
        install_parser.add_argument('host', choices=['linux', 'mac', 'windows'], help="host os name")
        install_parser.add_argument('target', choices=['desktop', 'winrt', 'android', 'ios', 'tool'], help="target sdk")
        install_parser.add_argument('arch', nargs='?', help="\ntarget linux/desktop: gcc_64"
                                    "\ntarget mac/desktop:   clang_64"
                                    "\ntarget mac/ios:       ios"
                                    "\nwindows/desktop:      win64_msvc2017_64, win64_msvc2015_64"
                                    "\n                      win32_msvc2015, win32_mingw53"
                                    "\n                      win64_mingw73, win32_mingw73"
                                    "\nwindows/winrt:        win64_msvc2017_winrt_x64, win64_msvc2017_winrt_x86"
                                    "\n                      win64_msvc2017_winrt_armv7"
                                    "\nandroid:              android_x86, android_armv7")
        install_parser.add_argument('-O', '--outputdir', nargs='?',
                                    help='Target output directory(default current directory)')
        install_parser.add_argument('-b', '--base', nargs='?',
                                    help="Specify mirror base url such as http://mirrors.ocf.berkeley.edu/qt/, "
                                         "where 'online' folder exist.")
        install_parser.add_argument('-E', '--external', nargs=1, help='Specify external 7zip command path.')
        install_parser.add_argument('--internal', action='store_true', help='Use internal extractor.')
        list_parser = subparsers.add_parser('list')
        list_parser.set_defaults(func=self.run_list)
        list_parser.add_argument("qt_version", help="Qt version in the format of \"5.X.Y\"")
        help_parser = subparsers.add_parser('help')
        help_parser.set_defaults(func=self.show_help)
        self.parser = parser

    def run(self):
        args = self.parser.parse_args()
        args.func(args)

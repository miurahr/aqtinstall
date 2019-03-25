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
import sys

from aqt.archives import QtArchives
from aqt.installer import QtInstaller


class Cli():

    __slot__ = ['parser']

    def run_install(self, args):
        arch = args.arch
        target = args.target
        os_name = args.host
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

        QtInstaller(QtArchives(os_name, qt_version, target, arch)).install()

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
        install_parser.add_argument('target', choices=['desktop', 'android', 'ios'], help="target sdk")
        install_parser.add_argument('arch', nargs='?', help="\ntarget linux/desktop: gcc_64"
                                    "\ntarget mac/desktop:   clang_64"
                                    "\ntarget mac/ios:       ios"
                                    "\nwindows/desktop:      win64_msvc2017_64, win64_msvc2015_64"
                                    "\n                      in32_msvc2015, win32_mingw53"
                                    "\nandroid:              android_x86, android_armv7")
        list_parser = subparsers.add_parser('list')
        list_parser.set_defaults(func=self.run_list)
        list_parser.add_argument("qt_version", help="Qt version in the format of \"5.X.Y\"")
        help_parser = subparsers.add_parser('help')
        help_parser.set_defaults(func=self.show_help)
        self.parser = parser

    def run(self):
        args = self.parser.parse_args()
        args.func(args)

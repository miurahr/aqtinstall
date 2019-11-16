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
import json
import logging
import logging.config
import os
import platform
import sys

import yaml
from aqt.archives import QtArchives, ToolArchives
from aqt.installer import QtInstaller


class Cli():

    __slot__ = ['parser', 'combinations', 'logger']

    def __init__(self):
        with open(os.path.join(os.path.dirname(__file__), 'combinations.json'), 'r') as j:
            self.combinations = json.load(j)[0]
        self._create_parser()

    def _check_tools_arg_combination(self, os_name, tool_name, arch):
        for c in self.combinations['tools']:
            if c['os_name'] == os_name and c['tool_name'] == tool_name and c['arch'] == arch:
                return True
        return False

    def _check_qt_arg_combination(self, qt_version, os_name, target, arch):
        for c in self.combinations['qt']:
            if c['os_name'] == os_name and c['target'] == target and c['arch'] == arch:
                return True
        return False

    def _set_sevenzip(self, args):
        sevenzip = None
        if sys.version_info > (3, 5):
            use_py7zr = args.internal
        else:
            use_py7zr = False
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
        return sevenzip

    def _set_arch(self, args, oarch, os_name, target):
        arch = oarch
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
        return arch

    def _check_mirror(self, args):
        mirror = args.base
        if mirror is not None:
            if not mirror.startswith('http://') or mirror.startswith('https://') or mirror.startswith('ftp://'):
                args.print_help()
                exit(1)
        return mirror

    def run_install(self, args):
        arch = args.arch
        target = args.target
        os_name = args.host
        output_dir = args.outputdir
        arch = self._set_arch(args, arch, os_name, target)
        modules = args.modules
        sevenzip = self._set_sevenzip(args)
        mirror = self._check_mirror(args)
        qt_version = args.qt_version
        if not self._check_qt_arg_combination(qt_version, os_name, target, arch):
            self.logger.error("Specified target combination is not valid: {} {} {}".format(os_name, target, arch))
            exit(1)
        QtInstaller(QtArchives(os_name, target, qt_version, arch, modules=modules, mirror=mirror, logging=self.logger),
                    logging=self.logger).install(command=sevenzip, target_dir=output_dir)
        sys.stdout.write("\033[K")
        print("Finished installation")

    def run_tool(self, args):
        arch = args.arch
        tool_name = args.tool_name
        os_name = args.host
        output_dir = args.outputdir
        sevenzip = self._set_sevenzip(args)
        version = args.version
        mirror = self._check_mirror(args)
        if not self._check_tools_arg_combination(os_name, tool_name, arch):
            self.logger.error("Specified target combination is not valid: {} {} {}".format(os_name, tool_name, arch))
            exit(1)
        QtInstaller(ToolArchives(os_name, tool_name, version, arch, mirror=mirror, logging=self.logger),
                    logging=self.logger).install(command=sevenzip, target_dir=output_dir)

    def run_list(self, args):
        print('List Qt packages for %s' % args.qt_version)

    def show_help(self, args):
        print("show help")
        self.parser.print_help()

    def _create_parser(self):
        parser = argparse.ArgumentParser(prog='aqt', description='Installer for Qt SDK.',
                                         formatter_class=argparse.RawTextHelpFormatter, add_help=True)
        parser.add_argument('--logging-conf', type=argparse.FileType('r'),
                            nargs=1, help="Specify logging configuration YAML file.")
        parser.add_argument('--logger', nargs=1, help="Specify logger name")
        subparsers = parser.add_subparsers(title='subcommands', description='Valid subcommands',
                                           help='subcommand for aqt Qt installer')
        install_parser = subparsers.add_parser('install')
        install_parser.set_defaults(func=self.run_install)
        install_parser.add_argument("qt_version", help="Qt version in the format of \"5.X.Y\"")
        install_parser.add_argument('host', choices=['linux', 'mac', 'windows'], help="host os name")
        install_parser.add_argument('target', choices=['desktop', 'winrt', 'android', 'ios'], help="target sdk")
        install_parser.add_argument('arch', nargs='?', help="\ntarget linux/desktop: gcc_64, wasm_32"
                                    "\ntarget mac/desktop:   clang_64, wasm_32"
                                    "\ntarget mac/ios:       ios"
                                    "\nwindows/desktop:      win64_msvc2017_64, win64_msvc2015_64"
                                    "\n                      win32_msvc2015, win32_mingw53"
                                    "\n                      win64_mingw73, win32_mingw73"
                                    "\n                      wasm_32"
                                    "\nwindows/winrt:        win64_msvc2017_winrt_x64, win64_msvc2017_winrt_x86"
                                    "\n                      win64_msvc2017_winrt_armv7"
                                    "\nandroid:              android_x86, android_armv7")
        install_parser.add_argument('-m', '--modules', nargs='*', help="Specify extra modules to install")
        install_parser.add_argument('-O', '--outputdir', nargs='?',
                                    help='Target output directory(default current directory)')
        install_parser.add_argument('-b', '--base', nargs='?',
                                    help="Specify mirror base url such as http://mirrors.ocf.berkeley.edu/qt/, "
                                         "where 'online' folder exist.")
        install_parser.add_argument('-E', '--external', nargs=1, help='Specify external 7zip command path.')
        if sys.version_info >= (3, 5):
            install_parser.add_argument('--internal', action='store_true', help='Use internal extractor.')
        tools_parser = subparsers.add_parser('tool')
        tools_parser.set_defaults(func=self.run_tool)
        tools_parser.add_argument('host', choices=['linux', 'mac', 'windows'], help="host os name")
        tools_parser.add_argument('tool_name', help="Name of tool such as tools_ifw, tools_mingw")
        tools_parser.add_argument("version", help="Tool version in the format of \"4.1.2\"")
        tools_parser.add_argument('arch', help="Name of full tool name such as qt.tools.ifw.31")
        tools_parser.add_argument('-O', '--outputdir', nargs='?',
                                  help='Target output directory(default current directory)')
        tools_parser.add_argument('-b', '--base', nargs='?',
                                  help="Specify mirror base url such as http://mirrors.ocf.berkeley.edu/qt/, "
                                       "where 'online' folder exist.")
        tools_parser.add_argument('-E', '--external', nargs=1, help='Specify external 7zip command path.')
        tools_parser.add_argument('--internal', action='store_true', help='Use internal extractor.')
        list_parser = subparsers.add_parser('list')
        list_parser.set_defaults(func=self.run_list)
        list_parser.add_argument("qt_version", help="Qt version in the format of \"5.X.Y\"")
        help_parser = subparsers.add_parser('help')
        help_parser.set_defaults(func=self.show_help)
        self.parser = parser

    def _setup_logging(self, args, env_key='LOG_CFG'):
        envconf = os.getenv(env_key, None)
        conf = None
        if args.logging_conf:
            conf = args.logging_conf
        elif envconf is not None:
            conf = envconf
        if conf is None or not os.path.exists(conf):
            conf = os.path.join(os.path.dirname(__file__), 'logging.yml')
        with open(conf, 'r') as f:
            log_config = yaml.safe_load(f.read())
            logging.config.dictConfig(log_config)
        if args.logger is not None:
            self.logger = logging.getLogger(args.logger)
        else:
            self.logger = logging.getLogger('aqt')

    def run(self, arg=None):
        args = self.parser.parse_args(arg)
        self._setup_logging(args)
        args.func(args)

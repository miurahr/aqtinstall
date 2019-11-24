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
import asyncio
import logging
import logging.config
import os
import pathlib

from packaging.version import Version, parse

from aqt.archives import QtArchives, ToolArchives
from aqt.installer import QtInstaller
from aqt.settings import Settings


class Cli():
    """CLI main class to parse command line argument and launch proper functions."""

    __slot__ = ['parser', 'combinations', 'logger']

    def __init__(self):
        self.settings = Settings()
        self._create_parser()

    def _check_tools_arg_combination(self, os_name, tool_name, arch):
        for c in self.settings.tools_combinations:
            if c['os_name'] == os_name and c['tool_name'] == tool_name and c['arch'] == arch:
                return True
        return False

    def _check_qt_arg_combination(self, qt_version, os_name, target, arch):
        for c in self.settings.qt_combinations:
            if c['os_name'] == os_name and c['target'] == target and c['arch'] == arch:
                return True
        return False

    def _set_arch(self, args, oarch, os_name, target, qt_version):
        arch = oarch
        if arch is None:
            if os_name == "linux" and target == "desktop":
                arch = "gcc_64"
            elif os_name == "mac" and target == "desktop":
                arch = "clang_64"
            elif os_name == "mac" and target == "ios":
                arch = "ios"
            elif target == "android" and parse(qt_version) >= Version('5.14.0'):
                arch = "android"
        if arch == "":
            print("Please supply a target architecture.")
            args.print_help()
            exit(1)
        return arch

    def _check_mirror(self, mirror):
        if mirror is None:
            return True
        if mirror.startswith('http://') or mirror.startswith('https://') or mirror.startswith('ftp://'):
            pass
        else:
            self.parser.print_help()
            exit(1)
        return True

    def _check_modules_arg(self, qt_version, modules):
        if modules is None:
            return True
        available = self.settings.available_modules(qt_version)
        if available is None:
            return False
        return all([m in available for m in modules])

    def run_install(self, args):
        arch = args.arch
        target = args.target
        os_name = args.host
        qt_version = args.qt_version
        output_dir = args.outputdir
        arch = self._set_arch(args, arch, os_name, target, qt_version)
        modules = args.modules
        mirror = args.base
        self._check_mirror(mirror)
        if not self._check_qt_arg_combination(qt_version, os_name, target, arch):
            self.logger.warning("Specified target combination is not valid: {} {} {}".format(os_name, target, arch))
        if not self._check_modules_arg(qt_version, modules):
            self.logger.warning("Some of specified modules are unknown.")
        installer = QtInstaller(QtArchives(os_name, target, qt_version, arch, modules=modules, mirror=mirror,
                                           logging=self.logger))
        results = self.asyncrun(installer.install(target_dir=output_dir))
        if all(results):
            self.make_conf_files(qt_version, arch, base_dir=output_dir)
            print("Finished installation")
        else:
            self.logger.error("Fails to installation.")

    def run_tool(self, args):
        arch = args.arch
        tool_name = args.tool_name
        os_name = args.host
        output_dir = args.outputdir
        version = args.version
        mirror = self._check_mirror(args.base)
        if not self._check_tools_arg_combination(os_name, tool_name, arch):
            self.logger.warning("Specified target combination is not valid: {} {} {}".format(os_name, tool_name, arch))
        installer = QtInstaller(ToolArchives(os_name, tool_name, version, arch, mirror=mirror, logging=self.logger))
        results = self.asyncrun(installer.install(target_dir=output_dir))
        if all(results):
            print("Finished installation")
        else:
            self.logger.error("Fails to installation.")

    def run_list(self, args):
        print('List Qt packages for %s' % args.qt_version)

    def show_help(self, args):
        print("show help")
        self.parser.print_help()

    def _create_parser(self):
        parser = argparse.ArgumentParser(prog='aqt', description='Installer for Qt SDK.',
                                         formatter_class=argparse.RawTextHelpFormatter, add_help=True)
        parser.add_argument('--logging-conf', type=argparse.FileType('r'),
                            nargs=1, help="Logging configuration ini file.")
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
                                    "\nandroid:              Qt 5.14:          android (optional)"
                                    "\n                      Qt 5.13 or below: android_x86_64, android_arm64_v8a"
                                    "\n                                        android_x86, android_armv7")
        install_parser.add_argument('-m', '--modules', nargs='*', help="Specify extra modules to install")
        install_parser.add_argument('-O', '--outputdir', nargs='?',
                                    help='Target output directory(default current directory)')
        install_parser.add_argument('-b', '--base', nargs='?',
                                    help="Specify mirror base url such as http://mirrors.ocf.berkeley.edu/qt/, "
                                         "where 'online' folder exist.")
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
            conf = os.path.join(os.path.dirname(__file__), 'logging.ini')
        logging.config.fileConfig(conf)
        if args.logger is not None:
            self.logger = logging.getLogger(args.logger)
        else:
            self.logger = logging.getLogger('aqt')

    def run(self, arg=None):
        args = self.parser.parse_args(arg)
        self._setup_logging(args)
        args.func(args)

    def asyncrun(self, arg):
        self.logger.debug("- Start execution {}...".format(arg))
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(arg)
        loop.run_until_complete(asyncio.sleep(0.250))
        self.logger.debug("- End execution {}...".format(arg))
        return result

    def make_conf_files(self, qt_version, arch, base_dir):
        """Make Qt configuration files, qt.conf and qtconfig.pri"""
        if arch.startswith('win64_mingw'):
            arch_dir = arch[6:] + '_64'
        elif arch.startswith('win32_mingw'):
            arch_dir = arch[6:] + '_32'
        elif arch.startswith('win'):
            arch_dir = arch[6:]
        else:
            arch_dir = arch

        if isinstance(base_dir, str):
            target_base = pathlib.Path(base_dir)
        elif isinstance(base_dir, pathlib.Path):
            target_base = base_dir
        else:
            target_base = pathlib.Path('.')
        try:
            # prepare qt.conf
            with target_base.joinpath(qt_version, arch_dir, 'bin', 'qt.conf').open('w') as f:
                f.write("[Paths]\n")
                f.write("Prefix=..\n")
            # update qtconfig.pri only as OpenSource
            with target_base.joinpath(qt_version, arch_dir, 'mkspecs', 'qconfig.pri').open('r+') as f:
                lines = f.readlines()
                f.seek(0)
                f.truncate()
                for line in lines:
                    if line.startswith('QT_EDITION ='):
                        line = 'QT_EDITION = OpenSource\n'
                    if line.startswith('QT_LICHECK ='):
                        line = 'QT_LICHECK =\n'
                    f.write(line)
        except IOError as e:
            self.logger.error("Configuration file generation error: %s\n", e.args, exc_info=True)
            raise e

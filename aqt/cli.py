#!/usr/bin/env python3
#
# Copyright (C) 2018 Linus Jahn <lnj@kaidan.im>
# Copyright (C) 2019-2020 Hiroshi Miura <miurahr@linux.com>
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
import logging
import logging.config
import os
import platform
import subprocess
import time

from packaging.version import Version, parse

from aqt.archives import (ArchiveDownloadError, ArchiveListError, QtArchives,
                          SrcDocExamplesArchives, ToolArchives)
from aqt.installer import QtInstaller
from aqt.settings import Settings

try:
    from importlib import metadata as importlib_metadata  # noqa
except ImportError:
    import importlib_metadata


class Cli():
    """CLI main class to parse command line argument and launch proper functions."""

    __slot__ = ['parser', 'combinations', 'logger']

    def __init__(self, env_key='AQT_CONFIG'):
        config = os.getenv(env_key, None)
        self.settings = Settings(config=config)
        self._create_parser()

    def _check_tools_arg_combination(self, os_name, tool_name, arch):
        for c in self.settings.tools_combinations:
            if c['os_name'] == os_name and c['tool_name'] == tool_name and c['arch'] == arch:
                return True
        return False

    def _check_qt_arg_combination(self, qt_version, os_name, target, arch):
        if qt_version.startswith('5.15.0') and os_name == 'windows' and target == 'desktop':
            if arch in ['win64_msvc2017_64', 'win32_msvc2017', 'win64_mingw73', 'win32_mingw73']:
                return False
        for c in self.settings.qt_combinations:
            if c['os_name'] == os_name and c['target'] == target and c['arch'] == arch:
                return True
        return False

    def _check_qt_arg_versions(self, qt_version):
        for ver in self.settings.available_versions:
            if ver == qt_version:
                return True
        return False

    def _set_sevenzip(self, args):
        sevenzip = args.external
        if sevenzip is None:
            return None

        try:
            subprocess.run([sevenzip, '--help'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError as e:
            raise Exception('Specified 7zip command executable does not exist: {!r}'.format(sevenzip)) from e

        return sevenzip

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
            pass
        elif mirror.startswith('http://') or mirror.startswith('https://') or mirror.startswith('ftp://'):
            pass
        else:
            return False
        return True

    def _check_modules_arg(self, qt_version, modules):
        if modules is None:
            return True
        available = self.settings.available_modules(qt_version)
        if available is None:
            return False
        return all([m in available for m in modules])

    def _run_common_part(self, output_dir=None, mirror=None):
        self.show_aqt_version()
        if output_dir is not None:
            output_dir = os.path.normpath(output_dir)
        if not self._check_mirror(mirror):
            self.parser.print_help()
            exit(1)

    def run_install(self, args):
        start_time = time.perf_counter()
        arch = args.arch
        target = args.target
        os_name = args.host
        qt_version = args.qt_version
        output_dir = args.outputdir
        arch = self._set_arch(args, arch, os_name, target, qt_version)
        modules = args.modules
        sevenzip = self._set_sevenzip(args)
        mirror = args.base
        archives = args.archives
        self._run_common_part(output_dir, mirror)
        if not self._check_qt_arg_versions(qt_version):
            self.logger.warning("Specified Qt version is unknown: {}.".format(qt_version))
        if not self._check_qt_arg_combination(qt_version, os_name, target, arch):
            self.logger.warning("Specified target combination is not valid or unknown: {} {} {}".format(os_name,
                                                                                                        target, arch))
        all_extra = True if modules is not None and 'all' in modules else False
        if not all_extra and not self._check_modules_arg(qt_version, modules):
            self.logger.warning("Some of specified modules are unknown.")
        try:
            qt_archives = QtArchives(os_name, target, qt_version, arch, subarchives=archives, modules=modules,
                                     mirror=mirror, logging=self.logger, all_extra=all_extra)
        except ArchiveDownloadError or ArchiveListError:
            exit(1)
        else:
            installer = QtInstaller(qt_archives, logging=self.logger, command=sevenzip, target_dir=output_dir)
            installer.install()
            installer.finalize()
        self.logger.info("Finished installation")
        self.logger.info("Time elasped: {time:.8f} second".format(time=time.perf_counter() - start_time))

    def _run_src_doc_examples(self, flavor, args):
        start_time = time.perf_counter()
        target = args.target
        os_name = args.host
        qt_version = args.qt_version
        output_dir = args.outputdir
        mirror = args.base
        sevenzip = self._set_sevenzip(args)
        if flavor in ['doc', 'examples']:
            modules = args.modules
            archives = args.archives
        else:
            modules = None
            archives = None
        self._run_common_part(output_dir, mirror)
        all_extra = True if modules is not None and 'all' in modules else False
        if not self._check_qt_arg_versions(qt_version):
            self.logger.warning("Specified Qt version is unknown: {}.".format(qt_version))
        try:
            srcdocexamples_archives = SrcDocExamplesArchives(flavor, os_name, target, qt_version, subarchives=archives,
                                                             modules=modules, mirror=mirror, logging=self.logger,
                                                             all_extra=all_extra)
        except ArchiveDownloadError or ArchiveListError:
            exit(1)
        else:
            installer = QtInstaller(srcdocexamples_archives, logging=self.logger, command=sevenzip,
                                    target_dir=output_dir)
            installer.install()
        self.logger.info("Finished installation")
        self.logger.info("Time elasped: {time:.8f} second".format(time=time.perf_counter() - start_time))

    def run_src(self, args):
        self._run_src_doc_examples('src', args)

    def run_examples(self, args):
        self._run_src_doc_examples('examples', args)

    def run_doc(self, args):
        self._run_src_doc_examples('doc', args)

    def run_tool(self, args):
        start_time = time.perf_counter()
        arch = args.arch
        tool_name = args.tool_name
        os_name = args.host
        output_dir = args.outputdir
        sevenzip = self._set_sevenzip(args)
        version = args.version
        mirror = args.base
        self._run_common_part(output_dir, mirror)
        if not self._check_tools_arg_combination(os_name, tool_name, arch):
            self.logger.warning("Specified target combination is not valid: {} {} {}".format(os_name, tool_name, arch))
        try:
            tool_archives = ToolArchives(os_name, tool_name, version, arch, mirror=mirror, logging=self.logger)
        except ArchiveDownloadError or ArchiveListError:
            exit(1)
        else:
            installer = QtInstaller(tool_archives, logging=self.logger, command=sevenzip, target_dir=output_dir)
            installer.install()
        self.logger.info("Finished installation")
        self.logger.info("Time elasped: {time:.8f} second".format(time=time.perf_counter() - start_time))

    def run_list(self, args):
        self.show_aqt_version()
        print('List Qt packages for %s' % args.qt_version)

    def show_help(self, args):
        self.parser.print_help()

    def show_aqt_version(self):
        dist = importlib_metadata.distribution('aqtinstall')
        module_name = dist.entry_points[0].name
        py_version = platform.python_version()
        py_impl = platform.python_implementation()
        py_build = platform.python_compiler()
        self.logger.info("aqtinstall({}) v{} on Python {} [{} {}]".format(module_name, dist.version,
                                                                          py_version, py_impl, py_build))

    def _set_common_options(self, subparser):
        subparser.add_argument('-O', '--outputdir', nargs='?',
                               help='Target output directory(default current directory)')
        subparser.add_argument('-b', '--base', nargs='?',
                               help="Specify mirror base url such as http://mirrors.ocf.berkeley.edu/qt/, "
                                    "where 'online' folder exist.")
        subparser.add_argument('-E', '--external', nargs='?', help='Specify external 7zip command path.')
        subparser.add_argument('--internal', action='store_true', help='Use internal extractor.')

    def _set_module_options(self, subparser):
        subparser.add_argument('-m', '--modules', nargs='*', help="Specify extra modules to install")
        subparser.add_argument('--archives', nargs='*',
                               help="Specify subset modules to install(Default: all standard modules).")

    def _set_common_argument(self, subparser):
        subparser.add_argument("qt_version", help="Qt version in the format of \"5.X.Y\"")
        subparser.add_argument('host', choices=['linux', 'mac', 'windows'], help="host os name")
        subparser.add_argument('target', choices=['desktop', 'winrt', 'android', 'ios'], help="target sdk")

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
        self._set_common_argument(install_parser)
        self._set_common_options(install_parser)
        install_parser.add_argument('arch', nargs='?', help="\ntarget linux/desktop: gcc_64, wasm_32"
                                    "\ntarget mac/desktop:   clang_64, wasm_32"
                                    "\ntarget mac/ios:       ios"
                                    "\nwindows/desktop:      win64_msvc2019_64, win32_msvc2019"
                                    "\n                      win64_msvc2017_64, win32_msvc2017"
                                    "\n                      win64_msvc2015_64, win32_msvc2015"
                                    "\n                      win64_mingw73, win32_mingw73"
                                    "\n                      win32_mingw53"
                                    "\n                      wasm_32"
                                    "\nwindows/winrt:        win64_msvc2019_winrt_x64, win64_msvc2019_winrt_x86"
                                    "\n                      win64_msvc2017_winrt_x64, win64_msvc2017_winrt_x86"
                                    "\n                      win64_msvc2019_winrt_armv7"
                                    "\n                      win64_msvc2017_winrt_armv7"
                                    "\nandroid:              Qt 5.14:          android (optional)"
                                    "\n                      Qt 5.13 or below: android_x86_64, android_arm64_v8a"
                                    "\n                                        android_x86, android_armv7")
        self._set_module_options(install_parser)
        #
        doc_parser = subparsers.add_parser('doc')
        doc_parser.set_defaults(func=self.run_doc)
        self._set_common_argument(doc_parser)
        self._set_common_options(doc_parser)
        self._set_module_options(doc_parser)
        #
        examples_parser = subparsers.add_parser('examples')
        examples_parser.set_defaults(func=self.run_examples)
        self._set_common_argument(examples_parser)
        self._set_common_options(examples_parser)
        self._set_module_options(examples_parser)
        #
        src_parser = subparsers.add_parser('src')
        src_parser.set_defaults(func=self.run_src)
        self._set_common_argument(src_parser)
        self._set_common_options(src_parser)
        #
        tools_parser = subparsers.add_parser('tool')
        tools_parser.set_defaults(func=self.run_tool)
        tools_parser.add_argument('host', choices=['linux', 'mac', 'windows'], help="host os name")
        tools_parser.add_argument('tool_name', help="Name of tool such as tools_ifw, tools_mingw")
        tools_parser.add_argument("version", help="Tool version in the format of \"4.1.2\"")
        tools_parser.add_argument('arch', help="Name of full tool name such as qt.tools.ifw.31")
        self._set_common_options(tools_parser)
        #
        list_parser = subparsers.add_parser('list')
        list_parser.set_defaults(func=self.run_list)
        list_parser.add_argument("qt_version", help="Qt version in the format of \"5.X.Y\"")
        help_parser = subparsers.add_parser('help')
        help_parser.set_defaults(func=self.show_help)
        parser.set_defaults(func=self.show_help)
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
        return args.func(args)

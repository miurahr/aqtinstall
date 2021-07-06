#!/usr/bin/env python3
#
# Copyright (C) 2018 Linus Jahn <lnj@kaidan.im>
# Copyright (C) 2019-2021 Hiroshi Miura <miurahr@linux.com>
# Copyright (C) 2020, Aurélien Gâteau
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
import binascii
import multiprocessing
import os
import platform
import random
import subprocess
import time
from logging import getLogger
from logging.handlers import QueueHandler

from semantic_version import Version

import aqt
from aqt.archives import ListCommand, QtArchives, SrcDocExamplesArchives, ToolArchives
from aqt.exceptions import (
    ArchiveConnectionError,
    ArchiveDownloadError,
    ArchiveListError,
    NoPackageFound,
)
from aqt.helper import (
    ArchiveId,
    MyQueueListener,
    Settings,
    downloadBinaryFile,
    getUrl,
    setup_logging,
)
from aqt.updater import Updater

try:
    import py7zr

    EXT7Z = False
except ImportError:
    EXT7Z = True


class ExtractionError(Exception):
    pass


class Cli:
    """CLI main class to parse command line argument and launch proper functions."""

    __slot__ = ["parser", "combinations", "logger"]

    def __init__(self):
        self._create_parser()

    def _check_tools_arg_combination(self, os_name, tool_name, arch):
        for c in Settings.tools_combinations:
            if (
                c["os_name"] == os_name
                and c["tool_name"] == tool_name
                and c["arch"] == arch
            ):
                return True
        return False

    def _check_qt_arg_combination(self, qt_version, os_name, target, arch):
        if os_name == "windows" and target == "desktop":
            major_minor = qt_version[: qt_version.rfind(".")]
            # check frequent mistakes
            if major_minor in ["5.15", "6.0", "6.1"]:
                if arch in [
                    "win64_msvc2017_64",
                    "win32_msvc2017",
                    "win64_mingw73",
                    "win32_mingw73",
                ]:
                    return False
            elif major_minor in ["5.9", "5.10", "5.11"]:
                if arch in [
                    "win64_mingw73",
                    "win32_mingw73",
                    "win64_mingw81",
                    "win32_mingw81",
                ]:
                    return False
            elif arch in [
                "win64_msvc2019_64",
                "win32_msvc2019",
                "win64_mingw81",
                "win32_mingw81",
            ]:
                return False
        for c in Settings.qt_combinations:
            if c["os_name"] == os_name and c["target"] == target and c["arch"] == arch:
                return True
        return False

    def _check_qt_arg_versions(self, version):
        return version in Settings.available_versions

    def _check_qt_arg_version_offline(self, version):
        return version in Settings.available_offline_installer_version

    def _set_sevenzip(self, external):
        sevenzip = external
        if sevenzip is None:
            return None

        try:
            subprocess.run(
                [sevenzip, "--help"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as e:
            raise Exception(
                "Specified 7zip command executable does not exist: {!r}".format(
                    sevenzip
                )
            ) from e

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
            elif target == "android" and Version(qt_version) >= Version("5.14.0"):
                arch = "android"
            else:
                print("Please supply a target architecture.")
                self.show_help(args)
                exit(1)
        if arch == "":
            print("Please supply a target architecture.")
            self.show_help(args)
            exit(1)
        return arch

    def _check_mirror(self, mirror):
        if mirror is None:
            pass
        elif (
            mirror.startswith("http://")
            or mirror.startswith("https://")
            or mirror.startswith("ftp://")
        ):
            pass
        else:
            return False
        return True

    def _check_modules_arg(self, qt_version, modules):
        if modules is None:
            return True
        available = Settings.available_modules(qt_version)
        if available is None:
            return False
        return all([m in available for m in modules])

    def run_install(self, args):
        """Run install subcommand"""
        start_time = time.perf_counter()
        self.show_aqt_version()
        arch = args.arch
        target = args.target
        os_name = args.host
        qt_version = args.qt_version
        self._validate_version_str(qt_version)
        keep = args.keep
        output_dir = args.outputdir
        if output_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = output_dir
        if args.timeout is not None:
            timeout = (args.timeout, args.timeout)
        else:
            timeout = (Settings.connection_timeout, Settings.response_timeout)
        arch = self._set_arch(args, arch, os_name, target, qt_version)
        modules = args.modules
        sevenzip = self._set_sevenzip(args.external)
        if EXT7Z and sevenzip is None:
            # override when py7zr is not exist
            sevenzip = self._set_sevenzip("7z")
        if args.base is not None:
            if not self._check_mirror(args.base):
                self.show_help()
                exit(1)
            base = args.base
        else:
            base = Settings.baseurl
        archives = args.archives
        if args.noarchives:
            if modules is None:
                print(
                    "When specified option --no-archives, an option --modules is mandatory."
                )
                exit(1)
            if archives is not None:
                print(
                    "Option --archives and --no-archives  are conflicted. Aborting..."
                )
                exit(1)
            else:
                archives = modules
        else:
            if modules is not None and archives is not None:
                archives.append(modules)
        nopatch = args.noarchives or (
            archives is not None and "qtbase" not in archives
        )  # type: bool
        if not self._check_qt_arg_versions(qt_version):
            self.logger.warning(
                "Specified Qt version is unknown: {}.".format(qt_version)
            )
        if not self._check_qt_arg_combination(qt_version, os_name, target, arch):
            self.logger.warning(
                "Specified target combination is not valid or unknown: {} {} {}".format(
                    os_name, target, arch
                )
            )
        all_extra = True if modules is not None and "all" in modules else False
        if not all_extra and not self._check_modules_arg(qt_version, modules):
            self.logger.warning("Some of specified modules are unknown.")
        try:
            qt_archives = QtArchives(
                os_name,
                target,
                qt_version,
                arch,
                base,
                subarchives=archives,
                modules=modules,
                all_extra=all_extra,
                timeout=timeout,
            )
        except ArchiveConnectionError:
            try:
                self.logger.warning(
                    "Connection to the download site failed and fallback to mirror site."
                )
                qt_archives = QtArchives(
                    os_name,
                    target,
                    qt_version,
                    arch,
                    random.choice(Settings.fallbacks),
                    subarchives=archives,
                    modules=modules,
                    all_extra=all_extra,
                    timeout=timeout,
                )
            except Exception:
                self.logger.error("Connection to the download site failed. Aborted...")
                exit(1)
        except ArchiveDownloadError or ArchiveListError or NoPackageFound:
            exit(1)
        target_config = qt_archives.get_target_config()
        self.call_installer(qt_archives, base_dir, sevenzip, keep)
        if not nopatch:
            Updater.update(target_config, base_dir)
        self.logger.info("Finished installation")
        self.logger.info(
            "Time elapsed: {time:.8f} second".format(
                time=time.perf_counter() - start_time
            )
        )

    def _run_src_doc_examples(self, flavor, args):
        self.show_aqt_version()
        target = args.target
        os_name = args.host
        qt_version = args.qt_version
        self._validate_version_str(qt_version)
        output_dir = args.outputdir
        if output_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = output_dir
        keep = args.keep
        if args.base is not None:
            base = args.base
        else:
            base = Settings.baseurl
        if args.timeout is not None:
            timeout = (args.timeout, args.timeout)
        else:
            timeout = (Settings.connection_timeout, Settings.response_timeout)
        sevenzip = self._set_sevenzip(args.external)
        if EXT7Z and sevenzip is None:
            # override when py7zr is not exist
            sevenzip = self._set_sevenzip(Settings.zipcmd)
        modules = args.modules
        archives = args.archives
        all_extra = True if modules is not None and "all" in modules else False
        if not self._check_qt_arg_versions(qt_version):
            self.logger.warning(
                "Specified Qt version is unknown: {}.".format(qt_version)
            )
        try:
            srcdocexamples_archives = SrcDocExamplesArchives(
                flavor,
                os_name,
                target,
                qt_version,
                base,
                subarchives=archives,
                modules=modules,
                all_extra=all_extra,
                timeout=timeout,
            )
        except ArchiveConnectionError:
            try:
                self.logger.warning(
                    "Connection to the download site failed and fallback to mirror site."
                )
                srcdocexamples_archives = SrcDocExamplesArchives(
                    flavor,
                    os_name,
                    target,
                    qt_version,
                    random.choice(Settings.fallbacks),
                    subarchives=archives,
                    modules=modules,
                    all_extra=all_extra,
                    timeout=timeout,
                )
            except Exception:
                self.logger.error("Connection to the download site failed. Aborted...")
                exit(1)
        except ArchiveDownloadError or ArchiveListError:
            exit(1)
        self.call_installer(srcdocexamples_archives, base_dir, sevenzip, keep)
        self.logger.info("Finished installation")

    def run_src(self, args):
        """Run src subcommand"""
        if args.kde:
            if args.qt_version != "5.15.2":
                print("KDE patch: unsupported version!!")
                exit(1)
        start_time = time.perf_counter()
        self._run_src_doc_examples("src", args)
        if args.kde:
            if args.outputdir is None:
                target_dir = os.path.join(os.getcwd(), args.qt_version, "Src")
            else:
                target_dir = os.path.join(args.outputdir, args.qt_version, "Src")
            Updater.patch_kde(target_dir)
        self.logger.info(
            "Time elapsed: {time:.8f} second".format(
                time=time.perf_counter() - start_time
            )
        )

    def run_examples(self, args):
        """Run example subcommand"""
        start_time = time.perf_counter()
        self._run_src_doc_examples("examples", args)
        self.logger.info(
            "Time elapsed: {time:.8f} second".format(
                time=time.perf_counter() - start_time
            )
        )

    def run_doc(self, args):
        """Run doc subcommand"""
        start_time = time.perf_counter()
        self._run_src_doc_examples("doc", args)
        self.logger.info(
            "Time elapsed: {time:.8f} second".format(
                time=time.perf_counter() - start_time
            )
        )

    def run_tool(self, args):
        """Run tool subcommand"""
        start_time = time.perf_counter()
        self.show_aqt_version()
        arch = args.arch
        tool_name = args.tool_name
        os_name = args.host
        output_dir = args.outputdir
        if output_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = output_dir
        sevenzip = self._set_sevenzip(args.external)
        if EXT7Z and sevenzip is None:
            # override when py7zr is not exist
            sevenzip = self._set_sevenzip(Settings.zipcmd)
        version = args.version
        keep = args.keep
        if args.base is not None:
            base = args.base
        else:
            base = Settings.baseurl
        if args.timeout is not None:
            timeout = (args.timeout, args.timeout)
        else:
            timeout = (Settings.connection_timeout, Settings.response_timeout)
        if not self._check_tools_arg_combination(os_name, tool_name, arch):
            self.logger.warning(
                "Specified target combination is not valid: {} {} {}".format(
                    os_name, tool_name, arch
                )
            )

        try:
            tool_archives = ToolArchives(
                os_name=os_name,
                tool_name=tool_name,
                base=base,
                version_str=version,
                arch=arch,
                timeout=timeout,
            )
        except ArchiveConnectionError:
            try:
                self.logger.warning(
                    "Connection to the download site failed and fallback to mirror site."
                )
                tool_archives = ToolArchives(
                    os_name=os_name,
                    tool_name=tool_name,
                    base=random.choice(Settings.fallbacks),
                    version_str=version,
                    arch=arch,
                    timeout=timeout,
                )
            except Exception:
                self.logger.error("Connection to the download site failed. Aborted...")
                exit(1)
        except ArchiveDownloadError or ArchiveListError:
            exit(1)
        self.call_installer(tool_archives, base_dir, sevenzip, keep)
        self.logger.info("Finished installation")
        self.logger.info(
            "Time elapsed: {time:.8f} second".format(
                time=time.perf_counter() - start_time
            )
        )

    def run_list(self, args: argparse.ArgumentParser) -> int:
        """Print tools, versions of Qt, extensions, modules, architectures"""

        if not args.target:
            print(" ".join(ArchiveId.TARGETS_FOR_HOST[args.host]))
            return 0
        if args.target not in ArchiveId.TARGETS_FOR_HOST[args.host]:
            self.logger.error(
                "'{0.target}' is not a valid target for host '{0.host}'".format(args)
            )
            return 1
        command = ListCommand(
            archive_id=ArchiveId(
                args.category,
                args.host,
                args.target,
                args.extension if args.extension else "",
            ),
            filter_minor=args.filter_minor,
            is_latest_version=args.latest_version,
            modules_ver=args.modules,
            extensions_ver=args.extensions,
            architectures_ver=args.arch,
            tool_name=args.tool,
        )
        return command.run()

    def _make_list_parser(self, subparsers: argparse._SubParsersAction):
        """Creates a subparser that works with the ListCommand, and adds it to the `subparsers` parameter"""
        list_parser: argparse.ArgumentParser = subparsers.add_parser(
            "list",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="Examples:\n"
            "$ aqt list qt5 mac                                            # print all targets for Mac OS\n"
            "$ aqt list tools mac desktop                                  # print all tools for mac desktop\n"
            "$ aqt list tools mac desktop --tool tools_ifw                 # print all tool variant names for QtIFW\n"
            "$ aqt list qt5 mac desktop                                    # print all versions of Qt 5\n"
            "$ aqt list qt5 mac desktop --extension wasm                   # print all wasm versions of Qt 5\n"
            "$ aqt list qt5 mac desktop --filter-minor 9                   # print all versions of Qt 5.9\n"
            "$ aqt list qt5 mac desktop --filter-minor 9 --latest-version  # print latest Qt 5.9\n"
            "$ aqt list qt5 mac desktop --modules 5.12.0                   # print modules for 5.12.0\n"
            "$ aqt list qt5 mac desktop --filter-minor 9 --modules latest  # print modules for latest 5.9\n"
            "$ aqt list qt5 mac desktop --extensions 5.9.0                 # print choices for --extension flag\n"
            "$ aqt list qt5 mac desktop --arch 5.9.9                       "
            "# print architectures for 5.9.9/mac/desktop\n"
            "$ aqt list qt5 mac desktop --arch latest                      "
            "# print architectures for the latest Qt 5\n",
        )
        list_parser.add_argument(
            "category",
            choices=["tools", "qt5", "qt6"],
            help="category of packages to list",
        )
        list_parser.add_argument(
            "host", choices=["linux", "mac", "windows"], help="host os name"
        )
        list_parser.add_argument(
            "target",
            nargs="?",
            default=None,
            choices=["desktop", "winrt", "android", "ios"],
            help="Target SDK. When omitted, this prints all the targets available for a host OS.",
        )
        list_parser.add_argument(
            "--extension",
            choices=ArchiveId.ALL_EXTENSIONS,
            help="Extension of packages to list. "
            "Use the `--extensions` flag to list all relevant options for a host/target.",
        )
        list_parser.add_argument(
            "--filter-minor",
            type=int,
            metavar="MINOR_VERSION",
            help="print versions for a particular minor version. "
            "IE: `aqt list qt5 windows desktop --filter-minor 12` prints all versions beginning with 5.12",
        )
        output_modifier_exclusive_group = list_parser.add_mutually_exclusive_group()
        output_modifier_exclusive_group.add_argument(
            "--modules",
            type=str,
            metavar="(VERSION | latest)",
            help='Qt version in the format of "5.X.Y", or the keyword "latest". '
            "When set, this prints all the modules available for either Qt 5.X.Y or the latest version of Qt.",
        )
        output_modifier_exclusive_group.add_argument(
            "--extensions",
            type=str,
            metavar="(VERSION | latest)",
            help='Qt version in the format of "5.X.Y", or the keyword "latest". '
            "When set, this prints all valid arguments for the `--extension` flag "
            "for either Qt 5.X.Y or the latest version of Qt.",
        )
        output_modifier_exclusive_group.add_argument(
            "--arch",
            type=str,
            metavar="(VERSION | latest)",
            help='Qt version in the format of "5.X.Y", or the keyword "latest". '
            "When set, this prints all architectures available for either Qt 5.X.Y or the latest version of Qt.",
        )
        output_modifier_exclusive_group.add_argument(
            "--latest-version",
            action="store_true",
            help="print only the newest version available",
        )
        output_modifier_exclusive_group.add_argument(
            "--tool",
            type=str,
            metavar="TOOL_NAME",
            help="The name of a tool. Use 'aqt list tools <host> <target>' to see accepted values. "
            "This flag only works with the 'tools' category, and cannot be combined with any other flags. "
            "When set, this prints all 'tool variant names' available. "
            # TODO: find a better word ^^^^^^^^^^^^^^^^^^^^; this is a mysterious help message
            "The output of this command is intended to be used with `aqt tool`.",
        )
        list_parser.set_defaults(func=self.run_list)

    def show_help(self, args=None):
        """Display help message"""
        self.parser.print_help()

    def show_aqt_version(self, args=None):
        """Display version information"""
        py_version = platform.python_version()
        py_impl = platform.python_implementation()
        py_build = platform.python_compiler()
        self.logger.info(
            "aqtinstall(aqt) v{} on Python {} [{} {}]".format(
                aqt.__version__, py_version, py_impl, py_build
            )
        )

    def _set_common_options(self, subparser):
        subparser.add_argument(
            "-O",
            "--outputdir",
            nargs="?",
            help="Target output directory(default current directory)",
        )
        subparser.add_argument(
            "-b",
            "--base",
            nargs="?",
            help="Specify mirror base url such as http://mirrors.ocf.berkeley.edu/qt/, "
            "where 'online' folder exist.",
        )
        subparser.add_argument(
            "--timeout",
            nargs="?",
            type=float,
            help="Specify connection timeout for download site.(default: 5 sec)",
        )
        subparser.add_argument(
            "-E", "--external", nargs="?", help="Specify external 7zip command path."
        )
        subparser.add_argument(
            "--internal", action="store_true", help="Use internal extractor."
        )
        subparser.add_argument(
            "-k",
            "--keep",
            action="store_true",
            help="Keep downloaded archive when specified, otherwise remove after install",
        )

    def _set_module_options(self, subparser):
        subparser.add_argument(
            "-m", "--modules", nargs="*", help="Specify extra modules to install"
        )
        subparser.add_argument(
            "--archives",
            nargs="*",
            help="Specify subset packages to install (Default: all standard and extra modules).",
        )

    def _set_common_argument(self, subparser):
        subparser.add_argument("qt_version", help='Qt version in the format of "5.X.Y"')
        subparser.add_argument(
            "host", choices=["linux", "mac", "windows"], help="host os name"
        )
        subparser.add_argument(
            "target", choices=["desktop", "winrt", "android", "ios"], help="target sdk"
        )

    def _create_parser(self):
        parser = argparse.ArgumentParser(
            prog="aqt",
            description="Installer for Qt SDK.",
            formatter_class=argparse.RawTextHelpFormatter,
            add_help=True,
        )
        parser.add_argument(
            "-c",
            "--config",
            type=argparse.FileType("r"),
            help="Configuration ini file.",
        )
        subparsers = parser.add_subparsers(
            title="subcommands",
            description="Valid subcommands",
            help="subcommand for aqt Qt installer",
        )
        install_parser = subparsers.add_parser(
            "install", formatter_class=argparse.RawTextHelpFormatter
        )
        install_parser.set_defaults(func=self.run_install)
        self._set_common_argument(install_parser)
        self._set_common_options(install_parser)
        install_parser.add_argument(
            "arch",
            nargs="?",
            help="\ntarget linux/desktop: gcc_64, wasm_32"
            "\ntarget mac/desktop:   clang_64, wasm_32"
            "\ntarget mac/ios:       ios"
            "\nwindows/desktop:      win64_msvc2019_64, win32_msvc2019"
            "\n                      win64_msvc2017_64, win32_msvc2017"
            "\n                      win64_msvc2015_64, win32_msvc2015"
            "\n                      win64_mingw81, win32_mingw81"
            "\n                      win64_mingw73, win32_mingw73"
            "\n                      win32_mingw53"
            "\n                      wasm_32"
            "\nwindows/winrt:        win64_msvc2019_winrt_x64, win64_msvc2019_winrt_x86"
            "\n                      win64_msvc2017_winrt_x64, win64_msvc2017_winrt_x86"
            "\n                      win64_msvc2019_winrt_armv7"
            "\n                      win64_msvc2017_winrt_armv7"
            "\nandroid:              Qt 5.14:          android (optional)"
            "\n                      Qt 5.13 or below: android_x86_64, android_arm64_v8a"
            "\n                                        android_x86, android_armv7",
        )
        self._set_module_options(install_parser)
        install_parser.add_argument(
            "--noarchives",
            action="store_true",
            help="No base packages; allow mod amendment with --modules option.",
        )
        #
        doc_parser = subparsers.add_parser("doc")
        doc_parser.set_defaults(func=self.run_doc)
        self._set_common_argument(doc_parser)
        self._set_common_options(doc_parser)
        self._set_module_options(doc_parser)
        #
        examples_parser = subparsers.add_parser("examples")
        examples_parser.set_defaults(func=self.run_examples)
        self._set_common_argument(examples_parser)
        self._set_common_options(examples_parser)
        self._set_module_options(examples_parser)
        #
        src_parser = subparsers.add_parser("src")
        src_parser.set_defaults(func=self.run_src)
        self._set_common_argument(src_parser)
        self._set_common_options(src_parser)
        self._set_module_options(src_parser)
        src_parser.add_argument(
            "--kde", action="store_true", help="patching with KDE patch kit."
        )
        #
        tools_parser = subparsers.add_parser("tool")
        tools_parser.set_defaults(func=self.run_tool)
        tools_parser.add_argument(
            "host", choices=["linux", "mac", "windows"], help="host os name"
        )
        tools_parser.add_argument(
            "tool_name", help="Name of tool such as tools_ifw, tools_mingw"
        )
        tools_parser.add_argument(
            "version", help='Tool version in the format of "4.1.2"'
        )
        tools_parser.add_argument(
            "arch",
            help="Name of full tool name such as qt.tools.ifw.31. "
            "Please use 'aqt list --tool' to list acceptable values for this parameter.",
        )
        self._set_common_options(tools_parser)

        self._make_list_parser(subparsers)
        #
        help_parser = subparsers.add_parser("help")
        help_parser.set_defaults(func=self.show_help)
        #
        version_parser = subparsers.add_parser("version")
        version_parser.set_defaults(func=self.show_aqt_version)
        parser.set_defaults(func=self.show_help)
        self.parser = parser

    def _setup_settings(self, args=None):
        # setup logging
        setup_logging()
        self.logger = getLogger("aqt.main")
        # setup settings
        if args is not None and args.config is not None:
            Settings.load_settings(args.config)
        else:
            config = os.getenv("AQT_CONFIG", None)
            if config is not None and os.path.exists(config):
                Settings.load_settings(config)
                self.logger.debug("Load configuration from {}".format(config))
            else:
                Settings.load_settings()

    def run(self, arg=None):
        args = self.parser.parse_args(arg)
        self._setup_settings(args)
        result = args.func(args)
        return result

    def call_installer(self, qt_archives, base_dir, sevenzip, keep):
        queue = multiprocessing.Manager().Queue(-1)
        listener = MyQueueListener(queue)
        listener.start()
        #
        tasks = []
        for arc in qt_archives.get_archives():
            tasks.append((arc, base_dir, sevenzip, queue, keep))
        ctx = multiprocessing.get_context("spawn")
        pool = ctx.Pool(Settings.concurrency)
        pool.starmap(installer, tasks)
        #
        pool.close()
        pool.join()
        # all done, close logging service for sub-processes
        listener.enqueue_sentinel()
        listener.stop()

    def _validate_version_str(self, version_str: str) -> None:
        try:
            Version(version_str)
        except ValueError:
            self.logger.error(
                "Invalid version: '{}'! Please use the form '5.X.Y'.".format(
                    version_str
                )
            )
            exit(1)


def installer(qt_archive, base_dir, command, queue, keep=False, response_timeout=None):
    """
    Installer function to download archive files and extract it.
    It is called through multiprocessing.Pool()
    """
    name = qt_archive.name
    url = qt_archive.url
    hashurl = qt_archive.hashurl
    archive = qt_archive.archive
    start_time = time.perf_counter()
    # set defaults
    Settings.load_settings()
    # set logging
    setup_logging()  # XXX: why need to load again?
    qh = QueueHandler(queue)
    logger = getLogger()
    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)
    logger.addHandler(qh)
    #
    logger.info("Downloading {}...".format(name))
    logger.debug("Download URL: {}".format(url))
    if response_timeout is None:
        timeout = (Settings.connection_timeout, Settings.response_timeout)
    else:
        timeout = (Settings.connection_timeout, response_timeout)
    hash = binascii.unhexlify(getUrl(hashurl, timeout))
    downloadBinaryFile(url, archive, "sha1", hash, timeout)
    if command is None:
        with py7zr.SevenZipFile(archive, "r") as szf:
            szf.extractall(path=base_dir)
    else:
        if base_dir is not None:
            command_args = [
                command,
                "x",
                "-aoa",
                "-bd",
                "-y",
                "-o{}".format(base_dir),
                archive,
            ]
        else:
            command_args = [command, "x", "-aoa", "-bd", "-y", archive]
        try:
            proc = subprocess.run(command_args, stdout=subprocess.PIPE, check=True)
            logger.debug(proc.stdout)
        except subprocess.CalledProcessError as cpe:
            logger.error("Extraction error: %d" % cpe.returncode)
            if cpe.stdout is not None:
                logger.error(cpe.stdout)
            if cpe.stderr is not None:
                logger.error(cpe.stderr)
            raise cpe
    if not keep:
        os.unlink(archive)
    logger.info(
        "Finished installation of {} in {:.8f}".format(
            archive, time.perf_counter() - start_time
        )
    )
    qh.flush()
    qh.close()
    logger.removeHandler(qh)

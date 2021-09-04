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
import signal
import subprocess
import time
from logging import getLogger
from logging.handlers import QueueHandler
from typing import List, Optional

import aqt
from aqt.archives import QtArchives, QtPackage, SrcDocExamplesArchives, ToolArchives
from aqt.exceptions import ArchiveConnectionError, ArchiveDownloadError, ArchiveListError, NoPackageFound
from aqt.helper import MyQueueListener, Settings, downloadBinaryFile, getUrl, setup_logging
from aqt.metadata import ArchiveId, MetadataFactory, SimpleSpec, Version, show_list
from aqt.updater import Updater

try:
    import py7zr

    EXT7Z = False
except ImportError:
    EXT7Z = True


class Cli:
    """CLI main class to parse command line argument and launch proper functions."""

    __slot__ = ["parser", "combinations", "logger"]

    def __init__(self):
        parser = argparse.ArgumentParser(
            prog="aqt",
            description="Another unofficial Qt Installer.\n" "aqt helps you install Qt SDK, tools, examples and others\n",
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
            description="aqt accepts several subcommands:\n"
            "install-* subcommands are commands that install components\n"
            "list-* subcommands are commands that show available components\n\n"
            "commands {install|tool|src|examples|doc} are deprecated and marked for removal\n",
            help="Please refer to each help message by using '--help' with each subcommand",
        )
        self._make_install_parsers(subparsers)
        self._make_list_qt_parser(subparsers)
        self._make_list_tool_parser(subparsers)
        self._make_legacy_parsers(subparsers)
        self._make_common_parsers(subparsers)
        parser.set_defaults(func=self.show_help)
        self.parser = parser

    def run(self, arg=None):
        args = self.parser.parse_args(arg)
        self._setup_settings(args)
        result = args.func(args)
        return result

    def _check_tools_arg_combination(self, os_name, tool_name, arch):
        for c in Settings.tools_combinations:
            if c["os_name"] == os_name and c["tool_name"] == tool_name and c["arch"] == arch:
                return True
        return False

    def _check_qt_arg_combination(self, qt_version, os_name, target, arch):
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
            raise Exception("Specified 7zip command executable does not exist: {!r}".format(sevenzip)) from e

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
        elif mirror.startswith("http://") or mirror.startswith("https://") or mirror.startswith("ftp://"):
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

    def run_install_qt(self, args):
        """Run install subcommand"""
        start_time = time.perf_counter()
        self.show_aqt_version()
        if args.is_legacy:
            self._warn_on_deprecated_command("install", "install-qt")
        arch = args.arch
        target = args.target
        os_name = args.host
        qt_version = args.qt_version
        if not Cli._is_valid_version_str(qt_version):
            self.logger.error("Invalid version: '{}'! Please use the form '5.X.Y'.".format(qt_version))
            exit(1)
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
                print("When specified option --no-archives, an option --modules is mandatory.")
                exit(1)
            if archives is not None:
                print("Option --archives and --no-archives  are conflicted. Aborting...")
                exit(1)
            else:
                archives = modules
        else:
            if modules is not None and archives is not None:
                archives.append(modules)
        nopatch = args.noarchives or (archives is not None and "qtbase" not in archives)  # type: bool
        if not self._check_qt_arg_versions(qt_version):
            self.logger.warning("Specified Qt version is unknown: {}.".format(qt_version))
        if not self._check_qt_arg_combination(qt_version, os_name, target, arch):
            self.logger.warning(
                "Specified target combination is not valid or unknown: {} {} {}".format(os_name, target, arch)
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
                self.logger.warning("Connection to the download site failed and fallback to mirror site.")
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
        except (ArchiveDownloadError, ArchiveListError, NoPackageFound):
            exit(1)
        target_config = qt_archives.get_target_config()
        result = run_installer(qt_archives.get_packages(), base_dir, sevenzip, keep)
        if not result:
            exit(1)
        if not nopatch:
            Updater.update(target_config, base_dir)
        self.logger.info("Finished installation")
        self.logger.info("Time elapsed: {time:.8f} second".format(time=time.perf_counter() - start_time))

    def _run_src_doc_examples(self, flavor, args, cmd_name: Optional[str] = None):
        if not cmd_name:
            cmd_name = flavor

        self.show_aqt_version()
        if args.is_legacy:
            self._warn_on_deprecated_command(old_name=cmd_name, new_name=f"install-{cmd_name}")
        target = args.target
        os_name = args.host
        qt_version = args.qt_version
        if not Cli._is_valid_version_str(qt_version):
            self.logger.error("Invalid version: '{}'! Please use the form '5.X.Y'.".format(qt_version))
            exit(1)
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
            self.logger.warning("Specified Qt version is unknown: {}.".format(qt_version))
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
                self.logger.warning("Connection to the download site failed and fallback to mirror site.")
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
        except (ArchiveDownloadError, ArchiveListError, NoPackageFound):
            exit(1)
        result = run_installer(srcdocexamples_archives.get_packages(), base_dir, sevenzip, keep)
        if result:
            self.logger.info("Finished installation")
        else:
            exit(1)

    def run_install_src(self, args):
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
        self.logger.info("Time elapsed: {time:.8f} second".format(time=time.perf_counter() - start_time))

    def run_install_example(self, args):
        """Run example subcommand"""
        start_time = time.perf_counter()
        self._run_src_doc_examples("examples", args, cmd_name="example")
        self.logger.info("Time elapsed: {time:.8f} second".format(time=time.perf_counter() - start_time))

    def run_install_doc(self, args):
        """Run doc subcommand"""
        start_time = time.perf_counter()
        self._run_src_doc_examples("doc", args)
        self.logger.info("Time elapsed: {time:.8f} second".format(time=time.perf_counter() - start_time))

    def run_install_tool(self, args):
        """Run tool subcommand"""
        start_time = time.perf_counter()
        self.show_aqt_version()
        if args.is_legacy:
            self._warn_on_deprecated_command("tool", "install-tool")
        tool_name = args.tool_name  # such as tools_openssl_x64
        os_name = args.host  # windows, linux and mac
        target = args.target  # desktop, android and ios
        output_dir = args.outputdir
        if output_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = output_dir
        sevenzip = self._set_sevenzip(args.external)
        if EXT7Z and sevenzip is None:
            # override when py7zr is not exist
            sevenzip = self._set_sevenzip(Settings.zipcmd)
        version = "0.0.1"  # just store a dummy version
        keep = args.keep
        if args.base is not None:
            base = args.base
        else:
            base = Settings.baseurl
        if args.timeout is not None:
            timeout = (args.timeout, args.timeout)
        else:
            timeout = (Settings.connection_timeout, Settings.response_timeout)
        if args.arch is None:
            archs = MetadataFactory(
                archive_id=ArchiveId("tools", os_name, target, ""),
                is_latest_version=True,
                tool_name=tool_name,
            ).getList()
        else:
            archs = [args.arch]

        for arch in archs:
            if not self._check_tools_arg_combination(os_name, tool_name, arch):
                self.logger.warning("Specified target combination is not valid: {} {} {}".format(os_name, tool_name, arch))

            try:
                tool_archives = ToolArchives(
                    os_name=os_name,
                    tool_name=tool_name,
                    target=target,
                    base=base,
                    version_str=version,
                    arch=arch,
                    timeout=timeout,
                )
            except ArchiveConnectionError:
                try:
                    self.logger.warning("Connection to the download site failed and fallback to mirror site.")
                    tool_archives = ToolArchives(
                        os_name=os_name,
                        target=target,
                        tool_name=tool_name,
                        base=random.choice(Settings.fallbacks),
                        version_str=version,
                        arch=arch,
                        timeout=timeout,
                    )
                except Exception:
                    self.logger.error("Connection to the download site failed. Aborted...")
                    exit(1)
            except (ArchiveDownloadError, ArchiveListError, NoPackageFound):
                exit(1)
            if not run_installer(tool_archives.get_packages(), base_dir, sevenzip, keep):
                exit(1)
        self.logger.info("Finished installation")
        self.logger.info("Time elapsed: {time:.8f} second".format(time=time.perf_counter() - start_time))

    def run_list_qt(self, args: argparse.ArgumentParser) -> int:
        """Print versions of Qt, extensions, modules, architectures"""

        if not args.target:
            print(" ".join(ArchiveId.TARGETS_FOR_HOST[args.host]))
            return 0
        if args.target not in ArchiveId.TARGETS_FOR_HOST[args.host]:
            self.logger.error("'{0.target}' is not a valid target for host '{0.host}'".format(args))
            return 1

        for version_str in (args.modules, args.extensions, args.arch):
            if not Cli._is_valid_version_str(version_str, allow_latest=True, allow_empty=True):
                self.logger.error("Invalid version: '{}'! Please use the form '5.X.Y'.".format(version_str))
                exit(1)  # TODO: maybe return 1 instead?

        spec = None
        try:
            if args.spec is not None:
                spec = SimpleSpec(args.spec)
        except ValueError:
            self.logger.error(f"Invalid version specification: '{args.spec}'.\n" + SimpleSpec.usage())
            return 1

        meta = MetadataFactory(
            archive_id=ArchiveId(
                "qt",
                args.host,
                args.target,
                args.extension if args.extension else "",
            ),
            spec=spec,
            is_latest_version=args.latest_version,
            modules_ver=args.modules,
            extensions_ver=args.extensions,
            architectures_ver=args.arch,
        )
        return show_list(meta)

    def run_list_tool(self, args: argparse.ArgumentParser) -> int:
        """Print tools"""

        if not args.target:
            print(" ".join(ArchiveId.TARGETS_FOR_HOST[args.host]))
            return 0
        if args.target not in ArchiveId.TARGETS_FOR_HOST[args.host]:
            self.logger.error("'{0.target}' is not a valid target for host '{0.host}'".format(args))
            return 1

        meta = MetadataFactory(
            archive_id=ArchiveId("tools", args.host, args.target),
            tool_name=args.tool_name,
            is_long_listing=args.long,
        )
        return show_list(meta)

    def show_help(self, args=None):
        """Display help message"""
        self.parser.print_help()

    def show_aqt_version(self, args=None):
        """Display version information"""
        py_version = platform.python_version()
        py_impl = platform.python_implementation()
        py_build = platform.python_compiler()
        self.logger.info("aqtinstall(aqt) v{} on Python {} [{} {}]".format(aqt.__version__, py_version, py_impl, py_build))

    def _set_install_qt_parser(self, install_qt_parser, *, is_legacy: bool):
        install_qt_parser.set_defaults(func=self.run_install_qt, is_legacy=is_legacy)
        self._set_common_arguments(install_qt_parser, is_legacy=is_legacy)
        self._set_common_options(install_qt_parser)
        install_qt_parser.add_argument(
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
        self._set_module_options(install_qt_parser)
        install_qt_parser.add_argument(
            "--noarchives",
            action="store_true",
            help="No base packages; allow mod amendment with --modules option.",
        )

    def _set_install_tool_parser(self, install_tool_parser, *, is_legacy: bool):
        install_tool_parser.set_defaults(func=self.run_install_tool, is_legacy=is_legacy)
        install_tool_parser.add_argument("host", choices=["linux", "mac", "windows"], help="host os name")
        install_tool_parser.add_argument(
            "target",
            default=None,
            choices=["desktop", "winrt", "android", "ios"],
            help="Target SDK.",
        )
        install_tool_parser.add_argument("tool_name", help="Name of tool such as tools_ifw, tools_mingw")
        install_tool_parser.add_argument(
            "arch",
            nargs="?",
            default=None,
            help="Name of full tool name such as qt.tools.ifw.31. "
            "Please use 'aqt list-tool' to list acceptable values for this parameter.",
        )
        self._set_common_options(install_tool_parser)

    def _make_legacy_parsers(self, subparsers: argparse._SubParsersAction):
        deprecated_msg = "This command is deprecated and marked for removal in a future version of aqt."
        install_parser = subparsers.add_parser(
            "install",
            description=deprecated_msg,
            formatter_class=argparse.RawTextHelpFormatter,
        )
        self._set_install_qt_parser(install_parser, is_legacy=True)
        tool_parser = subparsers.add_parser("tool")
        self._set_install_tool_parser(tool_parser, is_legacy=True)
        #
        for cmd, f in (
            ("doc", self.run_install_doc),
            ("example", self.run_install_example),
            ("src", self.run_install_src),
        ):
            p = subparsers.add_parser(cmd, description=deprecated_msg)
            p.set_defaults(func=f, is_legacy=True)
            self._set_common_arguments(p, is_legacy=True)
            self._set_common_options(p)
            self._set_module_options(p)

    def _warn_on_deprecated_command(self, old_name: str, new_name: str):
        self.logger.warning(
            f"Warning: The command '{old_name}' is deprecated and marked for removal in a future version of aqt.\n"
            f"In the future, please use the command '{new_name}' instead."
        )

    def _make_install_parsers(self, subparsers: argparse._SubParsersAction):
        install_qt_parser = subparsers.add_parser("install-qt", formatter_class=argparse.RawTextHelpFormatter)
        self._set_install_qt_parser(install_qt_parser, is_legacy=False)
        tool_parser = subparsers.add_parser("install-tool")
        self._set_install_tool_parser(tool_parser, is_legacy=False)
        #
        for cmd, f in (
            ("install-doc", self.run_install_doc),
            ("install-example", self.run_install_example),
        ):
            p = subparsers.add_parser(cmd)
            p.set_defaults(func=f, is_legacy=False)
            self._set_common_arguments(p, is_legacy=False)
            self._set_common_options(p)
            self._set_module_options(p)
        src_parser = subparsers.add_parser("install-src")
        src_parser.set_defaults(func=self.run_install_src, is_legacy=False)
        self._set_common_arguments(src_parser, is_legacy=False)
        self._set_common_options(src_parser)
        self._set_module_options(src_parser)
        src_parser.add_argument("--kde", action="store_true", help="patching with KDE patch kit.")

    def _make_list_qt_parser(self, subparsers: argparse._SubParsersAction):
        """Creates a subparser that works with the MetadataFactory, and adds it to the `subparsers` parameter"""
        list_parser: argparse.ArgumentParser = subparsers.add_parser(
            "list-qt",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="Examples:\n"
            "$ aqt list-qt mac                                            # print all targets for Mac OS\n"
            "$ aqt list-qt mac desktop                                    # print all versions of Qt 5\n"
            "$ aqt list-qt mac desktop --extension wasm                   # print all wasm versions of Qt 5\n"
            '$ aqt list-qt mac desktop --spec "5.9"                       # print all versions of Qt 5.9\n'
            '$ aqt list-qt mac desktop --spec "5.9" --latest-version      # print latest Qt 5.9\n'
            "$ aqt list-qt mac desktop --modules 5.12.0                   # print modules for 5.12.0\n"
            "$ aqt list-qt mac desktop --spec 5.9 --modules latest  # print modules for latest 5.9\n"
            "$ aqt list-qt mac desktop --extensions 5.9.0                 # print choices for --extension flag\n"
            "$ aqt list-qt mac desktop --arch 5.9.9                       "
            "# print architectures for 5.9.9/mac/desktop\n"
            "$ aqt list-qt mac desktop --arch latest                      "
            "# print architectures for the latest Qt 5\n",
        )
        list_parser.add_argument("host", choices=["linux", "mac", "windows"], help="host os name")
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
            "--spec",
            type=str,
            metavar="SPECIFICATION",
            help="Filter output so that only versions that match the specification are printed. "
            'IE: `aqt list-qt windows desktop --spec "5.12"` prints all versions beginning with 5.12',
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
        list_parser.set_defaults(func=self.run_list_qt)

    def _make_list_tool_parser(self, subparsers: argparse._SubParsersAction):
        """Creates a subparser that works with the MetadataFactory, and adds it to the `subparsers` parameter"""
        list_parser: argparse.ArgumentParser = subparsers.add_parser(
            "list-tool",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="Examples:\n"
            "$ aqt list-tool mac desktop                 # print all tools for mac desktop\n"
            "$ aqt list-tool mac desktop tools_ifw       # print all tool variant names for QtIFW\n"
            "$ aqt list-tool mac desktop ifw             # print all tool variant names for QtIFW\n"
            "$ aqt list-tool mac desktop -l tools_ifw    # print tool variant names with metadata for QtIFW\n"
            "$ aqt list-tool mac desktop -l ifw          # print tool variant names with metadata for QtIFW\n",
        )
        list_parser.add_argument("host", choices=["linux", "mac", "windows"], help="host os name")
        list_parser.add_argument(
            "target",
            nargs="?",
            default=None,
            choices=["desktop", "winrt", "android", "ios"],
            help="Target SDK. When omitted, this prints all the targets available for a host OS.",
        )
        list_parser.add_argument(
            "tool_name",
            nargs="?",
            default=None,
            help='Name of a tool, ie "tools_mingw" or "tools_ifw". '
            "When omitted, this prints all the tool names available for a host OS/target SDK combination. "
            "When present, this prints all the tool variant names available for this tool. ",
        )
        list_parser.add_argument(
            "-l",
            "--long",
            action="store_true",
            help="Long display: shows a table of metadata associated with each tool variant. "
            "On narrow terminals, it displays tool variant names, versions, and release dates. "
            "On terminals wider than 95 characters, it also displays descriptions of each tool.",
        )
        list_parser.set_defaults(func=self.run_list_tool)

    def _make_common_parsers(self, subparsers: argparse._SubParsersAction):
        help_parser = subparsers.add_parser("help")
        help_parser.set_defaults(func=self.show_help)
        #
        version_parser = subparsers.add_parser("version")
        version_parser.set_defaults(func=self.show_aqt_version)

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
            help="Specify mirror base url such as http://mirrors.ocf.berkeley.edu/qt/, " "where 'online' folder exist.",
        )
        subparser.add_argument(
            "--timeout",
            nargs="?",
            type=float,
            help="Specify connection timeout for download site.(default: 5 sec)",
        )
        subparser.add_argument("-E", "--external", nargs="?", help="Specify external 7zip command path.")
        subparser.add_argument("--internal", action="store_true", help="Use internal extractor.")
        subparser.add_argument(
            "-k",
            "--keep",
            action="store_true",
            help="Keep downloaded archive when specified, otherwise remove after install",
        )

    def _set_module_options(self, subparser):
        subparser.add_argument("-m", "--modules", nargs="*", help="Specify extra modules to install")
        subparser.add_argument(
            "--archives",
            nargs="*",
            help="Specify subset packages to install (Default: all standard and extra modules).",
        )

    def _set_common_arguments(self, subparser, *, is_legacy: bool):
        """
        Legacy commands require that the version comes before host and target.
        Non-legacy commands require that the host and target are before the version.
        """
        if is_legacy:
            subparser.add_argument("qt_version", help='Qt version in the format of "5.X.Y"')
        subparser.add_argument("host", choices=["linux", "mac", "windows"], help="host os name")
        subparser.add_argument("target", choices=["desktop", "winrt", "android", "ios"], help="target sdk")
        if not is_legacy:
            subparser.add_argument("qt_version", help='Qt version in the format of "5.X.Y"')

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

    @staticmethod
    def _is_valid_version_str(version_str: str, *, allow_latest: bool = False, allow_empty: bool = False) -> bool:
        if (allow_latest and version_str == "latest") or (allow_empty and not version_str):
            return True
        try:
            Version(version_str)
            return True
        except ValueError:
            return False


def run_installer(archives: List[QtPackage], base_dir: str, sevenzip: Optional[str], keep: bool) -> bool:
    result = True
    queue = multiprocessing.Manager().Queue(-1)
    listener = MyQueueListener(queue)
    listener.start()
    #
    tasks = []
    for arc in archives:
        tasks.append((arc, base_dir, sevenzip, queue, keep))
    ctx = multiprocessing.get_context("spawn")
    pool = ctx.Pool(Settings.concurrency, init_worker_sh)
    try:
        pool.starmap(installer, tasks)
        pool.close()
        pool.join()
    except KeyboardInterrupt:
        logger = getLogger("aqt.installer")
        logger.warning("Caught KeyboardInterrupt, terminating installer workers")
        pool.terminate()
        pool.join()
        result = False
    # all done, close logging service for sub-processes
    listener.enqueue_sentinel()
    listener.stop()
    return result


def init_worker_sh():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def installer(
    qt_archive: QtPackage,
    base_dir: str,
    command: Optional[str],
    queue: multiprocessing.Queue,
    keep: bool = False,
    response_timeout: Optional[int] = None,
):
    """
    Installer function to download archive files and extract it.
    It is called through multiprocessing.Pool()
    """
    name = qt_archive.name
    url = qt_archive.archive_url
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
    logger.info("Finished installation of {} in {:.8f}".format(archive, time.perf_counter() - start_time))
    qh.flush()
    qh.close()
    logger.removeHandler(qh)

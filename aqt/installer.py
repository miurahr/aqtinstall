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
import errno
import gc
import multiprocessing
import os
import platform
import posixpath
import signal
import subprocess
import sys
import time
from logging import getLogger
from logging.handlers import QueueHandler
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Optional, Tuple, cast

import aqt
from aqt.archives import QtArchives, QtPackage, SrcDocExamplesArchives, TargetConfig, ToolArchives
from aqt.exceptions import (
    AqtException,
    ArchiveChecksumError,
    ArchiveDownloadError,
    ArchiveExtractionError,
    ArchiveListError,
    CliInputError,
    CliKeyboardInterrupt,
    DiskAccessNotPermitted,
    OutOfDiskSpace,
    OutOfMemory,
)
from aqt.helper import (
    MyQueueListener,
    Settings,
    downloadBinaryFile,
    get_hash,
    retry_on_bad_connection,
    retry_on_errors,
    setup_logging,
)
from aqt.metadata import ArchiveId, MetadataFactory, QtRepoProperty, SimpleSpec, Version, show_list, suggested_follow_up
from aqt.updater import Updater, dir_for_version

try:
    import py7zr

    EXT7Z = False
except ImportError:
    EXT7Z = True


class BaseArgumentParser(argparse.ArgumentParser):
    """Global options and subcommand trick"""

    config: Optional[str]
    func: object


class ListArgumentParser(BaseArgumentParser):
    """List-* command parser arguments and options"""

    arch: Optional[str]
    archives: List[str]
    extension: str
    extensions: str
    host: str
    last_version: str
    latest_version: bool
    long: bool
    long_modules: List[str]
    modules: List[str]
    qt_version_spec: str
    spec: str
    target: str


class ListToolArgumentParser(ListArgumentParser):
    """List-tool command options"""

    tool_name: str
    tool_version: str


class CommonInstallArgParser(BaseArgumentParser):
    """Install-*/install common arguments"""

    is_legacy: bool
    target: str
    host: str

    outputdir: Optional[str]
    base: Optional[str]
    timeout: Optional[float]
    external: Optional[str]
    internal: bool
    keep: bool
    archive_dest: Optional[str]


class InstallArgParser(CommonInstallArgParser):
    """Install-qt arguments and options"""

    arch: Optional[str]
    qt_version: str
    qt_version_spec: str

    modules: Optional[List[str]]
    archives: Optional[List[str]]
    noarchives: bool
    autodesktop: bool


class InstallToolArgParser(CommonInstallArgParser):
    """Install-tool arguments and options"""

    tool_name: str
    version: Optional[str]
    tool_variant: Optional[str]


class Cli:
    """CLI main class to parse command line argument and launch proper functions."""

    __slot__ = ["parser", "combinations", "logger"]

    UNHANDLED_EXCEPTION_CODE = 254

    def __init__(self):
        parser = argparse.ArgumentParser(
            prog="aqt",
            description="Another unofficial Qt Installer.\naqt helps you install Qt SDK, tools, examples and others\n",
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
        self._make_all_parsers(subparsers)
        parser.set_defaults(func=self.show_help)
        self.parser = parser

    def run(self, arg=None) -> int:
        args = self.parser.parse_args(arg)
        self._setup_settings(args)
        try:
            args.func(args)
            return 0
        except AqtException as e:
            self.logger.error(format(e), exc_info=Settings.print_stacktrace_on_error)
            if e.should_show_help:
                self.show_help()
            return 1
        except Exception as e:
            # If we didn't account for it, and wrap it in an AqtException, it's a bug.
            self.logger.exception(e)  # Print stack trace
            self.logger.error(
                f"{self._format_aqt_version()}\n"
                f"Working dir: `{os.getcwd()}`\n"
                f"Arguments: `{sys.argv}` Host: `{platform.uname()}`\n"
                "===========================PLEASE FILE A BUG REPORT===========================\n"
                "You have discovered a bug in aqt.\n"
                "Please file a bug report at https://github.com/miurahr/aqtinstall/issues\n"
                "Please remember to include a copy of this program's output in your report."
            )
            return Cli.UNHANDLED_EXCEPTION_CODE

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

    def _warning_unknown_qt_version(self, qt_version: str) -> str:
        return self._warning_on_bad_combination(f'Qt version "{qt_version}"')

    def _warning_unknown_target_arch_combo(self, args: List[str]) -> str:
        return self._warning_on_bad_combination(f"target combination \"{' '.join(args)}\"")

    def _warning_unexpected_modules(self, unexpected_modules: List[str]) -> str:
        return self._warning_on_bad_combination(f"modules {unexpected_modules}")

    def _warning_on_bad_combination(self, combo_message: str) -> str:
        return (
            f"Specified {combo_message} did not exist when this version of aqtinstall was released. "
            "This may not install properly, but we will try our best."
        )

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
            raise CliInputError("Specified 7zip command executable does not exist: {!r}".format(sevenzip)) from e

        return sevenzip

    @staticmethod
    def _set_arch(arch: Optional[str], os_name: str, target: str, qt_version_or_spec: str) -> str:
        """Choose a default architecture, if one can be determined"""
        if arch is not None and arch != "":
            return arch
        if os_name == "linux" and target == "desktop":
            return "gcc_64"
        elif os_name == "mac" and target == "desktop":
            return "clang_64"
        elif os_name == "mac" and target == "ios":
            return "ios"
        elif target == "android":
            try:
                if Version(qt_version_or_spec) >= Version("5.14.0"):
                    return "android"
            except ValueError:
                pass
        raise CliInputError("Please supply a target architecture.", should_show_help=True)

    def _check_mirror(self, mirror):
        if mirror is None:
            pass
        elif mirror.startswith("http://") or mirror.startswith("https://") or mirror.startswith("ftp://"):
            pass
        else:
            return False
        return True

    def _select_unexpected_modules(self, qt_version: str, modules: Optional[List[str]]) -> List[str]:
        """Returns a sorted list of all the requested modules that do not exist in the combinations.json file."""
        available = Settings.available_modules(qt_version)
        return sorted(set(modules or []) - set(available or []))

    @staticmethod
    def _determine_qt_version(
        qt_version_or_spec: str, host: str, target: str, arch: str, base_url: str = Settings.baseurl
    ) -> Version:
        def choose_highest(x: Optional[Version], y: Optional[Version]) -> Optional[Version]:
            if x and y:
                return max(x, y)
            return x or y

        def opt_version_for_spec(ext: str, _spec: SimpleSpec) -> Optional[Version]:
            try:
                meta = MetadataFactory(ArchiveId("qt", host, target), spec=_spec, base_url=base_url)
                return meta.fetch_latest_version(ext)
            except AqtException:
                return None

        try:
            return Version(qt_version_or_spec)
        except ValueError:
            pass
        try:
            spec = SimpleSpec(qt_version_or_spec)
        except ValueError as e:
            raise CliInputError(f"Invalid version or SimpleSpec: '{qt_version_or_spec}'\n" + SimpleSpec.usage()) from e
        else:
            version: Optional[Version] = None
            for ext in QtRepoProperty.possible_extensions_for_arch(arch):
                version = choose_highest(version, opt_version_for_spec(ext, spec))
            if not version:
                raise CliInputError(
                    f"No versions of Qt exist for spec={spec} with host={host}, target={target}, arch={arch}"
                )
            getLogger("aqt.installer").info(f"Resolved spec '{qt_version_or_spec}' to {version}")
            return version

    @staticmethod
    def choose_archive_dest(archive_dest: Optional[str], keep: bool, temp_dir: str) -> Path:
        """
        Choose archive download destination, based on context.

        There are three potential behaviors here:
        1. By default, return a temp directory that will be removed on program exit.
        2. If the user has asked to keep archives, but has not specified a destination,
            we return Settings.archive_download_location ("." by default).
        3. If the user has asked to keep archives and specified a destination,
            we create the destination dir if it doesn't exist, and return that directory.
        """
        if not archive_dest:
            return Path(Settings.archive_download_location if keep else temp_dir)
        dest = Path(archive_dest)
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    def run_install_qt(self, args: InstallArgParser):
        """Run install subcommand"""
        start_time = time.perf_counter()
        self.show_aqt_version()
        if args.is_legacy:
            self._warn_on_deprecated_command("install", "install-qt")
        target: str = args.target
        os_name: str = args.host
        qt_version_or_spec: str = getattr(args, "qt_version", getattr(args, "qt_version_spec", ""))
        arch: str = self._set_arch(args.arch, os_name, target, qt_version_or_spec)
        keep: bool = args.keep or Settings.always_keep_archives
        archive_dest: Optional[str] = args.archive_dest
        output_dir = args.outputdir
        if output_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = output_dir
        if args.timeout is not None:
            timeout = (args.timeout, args.timeout)
        else:
            timeout = (Settings.connection_timeout, Settings.response_timeout)
        modules = args.modules
        sevenzip = self._set_sevenzip(args.external)
        if EXT7Z and sevenzip is None:
            # override when py7zr is not exist
            sevenzip = self._set_sevenzip("7z")
        if args.base is not None:
            if not self._check_mirror(args.base):
                raise CliInputError(
                    "The `--base` option requires a url where the path `online/qtsdkrepository` exists.",
                    should_show_help=True,
                )
            base = args.base
        else:
            base = Settings.baseurl
        if hasattr(args, "qt_version_spec"):
            qt_version: str = str(Cli._determine_qt_version(args.qt_version_spec, os_name, target, arch, base_url=base))
        else:
            qt_version = args.qt_version
            Cli._validate_version_str(qt_version)
        archives = args.archives
        if args.noarchives:
            if modules is None:
                raise CliInputError("When `--noarchives` is set, the `--modules` option is mandatory.")
            if archives is not None:
                raise CliInputError("Options `--archives` and `--noarchives` are mutually exclusive.")
        else:
            if modules is not None and archives is not None:
                archives.extend(modules)
        nopatch = args.noarchives or (archives is not None and "qtbase" not in archives)  # type: bool
        should_autoinstall: bool = args.autodesktop
        _version = Version(qt_version)
        base_path = Path(base_dir)

        expect_desktop_archdir, autodesk_arch = self._get_autodesktop_dir_and_arch(
            should_autoinstall, os_name, target, base_path, _version, is_wasm=(arch.startswith("wasm"))
        )

        def get_auto_desktop_archives() -> List[QtPackage]:
            def to_archives(baseurl: str) -> QtArchives:
                return QtArchives(os_name, "desktop", qt_version, cast(str, autodesk_arch), base=baseurl, timeout=timeout)

            if autodesk_arch is not None:
                return cast(QtArchives, retry_on_bad_connection(to_archives, base)).archives
            else:
                return []

        auto_desktop_archives: List[QtPackage] = get_auto_desktop_archives()

        if not self._check_qt_arg_versions(qt_version):
            self.logger.warning(self._warning_unknown_qt_version(qt_version))
        if not self._check_qt_arg_combination(qt_version, os_name, target, arch):
            self.logger.warning(self._warning_unknown_target_arch_combo([os_name, target, arch]))
        all_extra = True if modules is not None and "all" in modules else False
        if not all_extra:
            unexpected_modules = self._select_unexpected_modules(qt_version, modules)
            if unexpected_modules:
                self.logger.warning(self._warning_unexpected_modules(unexpected_modules))

        qt_archives: QtArchives = retry_on_bad_connection(
            lambda base_url: QtArchives(
                os_name,
                target,
                qt_version,
                arch,
                base=base_url,
                subarchives=archives,
                modules=modules,
                all_extra=all_extra,
                is_include_base_package=not args.noarchives,
                timeout=timeout,
            ),
            base,
        )
        qt_archives.archives.extend(auto_desktop_archives)
        target_config = qt_archives.get_target_config()
        with TemporaryDirectory() as temp_dir:
            _archive_dest = Cli.choose_archive_dest(archive_dest, keep, temp_dir)
            run_installer(qt_archives.get_packages(), base_dir, sevenzip, keep, _archive_dest)

        if not nopatch:
            Updater.update(target_config, base_path, expect_desktop_archdir)
            if autodesk_arch is not None:
                d_target_config = TargetConfig(str(_version), "desktop", autodesk_arch, os_name)
                Updater.update(d_target_config, base_path, expect_desktop_archdir)
        self.logger.info("Finished installation")
        self.logger.info("Time elapsed: {time:.8f} second".format(time=time.perf_counter() - start_time))

    def _run_src_doc_examples(self, flavor, args, cmd_name: Optional[str] = None):
        self.show_aqt_version()
        if args.is_legacy:
            if cmd_name is None:
                self._warn_on_deprecated_command(old_name=flavor, new_name=f"install-{flavor}")
            else:
                self._warn_on_deprecated_command(old_name=cmd_name, new_name=f"install-{cmd_name}")
        elif getattr(args, "target", None) is not None:
            self._warn_on_deprecated_parameter("target", args.target)
        target = "desktop"  # The only valid target for src/doc/examples is "desktop"
        os_name = args.host
        output_dir = args.outputdir
        if output_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = output_dir
        keep: bool = args.keep or Settings.always_keep_archives
        archive_dest: Optional[str] = args.archive_dest
        if args.base is not None:
            base = args.base
        else:
            base = Settings.baseurl
        if hasattr(args, "qt_version_spec"):
            qt_version = str(Cli._determine_qt_version(args.qt_version_spec, os_name, target, arch="", base_url=base))
        else:
            qt_version = args.qt_version
            Cli._validate_version_str(qt_version)
        if args.timeout is not None:
            timeout = (args.timeout, args.timeout)
        else:
            timeout = (Settings.connection_timeout, Settings.response_timeout)
        sevenzip = self._set_sevenzip(args.external)
        if EXT7Z and sevenzip is None:
            # override when py7zr is not exist
            sevenzip = self._set_sevenzip(Settings.zipcmd)
        modules = getattr(args, "modules", None)  # `--modules` is invalid for `install-src`
        archives = args.archives
        all_extra = True if modules is not None and "all" in modules else False
        if not self._check_qt_arg_versions(qt_version):
            self.logger.warning(self._warning_unknown_qt_version(qt_version))

        srcdocexamples_archives: SrcDocExamplesArchives = retry_on_bad_connection(
            lambda base_url: SrcDocExamplesArchives(
                flavor,
                os_name,
                target,
                qt_version,
                base=base_url,
                subarchives=archives,
                modules=modules,
                all_extra=all_extra,
                timeout=timeout,
            ),
            base,
        )
        with TemporaryDirectory() as temp_dir:
            _archive_dest = Cli.choose_archive_dest(archive_dest, keep, temp_dir)
            run_installer(srcdocexamples_archives.get_packages(), base_dir, sevenzip, keep, _archive_dest)
        self.logger.info("Finished installation")

    def run_install_src(self, args):
        """Run src subcommand"""
        if not hasattr(args, "qt_version"):
            base = args.base if hasattr(args, "base") else Settings.baseurl
            args.qt_version = str(
                Cli._determine_qt_version(args.qt_version_spec, args.host, args.target, arch="", base_url=base)
            )
        if args.kde and args.qt_version != "5.15.2":
            raise CliInputError("KDE patch: unsupported version!!")
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

    def run_install_tool(self, args: InstallToolArgParser):
        """Run tool subcommand"""
        start_time = time.perf_counter()
        self.show_aqt_version()
        if args.is_legacy:
            self._warn_on_deprecated_command("tool", "install-tool")
        tool_name = args.tool_name  # such as tools_openssl_x64
        os_name = args.host  # windows, linux and mac
        target = "desktop" if args.is_legacy else args.target  # desktop, android and ios
        output_dir = args.outputdir
        if output_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = output_dir
        sevenzip = self._set_sevenzip(args.external)
        if EXT7Z and sevenzip is None:
            # override when py7zr is not exist
            sevenzip = self._set_sevenzip(Settings.zipcmd)
        version = getattr(args, "version", None)
        if version is not None:
            Cli._validate_version_str(version, allow_minus=True)
        keep: bool = args.keep or Settings.always_keep_archives
        archive_dest: Optional[str] = args.archive_dest
        if args.base is not None:
            base = args.base
        else:
            base = Settings.baseurl
        if args.timeout is not None:
            timeout = (args.timeout, args.timeout)
        else:
            timeout = (Settings.connection_timeout, Settings.response_timeout)
        if args.tool_variant is None:
            archive_id = ArchiveId("tools", os_name, target)
            meta = MetadataFactory(archive_id, base_url=base, is_latest_version=True, tool_name=tool_name)
            try:
                archs: List[str] = cast(list, meta.getList())
            except ArchiveDownloadError as e:
                msg = f"Failed to locate XML data for the tool '{tool_name}'."
                raise ArchiveListError(msg, suggested_action=suggested_follow_up(meta)) from e

        else:
            archs = [args.tool_variant]

        for arch in archs:
            if not self._check_tools_arg_combination(os_name, tool_name, arch):
                self.logger.warning(self._warning_unknown_target_arch_combo([os_name, tool_name, arch]))

            tool_archives: ToolArchives = retry_on_bad_connection(
                lambda base_url: ToolArchives(
                    os_name=os_name,
                    tool_name=tool_name,
                    target=target,
                    base=base_url,
                    version_str=version,
                    arch=arch,
                    timeout=timeout,
                ),
                base,
            )
            with TemporaryDirectory() as temp_dir:
                _archive_dest = Cli.choose_archive_dest(archive_dest, keep, temp_dir)
                run_installer(tool_archives.get_packages(), base_dir, sevenzip, keep, _archive_dest)
        self.logger.info("Finished installation")
        self.logger.info("Time elapsed: {time:.8f} second".format(time=time.perf_counter() - start_time))

    def run_list_qt(self, args: ListArgumentParser):
        """Print versions of Qt, extensions, modules, architectures"""

        if args.extensions:
            self._warn_on_deprecated_parameter("extensions", args.extensions)
            self.logger.warning(
                "The '--extensions' flag will always return an empty list, "
                "because there are no useful arguments for the '--extension' flag."
            )
            print("")
            return
        if args.extension:
            self._warn_on_deprecated_parameter("extension", args.extension)
            self.logger.warning("The '--extension' flag will be ignored.")

        if not args.target:
            print(" ".join(ArchiveId.TARGETS_FOR_HOST[args.host]))
            return
        if args.target not in ArchiveId.TARGETS_FOR_HOST[args.host]:
            raise CliInputError("'{0.target}' is not a valid target for host '{0.host}'".format(args))
        if args.modules:
            assert len(args.modules) == 2, "broken argument parser for list-qt"
            modules_query = MetadataFactory.ModulesQuery(args.modules[0], args.modules[1])
            modules_ver, is_long = args.modules[0], False
        elif args.long_modules:
            assert args.long_modules and len(args.long_modules) == 2, "broken argument parser for list-qt"
            modules_query = MetadataFactory.ModulesQuery(args.long_modules[0], args.long_modules[1])
            modules_ver, is_long = args.long_modules[0], True
        else:
            modules_ver, modules_query, is_long = None, None, False

        for version_str in (modules_ver, args.arch, args.archives[0] if args.archives else None):
            Cli._validate_version_str(version_str, allow_latest=True, allow_empty=True)

        spec = None
        try:
            if args.spec is not None:
                spec = SimpleSpec(args.spec)
        except ValueError as e:
            raise CliInputError(f"Invalid version specification: '{args.spec}'.\n" + SimpleSpec.usage()) from e

        meta = MetadataFactory(
            archive_id=ArchiveId("qt", args.host, args.target),
            spec=spec,
            is_latest_version=args.latest_version,
            modules_query=modules_query,
            is_long_listing=is_long,
            architectures_ver=args.arch,
            archives_query=args.archives,
        )
        show_list(meta)

    def run_list_tool(self, args: ListToolArgumentParser):
        """Print tools"""

        if not args.target:
            print(" ".join(ArchiveId.TARGETS_FOR_HOST[args.host]))
            return
        if args.target not in ArchiveId.TARGETS_FOR_HOST[args.host]:
            raise CliInputError("'{0.target}' is not a valid target for host '{0.host}'".format(args))

        meta = MetadataFactory(
            archive_id=ArchiveId("tools", args.host, args.target),
            tool_name=args.tool_name,
            is_long_listing=args.long,
        )
        show_list(meta)

    def run_list_src_doc_examples(self, args: ListArgumentParser, cmd_type: str):
        target = "desktop"  # The only valid target for src/doc/examples is "desktop"
        version = Cli._determine_qt_version(args.qt_version_spec, args.host, target, arch="")
        is_fetch_modules: bool = getattr(args, "modules", False)
        meta = MetadataFactory(
            archive_id=ArchiveId("qt", args.host, target),
            src_doc_examples_query=MetadataFactory.SrcDocExamplesQuery(cmd_type, version, is_fetch_modules),
        )
        show_list(meta)

    def show_help(self, args=None):
        """Display help message"""
        self.parser.print_help()

    def _format_aqt_version(self) -> str:
        py_version = platform.python_version()
        py_impl = platform.python_implementation()
        py_build = platform.python_compiler()
        return f"aqtinstall(aqt) v{aqt.__version__} on Python {py_version} [{py_impl} {py_build}]"

    def show_aqt_version(self, args=None):
        """Display version information"""
        self.logger.info(self._format_aqt_version())

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
        self._set_archive_options(install_qt_parser)
        install_qt_parser.add_argument(
            "--noarchives",
            action="store_true",
            help="No base packages; allow mod amendment with --modules option.",
        )
        install_qt_parser.add_argument(
            "--autodesktop",
            action="store_true",
            help="For Qt6 android, ios, and wasm installations, an additional desktop Qt installation is required. "
            "When enabled, this option installs the required desktop version automatically.",
        )

    def _set_install_tool_parser(self, install_tool_parser, *, is_legacy: bool):
        install_tool_parser.set_defaults(func=self.run_install_tool, is_legacy=is_legacy)
        install_tool_parser.add_argument("host", choices=["linux", "mac", "windows"], help="host os name")
        if not is_legacy:
            install_tool_parser.add_argument(
                "target",
                default=None,
                choices=["desktop", "winrt", "android", "ios"],
                help="Target SDK.",
            )
        install_tool_parser.add_argument("tool_name", help="Name of tool such as tools_ifw, tools_mingw")
        if is_legacy:
            install_tool_parser.add_argument("version", help="Version of tool variant")

        tool_variant_opts = {} if is_legacy else {"nargs": "?", "default": None}
        install_tool_parser.add_argument(
            "tool_variant",
            **tool_variant_opts,
            help="Name of tool variant, such as qt.tools.ifw.41. "
            "Please use 'aqt list-tool' to list acceptable values for this parameter.",
        )
        self._set_common_options(install_tool_parser)

    def _warn_on_deprecated_command(self, old_name: str, new_name: str) -> None:
        self.logger.warning(
            f"The command '{old_name}' is deprecated and marked for removal in a future version of aqt.\n"
            f"In the future, please use the command '{new_name}' instead."
        )

    def _warn_on_deprecated_parameter(self, parameter_name: str, value: str):
        self.logger.warning(
            f"The parameter '{parameter_name}' with value '{value}' is deprecated and marked for "
            f"removal in a future version of aqt.\n"
            f"In the future, please omit this parameter."
        )

    def _make_all_parsers(self, subparsers: argparse._SubParsersAction) -> None:
        deprecated_msg = "This command is deprecated and marked for removal in a future version of aqt."

        def make_parser_it(cmd: str, desc: str, is_legacy: bool, set_parser_cmd, formatter_class):
            description = f"{desc} {deprecated_msg}" if is_legacy else desc
            kwargs = {"formatter_class": formatter_class} if formatter_class else {}
            p = subparsers.add_parser(cmd, description=description, **kwargs)
            set_parser_cmd(p, is_legacy=is_legacy)

        def make_parser_sde(cmd: str, desc: str, is_legacy: bool, action, is_add_kde: bool, is_add_modules: bool = True):
            description = f"{desc} {deprecated_msg}" if is_legacy else desc
            parser = subparsers.add_parser(cmd, description=description)
            parser.set_defaults(func=action, is_legacy=is_legacy)
            self._set_common_arguments(parser, is_legacy=is_legacy, is_target_deprecated=True)
            self._set_common_options(parser)
            if is_add_modules:
                self._set_module_options(parser)
            self._set_archive_options(parser)
            if is_add_kde:
                parser.add_argument("--kde", action="store_true", help="patching with KDE patch kit.")

        def make_parser_list_sde(cmd: str, desc: str, cmd_type: str):
            parser = subparsers.add_parser(cmd, description=desc)
            parser.add_argument("host", choices=["linux", "mac", "windows"], help="host os name")
            parser.add_argument(
                "qt_version_spec",
                metavar="(VERSION | SPECIFICATION)",
                help='Qt version in the format of "5.X.Y" or SimpleSpec like "5.X" or "<6.X"',
            )
            parser.set_defaults(func=lambda args: self.run_list_src_doc_examples(args, cmd_type))

            if cmd_type != "src":
                parser.add_argument("-m", "--modules", action="store_true", help="Print list of available modules")

        make_parser_it("install-qt", "Install Qt.", False, self._set_install_qt_parser, argparse.RawTextHelpFormatter)
        make_parser_it("install-tool", "Install tools.", False, self._set_install_tool_parser, None)
        make_parser_sde("install-doc", "Install documentation.", False, self.run_install_doc, False)
        make_parser_sde("install-example", "Install examples.", False, self.run_install_example, False)
        make_parser_sde("install-src", "Install source.", False, self.run_install_src, True, is_add_modules=False)

        self._make_list_qt_parser(subparsers)
        self._make_list_tool_parser(subparsers)
        make_parser_list_sde("list-doc", "List documentation archives available (use with install-doc)", "doc")
        make_parser_list_sde("list-example", "List example archives available (use with install-example)", "examples")
        make_parser_list_sde("list-src", "List source archives available (use with install-src)", "src")

        make_parser_it("install", "Install Qt.", True, self._set_install_qt_parser, argparse.RawTextHelpFormatter)
        make_parser_it("tool", "Install tools.", True, self._set_install_tool_parser, None)
        make_parser_sde("doc", "Install documentation.", True, self.run_install_doc, False)
        make_parser_sde("examples", "Install examples.", True, self.run_install_example, False)
        make_parser_sde("src", "Install source.", True, self.run_install_src, True)

        self._make_common_parsers(subparsers)

    def _make_list_qt_parser(self, subparsers: argparse._SubParsersAction):
        """Creates a subparser that works with the MetadataFactory, and adds it to the `subparsers` parameter"""
        list_parser: ListArgumentParser = subparsers.add_parser(
            "list-qt",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="Examples:\n"
            "$ aqt list-qt mac                                                # print all targets for Mac OS\n"
            "$ aqt list-qt mac desktop                                        # print all versions of Qt 5\n"
            '$ aqt list-qt mac desktop --spec "5.9"                           # print all versions of Qt 5.9\n'
            '$ aqt list-qt mac desktop --spec "5.9" --latest-version          # print latest Qt 5.9\n'
            "$ aqt list-qt mac desktop --modules 5.12.0 clang_64              # print modules for 5.12.0\n"
            "$ aqt list-qt mac desktop --spec 5.9 --modules latest clang_64   # print modules for latest 5.9\n"
            "$ aqt list-qt mac desktop --arch 5.9.9                           # print architectures for 5.9.9/mac/desktop\n"
            "$ aqt list-qt mac desktop --arch latest                          # print architectures for the latest Qt 5\n"
            "$ aqt list-qt mac desktop --archives 5.9.0 clang_64              # list archives in base Qt installation\n"
            "$ aqt list-qt mac desktop --archives 5.14.0 clang_64 debug_info  # list archives in debug_info module\n",
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
            help="Deprecated since aqt v3.1.0. Use of this flag will emit a warning, but will otherwise be ignored.",
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
            nargs=2,
            metavar=("(VERSION | latest)", "ARCHITECTURE"),
            help='First arg: Qt version in the format of "5.X.Y", or the keyword "latest". '
            'Second arg: an architecture, which may be printed with the "--arch" flag. '
            "When set, this prints all the modules available for either Qt 5.X.Y or the latest version of Qt.",
        )
        output_modifier_exclusive_group.add_argument(
            "--long-modules",
            type=str,
            nargs=2,
            metavar=("(VERSION | latest)", "ARCHITECTURE"),
            help='First arg: Qt version in the format of "5.X.Y", or the keyword "latest". '
            'Second arg: an architecture, which may be printed with the "--arch" flag. '
            "When set, this prints a table that describes all the modules available "
            "for either Qt 5.X.Y or the latest version of Qt.",
        )
        output_modifier_exclusive_group.add_argument(
            "--extensions",
            type=str,
            metavar="(VERSION | latest)",
            help="Deprecated since v3.1.0. Prints a list of valid arguments for the '--extension' flag. "
            "Since the '--extension' flag is now deprecated, this will always print an empty list.",
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
            "--archives",
            type=str,
            nargs="+",
            help="print the archives available for Qt base or modules. "
            "If two arguments are provided, the first two arguments must be 'VERSION | latest' and "
            "'ARCHITECTURE', and this command will print all archives associated with the base Qt package. "
            "If more than two arguments are provided, the remaining arguments will be interpreted as modules, "
            "and this command will print all archives associated with those modules. "
            "At least two arguments are required.",
        )
        list_parser.set_defaults(func=self.run_list_qt)

    def _make_list_tool_parser(self, subparsers: argparse._SubParsersAction):
        """Creates a subparser that works with the MetadataFactory, and adds it to the `subparsers` parameter"""
        list_parser: ListArgumentParser = subparsers.add_parser(
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
        subparser.add_argument(
            "-d",
            "--archive-dest",
            type=str,
            default=None,
            help="Set the destination path for downloaded archives (temp directory by default).",
        )

    def _set_module_options(self, subparser):
        subparser.add_argument("-m", "--modules", nargs="*", help="Specify extra modules to install")

    def _set_archive_options(self, subparser):
        subparser.add_argument(
            "--archives",
            nargs="*",
            help="Specify subset of archives to install. Affects the base module and the debug_info module. "
            "(Default: all archives).",
        )

    def _set_common_arguments(self, subparser, *, is_legacy: bool, is_target_deprecated: bool = False):
        """
        Legacy commands require that the version comes before host and target.
        Non-legacy commands require that the host and target are before the version.
        install-src/doc/example commands do not require a "target" argument anymore, as of 11/22/2021
        """
        if is_legacy:
            subparser.add_argument("qt_version", help='Qt version in the format of "5.X.Y"')
        subparser.add_argument("host", choices=["linux", "mac", "windows"], help="host os name")
        if is_target_deprecated:
            subparser.add_argument(
                "target",
                choices=["desktop", "winrt", "android", "ios"],
                nargs="?",
                help="Ignored. This parameter is deprecated and marked for removal in a future release. "
                "It is present here for backwards compatibility.",
            )
        else:
            subparser.add_argument("target", choices=["desktop", "winrt", "android", "ios"], help="target sdk")
        if not is_legacy:
            subparser.add_argument(
                "qt_version_spec",
                metavar="(VERSION | SPECIFICATION)",
                help='Qt version in the format of "5.X.Y" or SimpleSpec like "5.X" or "<6.X"',
            )

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
    def _validate_version_str(
        version_str: Optional[str], *, allow_latest: bool = False, allow_empty: bool = False, allow_minus: bool = False
    ) -> None:
        """
        Raise CliInputError if the version is not an acceptable Version.

        :param version_str: The version string to check.
        :param allow_latest: If true, the string "latest" is acceptable.
        :param allow_empty: If true, the empty string is acceptable.
        :param allow_minus: If true, everything after the first '-' in the version will be ignored.
                            This allows acceptance of versions like "1.2.3-0-202101020304"
        """
        if allow_latest and version_str == "latest":
            return
        if not version_str:
            if allow_empty:
                return
            else:
                raise CliInputError("Invalid empty version! Please use the form '5.X.Y'.")
        try:
            if "-" in version_str and allow_minus:
                version_str = version_str[: version_str.find("-")]
            Version(version_str)
        except ValueError as e:
            raise CliInputError(f"Invalid version: '{version_str}'! Please use the form '5.X.Y'.") from e

    def _get_autodesktop_dir_and_arch(
        self, should_autoinstall: bool, host: str, target: str, base_path: Path, version: Version, is_wasm: bool = False
    ) -> Tuple[Optional[str], Optional[str]]:
        """Returns expected_desktop_arch_dir, desktop_arch_to_install"""
        if version < Version("6.0.0") or (target not in ["ios", "android"] and not is_wasm):
            # We only need to worry about the desktop directory for Qt6 mobile or wasm installs.
            return None, None

        installed_desktop_arch_dir = QtRepoProperty.find_installed_desktop_qt_dir(host, base_path, version)
        if installed_desktop_arch_dir:
            # An acceptable desktop Qt is already installed, so don't do anything.
            self.logger.info(f"Found installed {host}-desktop Qt at {installed_desktop_arch_dir}")
            return installed_desktop_arch_dir.name, None

        default_desktop_arch = MetadataFactory(ArchiveId("qt", host, "desktop")).fetch_default_desktop_arch(version)
        desktop_arch_dir = QtRepoProperty.get_arch_dir_name(host, default_desktop_arch, version)
        expected_desktop_arch_path = base_path / dir_for_version(version) / desktop_arch_dir

        qt_type = "Qt6-WASM" if is_wasm else target
        if should_autoinstall:
            # No desktop Qt is installed, but the user has requested installation. Find out what to install.
            self.logger.info(
                f"You are installing the {qt_type} version of Qt, which requires that the desktop version of Qt "
                f"is also installed. Now installing Qt: desktop {version} {default_desktop_arch}"
            )
            return expected_desktop_arch_path.name, default_desktop_arch
        else:
            self.logger.warning(
                f"You are installing the {qt_type} version of Qt, which requires that the desktop version of Qt "
                f"is also installed. You can install it with the following command:\n"
                f"          `aqt install-qt {host} desktop {version} {default_desktop_arch}`"
            )
            return expected_desktop_arch_path.name, None


def is_64bit() -> bool:
    """check if running platform is 64bit python."""
    return sys.maxsize > 1 << 32


def run_installer(archives: List[QtPackage], base_dir: str, sevenzip: Optional[str], keep: bool, archive_dest: Path):
    queue = multiprocessing.Manager().Queue(-1)
    listener = MyQueueListener(queue)
    listener.start()
    #
    tasks = []
    for arc in archives:
        tasks.append((arc, base_dir, sevenzip, queue, archive_dest, Settings.configfile, keep))
    ctx = multiprocessing.get_context("spawn")
    if is_64bit():
        pool = ctx.Pool(Settings.concurrency, init_worker_sh, (), 4)
    else:
        pool = ctx.Pool(Settings.concurrency, init_worker_sh, (), 1)

    def close_worker_pool_on_exception(exception: BaseException):
        logger = getLogger("aqt.installer")
        logger.warning(f"Caught {exception.__class__.__name__}, terminating installer workers")
        pool.terminate()
        pool.join()

    try:
        pool.starmap(installer, tasks)
        pool.close()
        pool.join()
    except PermissionError as e:  # subclass of OSError
        close_worker_pool_on_exception(e)
        raise DiskAccessNotPermitted(
            f"Failed to write to base directory at {base_dir}",
            suggested_action=[
                "Check that the destination is writable and does not already contain files owned by another user."
            ],
        ) from e
    except OSError as e:
        close_worker_pool_on_exception(e)
        if e.errno == errno.ENOSPC:
            raise OutOfDiskSpace(
                "Insufficient disk space to complete installation.",
                suggested_action=["Check available disk space.", "Check size requirements for installation."],
            ) from e
        else:
            raise
    except KeyboardInterrupt as e:
        close_worker_pool_on_exception(e)
        raise CliKeyboardInterrupt("Installer halted by keyboard interrupt.") from e
    except MemoryError as e:
        close_worker_pool_on_exception(e)
        alt_extractor_msg = (
            "Please try using the '--external' flag to specify an alternate 7z extraction tool "
            "(see https://aqtinstall.readthedocs.io/en/latest/cli.html#cmdoption-list-tool-external)"
        )
        if Settings.concurrency > 1:
            docs_url = "https://aqtinstall.readthedocs.io/en/stable/configuration.html#configuration"
            raise OutOfMemory(
                "Out of memory when downloading and extracting archives in parallel.",
                suggested_action=[f"Please reduce your 'concurrency' setting (see {docs_url})", alt_extractor_msg],
            ) from e
        raise OutOfMemory(
            "Out of memory when downloading and extracting archives.",
            suggested_action=["Please free up more memory.", alt_extractor_msg],
        )
    except Exception as e:
        close_worker_pool_on_exception(e)
        raise e from e
    finally:
        # all done, close logging service for sub-processes
        listener.enqueue_sentinel()
        listener.stop()


def init_worker_sh():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def installer(
    qt_package: QtPackage,
    base_dir: str,
    command: Optional[str],
    queue: multiprocessing.Queue,
    archive_dest: Path,
    settings_ini: str,
    keep: bool,
):
    """
    Installer function to download archive files and extract it.
    It is called through multiprocessing.Pool()
    """
    name = qt_package.name
    base_url = qt_package.base_url
    archive: Path = archive_dest / qt_package.archive
    start_time = time.perf_counter()
    Settings.load_settings(file=settings_ini)
    # setup queue logger
    setup_logging()
    qh = QueueHandler(queue)
    logger = getLogger()
    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)
    logger.addHandler(qh)
    #
    timeout = (Settings.connection_timeout, Settings.response_timeout)
    hash = get_hash(qt_package.archive_path, algorithm="sha256", timeout=timeout)

    def download_bin(_base_url):
        url = posixpath.join(_base_url, qt_package.archive_path)
        logger.debug("Download URL: {}".format(url))
        return downloadBinaryFile(url, archive, "sha256", hash, timeout)

    retry_on_errors(
        action=lambda: retry_on_bad_connection(download_bin, base_url),
        acceptable_errors=(ArchiveChecksumError,),
        num_retries=Settings.max_retries_on_checksum_error,
        name=f"Downloading {name}",
    )
    gc.collect()
    if command is None:
        with py7zr.SevenZipFile(archive, "r") as szf:
            szf.extractall(path=base_dir)
    else:
        command_args = [command, "x", "-aoa", "-bd", "-y", "-o{}".format(base_dir), str(archive)]
        try:
            proc = subprocess.run(command_args, stdout=subprocess.PIPE, check=True)
            logger.debug(proc.stdout)
        except subprocess.CalledProcessError as cpe:
            msg = "\n".join(filter(None, [f"Extraction error: {cpe.returncode}", cpe.stdout, cpe.stderr]))
            raise ArchiveExtractionError(msg) from cpe
    if not keep:
        os.unlink(archive)
    logger.info("Finished installation of {} in {:.8f}".format(archive.name, time.perf_counter() - start_time))
    gc.collect()
    qh.flush()
    qh.close()
    logger.removeHandler(qh)

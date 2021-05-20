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
import hashlib
import logging
import logging.config
import multiprocessing
import os
import platform
import random
import subprocess
import sys
import time
from logging import getLogger

import appdirs
import requests
from packaging.version import Version, parse
from requests.adapters import HTTPAdapter
from texttable import Texttable
from urllib3.util.retry import Retry

import aqt
from aqt.archives import (
    ArchiveConnectionError,
    ArchiveDownloadError,
    ArchiveListError,
    NoPackageFound,
    PackagesList,
    QtArchives,
    SrcDocExamplesArchives,
    ToolArchives,
)
from aqt.cuteci import DeployCuteCI
from aqt.helper import Settings, altlink
from aqt.updater import Updater

try:
    import py7zr

    EXT7Z = False
except ImportError:
    EXT7Z = True


class ExtractionError(Exception):
    pass


BASE_URL = "https://download.qt.io"
FALLBACK_URLS = [
    "https://mirrors.ocf.berkeley.edu/qt",
    "https://ftp.jaist.ac.jp/pub/qtproject",
    "http://ftp1.nluug.nl/languages/qt",
    "https://mirrors.dotsrc.org/qtproject",
]


class Cli:
    """CLI main class to parse command line argument and launch proper functions."""

    __slot__ = ["parser", "combinations", "logger"]

    def __init__(self, env_key="AQT_CONFIG"):
        config = os.getenv(env_key, None)
        self.settings = Settings(config=config)
        self._create_parser()

    def _check_tools_arg_combination(self, os_name, tool_name, arch):
        for c in self.settings.tools_combinations:
            if (
                c["os_name"] == os_name
                and c["tool_name"] == tool_name
                and c["arch"] == arch
            ):
                return True
        return False

    def _check_qt_arg_combination(self, qt_version, os_name, target, arch):
        if os_name == "windows" and target == "desktop":
            # check frequent mistakes
            if qt_version.startswith("5.15.") or qt_version.startswith("6."):
                if arch in [
                    "win64_msvc2017_64",
                    "win32_msvc2017",
                    "win64_mingw73",
                    "win32_mingw73",
                ]:
                    return False
            elif (
                qt_version.startswith("5.9.")
                or qt_version.startswith("5.10.")
                or qt_version.startswith("5.11.")
            ):
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
        for c in self.settings.qt_combinations:
            if c["os_name"] == os_name and c["target"] == target and c["arch"] == arch:
                return True
        return False

    def _check_qt_arg_versions(self, qt_version):
        for ver in self.settings.available_versions:
            if ver == qt_version:
                return True
        return False

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
            elif target == "android" and parse(qt_version) >= Version("5.14.0"):
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

    def call_installer(self, qt_archives, target_dir, sevenzip, keep):
        if target_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = target_dir
        tasks = []
        for arc in qt_archives.get_archives():
            tasks.append((arc, base_dir, sevenzip, keep))
        pool = multiprocessing.Pool(self.settings.concurrency)
        pool.starmap(installer, tasks)
        pool.close()
        pool.join()

    def run_install(self, args):
        """Run install subcommand"""
        start_time = time.perf_counter()
        arch = args.arch
        target = args.target
        os_name = args.host
        qt_version = args.qt_version
        output_dir = args.outputdir
        keep = args.keep
        if output_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = output_dir
        if args.timeout is not None:
            timeout = (args.timeout, args.timeout)
        else:
            timeout = (5, 5)
        arch = self._set_arch(args, arch, os_name, target, qt_version)
        modules = args.modules
        sevenzip = self._set_sevenzip(args.external)
        if EXT7Z and sevenzip is None:
            # override when py7zr is not exist
            sevenzip = self._set_sevenzip("7z")
        if args.base is not None:
            base = args.base
        else:
            base = BASE_URL
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
        self._run_common_part(output_dir, base)
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
                logging=self.logger,
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
                    random.choice(FALLBACK_URLS),
                    subarchives=archives,
                    modules=modules,
                    logging=self.logger,
                    all_extra=all_extra,
                    timeout=timeout,
                )
            except Exception:
                self.logger.error("Connection to the download site failed. Aborted...")
                exit(1)
        except ArchiveDownloadError or ArchiveListError or NoPackageFound:
            exit(1)
        target_config = qt_archives.get_target_config()
        self.call_installer(qt_archives, output_dir, sevenzip, keep)
        if not nopatch:
            Updater.update(target_config, base_dir, self.logger)
        self.logger.info("Finished installation")
        self.logger.info(
            "Time elasped: {time:.8f} second".format(
                time=time.perf_counter() - start_time
            )
        )

    def run_offline_installer(self, args):
        """Run online_installer subcommand"""
        start_time = time.perf_counter()
        os_name = args.host
        qt_version = args.qt_version
        output_dir = args.outputdir
        arch = args.arch
        if output_dir is None:
            base_dir = os.getcwd()
        else:
            base_dir = os.path.realpath(output_dir)
        if args.timeout is not None:
            timeout = args.timeout
        else:
            timeout = 300
        if args.base is not None:
            base = args.base
        else:
            base = BASE_URL
        self._run_common_part(output_dir, base)
        qt_ver_num = qt_version.replace(".", "")
        packages = ["qt.qt5.{}.{}".format(qt_ver_num, arch)]
        if args.archives is not None:
            packages.extend(args.archives)
        #
        qa = os.path.join(appdirs.user_data_dir("Qt", None), "qtaccount.ini")
        if not os.path.exists(qa):
            self.logger.warning("Cannot find {}".format(qa))
        cuteci = DeployCuteCI(qt_version, os_name, base, timeout)
        if not cuteci.check_archive():
            archive = cuteci.download_installer()
        else:
            self.logger.info("Reuse existent installer archive.")
            archive = cuteci.get_archive_name()
        cuteci.run_installer(archive, packages, base_dir, True)
        self.logger.info("Finished installation")
        self.logger.info(
            "Time elapsed: {time:.8f} second".format(
                time=time.perf_counter() - start_time
            )
        )

    def _run_src_doc_examples(self, flavor, args):
        start_time = time.perf_counter()
        target = args.target
        os_name = args.host
        qt_version = args.qt_version
        output_dir = args.outputdir
        keep = args.keep
        if args.base is not None:
            base = args.base
        else:
            base = BASE_URL
        if args.timeout is not None:
            timeout = (args.timeout, args.timeout)
        else:
            timeout = (5, 5)
        sevenzip = self._set_sevenzip(args.external)
        if EXT7Z and sevenzip is None:
            # override when py7zr is not exist
            sevenzip = self._set_sevenzip("7z")
        modules = args.modules
        archives = args.archives
        self._run_common_part(output_dir, base)
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
                logging=self.logger,
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
                    random.choice(FALLBACK_URLS),
                    subarchives=archives,
                    modules=modules,
                    logging=self.logger,
                    all_extra=all_extra,
                    timeout=timeout,
                )
            except Exception:
                self.logger.error("Connection to the download site failed. Aborted...")
                exit(1)
        except ArchiveDownloadError or ArchiveListError:
            exit(1)
        self.call_installer(srcdocexamples_archives, output_dir, sevenzip, keep)
        self.logger.info("Finished installation")
        self.logger.info(
            "Time elapsed: {time:.8f} second".format(
                time=time.perf_counter() - start_time
            )
        )

    def run_src(self, args):
        """Run src subcommand"""
        self._run_src_doc_examples("src", args)

    def run_examples(self, args):
        """Run example subcommand"""
        self._run_src_doc_examples("examples", args)

    def run_doc(self, args):
        """Run doc subcommand"""
        self._run_src_doc_examples("doc", args)

    def run_tool(self, args):
        """Run tool subcommand"""
        start_time = time.perf_counter()
        arch = args.arch
        tool_name = args.tool_name
        os_name = args.host
        output_dir = args.outputdir
        sevenzip = self._set_sevenzip(args.external)
        if EXT7Z and sevenzip is None:
            # override when py7zr is not exist
            sevenzip = self._set_sevenzip("7z")
        version = args.version
        keep = args.keep
        if args.base is not None:
            base = args.base
        else:
            base = BASE_URL
        if args.timeout is not None:
            timeout = (args.timeout, args.timeout)
        else:
            timeout = (5, 5)
        self._run_common_part(output_dir, base)
        if not self._check_tools_arg_combination(os_name, tool_name, arch):
            self.logger.warning(
                "Specified target combination is not valid: {} {} {}".format(
                    os_name, tool_name, arch
                )
            )
        try:
            tool_archives = ToolArchives(
                os_name,
                tool_name,
                version,
                arch,
                base,
                logging=self.logger,
                timeout=timeout,
            )
        except ArchiveConnectionError:
            try:
                self.logger.warning(
                    "Connection to the download site failed and fallback to mirror site."
                )
                tool_archives = ToolArchives(
                    os_name,
                    tool_name,
                    version,
                    arch,
                    random.choice(FALLBACK_URLS),
                    logging=self.logger,
                    timeout=timeout,
                )
            except Exception:
                self.logger.error("Connection to the download site failed. Aborted...")
                exit(1)
        except ArchiveDownloadError or ArchiveListError:
            exit(1)
        self.call_installer(tool_archives, output_dir, sevenzip, keep)
        self.logger.info("Finished installation")
        self.logger.info(
            "Time elapsed: {time:.8f} second".format(
                time=time.perf_counter() - start_time
            )
        )

    def run_list(self, args):
        """Run list subcommand"""
        self.show_aqt_version()
        qt_version = args.qt_version
        host = args.host
        target = args.target
        try:
            pl = PackagesList(qt_version, host, target, BASE_URL)
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            pl = PackagesList(qt_version, host, target, random.choice(FALLBACK_URLS))
        print("List Qt packages in %s for %s" % (args.qt_version, args.host))
        table = Texttable()
        table.set_deco(Texttable.HEADER)
        table.set_cols_dtype(["t", "t", "t"])
        table.set_cols_align(["l", "l", "l"])
        table.header(["target", "arch", "description"])
        for entry in pl.get_list():
            if qt_version[0:1] == "6" or not entry.virtual:
                archid = entry.name.split(".")[-1]
                table.add_row([entry.display_name, archid, entry.desc])
        print(table.draw())

    def show_help(self, args):
        """Display help message"""
        self.parser.print_help()

    def show_aqt_version(self):
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
            "--logging-conf",
            type=argparse.FileType("r"),
            nargs=1,
            help="Logging configuration ini file.",
        )
        parser.add_argument("--logger", nargs=1, help="Specify logger name")
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
            "arch", help="Name of full tool name such as qt.tools.ifw.31"
        )
        self._set_common_options(tools_parser)
        #
        list_parser = subparsers.add_parser("list")
        list_parser.set_defaults(func=self.run_list)
        self._set_common_argument(list_parser)
        #
        old_install = subparsers.add_parser(
            "offline_installer",
            formatter_class=argparse.RawTextHelpFormatter,
            description="Install Qt using offiline installer. It requires downloading installer binary(500-1500MB).\n"
            "Please help you for patience to wait downloding."
            "It can accept environment variables:\n"
            "  QTLOGIN: qt account login name\n"
            "  QTPASSWORD: qt account password\n",
        )
        old_install.add_argument(
            "qt_version", help='Qt version in the format of "5.X.Y"'
        )
        old_install.add_argument(
            "host", choices=["linux", "mac", "windows"], help="host os name"
        )
        old_install.add_argument(
            "arch",
            help="\ntarget linux/desktop: gcc_64"
            "\ntarget mac/desktop:   clang_64"
            "\nwindows/desktop:      win64_msvc2017_64, win32_msvc2017"
            "\n                      win64_msvc2015_64, win32_msvc2015",
        )
        old_install.add_argument(
            "--archives",
            nargs="*",
            help="Specify packages to install.",
        )
        old_install.add_argument(
            "-O",
            "--outputdir",
            nargs="?",
            help="Target output directory(default current directory)",
        )
        old_install.add_argument(
            "-b",
            "--base",
            nargs="?",
            help="Specify mirror base url such as http://mirrors.ocf.berkeley.edu/qt/, "
            "where 'online' folder exist.",
        )
        old_install.add_argument(
            "--timeout",
            nargs="?",
            type=float,
            help="Specify timeout for offline installer processing.(default: 300 sec)",
        )
        old_install.set_defaults(func=self.run_offline_installer)
        #
        help_parser = subparsers.add_parser("help")
        help_parser.set_defaults(func=self.show_help)
        parser.set_defaults(func=self.show_help)
        self.parser = parser

    def _setup_logging(self, args, env_key="LOG_CFG"):
        envconf = os.getenv(env_key, None)
        conf = None
        if args.logging_conf:
            conf = args.logging_conf
        elif envconf is not None:
            conf = envconf
        if conf is None or not os.path.exists(conf):
            conf = os.path.join(os.path.dirname(__file__), "logging.ini")
        logging.config.fileConfig(conf)
        if args.logger is not None:
            self.logger = logging.getLogger(args.logger)
        else:
            self.logger = logging.getLogger("aqt")

    def run(self, arg=None):
        args = self.parser.parse_args(arg)
        self._setup_logging(args)
        return args.func(args)


def installer(qt_archive, base_dir, command, keep=False, response_timeout=30):
    """
    Installer function to download archive files and extract it.
    It is called through multiprocessing.Pool()
    """
    name = qt_archive.name
    url = qt_archive.url
    hashurl = qt_archive.hashurl
    archive = qt_archive.archive
    start_time = time.perf_counter()
    logger = getLogger("aqt")
    logger.info("Downloading {}...".format(name))
    logger.debug("Download URL: {}".format(url))
    timeout = (3.5, response_timeout)
    #
    expected_sha1 = None
    with requests.Session() as session:
        retry = Retry(connect=5, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        try:
            r = session.get(hashurl, allow_redirects=True, timeout=timeout)
        except (requests.exceptions.ConnectionError or requests.exceptions.Timeout):
            pass  # ignore it
        else:
            expected_sha1 = binascii.unhexlify(r.content)
    #
    with requests.Session() as session:
        retry = Retry(connect=5, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        try:
            r = session.get(url, allow_redirects=False, stream=True, timeout=timeout)
            if r.status_code == 302:
                newurl = altlink(r.url, r.headers["Location"], logger=logger)
                logger.info("Redirected URL: {}".format(newurl))
                r = session.get(newurl, stream=True, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection error: %s" % e.args)
            raise e
        except requests.exceptions.Timeout as e:
            logger.error("Connection timeout: %s" % e.args)
            raise e
        else:
            checksum = hashlib.sha1()
            try:
                with open(archive, "wb") as fd:
                    for chunk in r.iter_content(chunk_size=8196):
                        fd.write(chunk)
                        checksum.update(chunk)
                    fd.flush()
                if expected_sha1 is not None:
                    if checksum.digest() != expected_sha1:
                        raise ArchiveDownloadError(
                            "Download file is corrupted! Check sum error."
                        )
                if command is None:
                    with py7zr.SevenZipFile(archive, "r") as szf:
                        szf.extractall(path=base_dir)
            except Exception as e:
                exc = sys.exc_info()
                logger.error("Download error: %s" % exc[1])
                raise e
            else:
                if command is not None:
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
                        proc = subprocess.run(
                            command_args, stdout=subprocess.PIPE, check=True
                        )
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
        "Finished installation of {} in {}".format(
            archive, time.perf_counter() - start_time
        )
    )

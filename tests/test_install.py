import errno
import hashlib
import logging
import os
import posixpath
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import py7zr
import pytest

from aqt.archives import QtPackage
from aqt.exceptions import ArchiveDownloadError, ArchiveExtractionError
from aqt.helper import Settings
from aqt.installer import Cli, installer


class MockMultiprocessingContext:
    """
    By default, monkeypatch will only patch objects in the main process.
    When multiprocessing is used, child processes will not be patched.
    This class forces all work to be done in the main process, so that all
    patched objects remain patched.

    NOTE: This probably isn't the right way to solve the problem, but it is
    the only way I have found to solve it.
    """

    def __init__(self, *args):
        pass

    class Pool:
        def __init__(self, *args):
            pass

        def starmap(self, func: Callable, func_args: List[Tuple], *args):
            for set_of_args in func_args:
                func(*set_of_args)

        def close(self):
            pass

        def join(self):
            pass

        def terminate(self):
            pass


class MockMultiprocessingManager:
    class Queue:
        def __init__(self, *args):
            pass

        def put_nowait(self, log_record: Optional[logging.LogRecord]):
            # NOTE: This is certainly not the right way to do this, but it works locally
            if not log_record or log_record.levelno < logging.INFO:
                return
            print(log_record.message, file=sys.stderr)

        def get(self, *args):
            return None


GET_URL_TYPE = Callable[[str, Any], str]
DOWNLOAD_ARCHIVE_TYPE = Callable[[str, str, str, bytes, Any], None]
LIST_OF_FILES_AND_CONTENTS = Iterable[Dict[str, str]]


@dataclass
class PatchedFile:
    filename: str
    unpatched_content: str
    patched_content: Optional[str] = None  # When None, the file is expected not to be patched.

    def expected_content(self, **kwargs) -> str:
        if not self.patched_content:
            return self.unpatched_content
        return self.patched_content.format(**kwargs)


@dataclass
class MockArchive:
    filename_7z: str
    update_xml_name: str
    contents: Iterable[PatchedFile]
    version: str = ""
    arch_dir: str = ""
    should_install: bool = True
    date: datetime = datetime.now()

    def xml_package_update(self) -> str:
        return textwrap.dedent(
            f"""\
             <PackageUpdate>
              <Name>{self.update_xml_name}</Name>
              <Version>{self.version}-0-{self.date.strftime("%Y%m%d%H%M")}</Version>
              <Description>none</Description>
              <DownloadableArchives>{self.filename_7z}</DownloadableArchives>
             </PackageUpdate>"""
        )

    def write_compressed_archive(self, dest: Path) -> None:
        with TemporaryDirectory() as temp_dir, py7zr.SevenZipFile(dest / self.filename_7z, "w") as archive:
            temp_path = Path(temp_dir)

            for folder in ("bin", "lib", "mkspecs"):
                (temp_path / self.arch_dir / folder).mkdir(parents=True, exist_ok=True)

            # Use `self.contents` to write qmake binary, qmake script, QtCore binaries, etc
            for patched_file in self.contents:
                full_path = temp_path / self.arch_dir / patched_file.filename
                if not full_path.parent.exists():
                    full_path.parent.mkdir(parents=True)
                full_path.write_text(patched_file.unpatched_content, "utf_8")

            archive_name = "5.9" if self.version == "5.9.0" else self.version
            archive.writeall(path=temp_path, arcname=archive_name)


def make_mock_geturl_download_archive(
    *,
    standard_archives: List[MockArchive],
    desktop_archives: Optional[List[MockArchive]] = None,
    standard_updates_url: str,
    desktop_updates_url: str = "",
) -> Tuple[GET_URL_TYPE, DOWNLOAD_ARCHIVE_TYPE]:
    """
    Returns a mock 'getUrl' and a mock 'downloadArchive' function.
    """
    if desktop_archives is None:
        desktop_archives = []
    for _archive in [*standard_archives, *desktop_archives]:
        assert _archive.filename_7z.endswith(".7z")

    standard_xml = "<Updates>\n{}\n</Updates>".format(
        "\n".join([archive.xml_package_update() for archive in standard_archives])
    )
    desktop_xml = "<Updates>\n{}\n</Updates>".format(
        "\n".join([archive.xml_package_update() for archive in desktop_archives])
    )

    def mock_getUrl(url: str, *args, **kwargs) -> str:
        for xml, updates_url in (
            (standard_xml, standard_updates_url),
            (desktop_xml, desktop_updates_url),
        ):
            basename = posixpath.dirname(updates_url)
            if not updates_url:
                continue
            elif url.endswith(updates_url):
                return xml
            elif basename in url and url.endswith(".sha256"):
                filename = url.split("/")[-1][: -len(".sha256")]
                return f"{hashlib.sha256(bytes(xml, 'utf-8')).hexdigest()} {filename}"
        assert False, f"No mocked url available for '{url}'"

    def mock_download_archive(url: str, out: str, *args):
        """Make a mocked 7z archive at out_filename"""

        def locate_archive() -> MockArchive:
            for archive in [*standard_archives, *desktop_archives]:
                if Path(out).name == archive.filename_7z:
                    return archive
            assert False, "Requested an archive that was not mocked"

        locate_archive().write_compressed_archive(Path(out).parent)

    return mock_getUrl, mock_download_archive


@pytest.fixture(autouse=True)
def disable_multiprocessing(monkeypatch):
    # This blocks all multiprocessing, which would otherwise spawn processes that are not monkeypatched
    monkeypatch.setattr(
        "aqt.installer.multiprocessing.get_context",
        lambda *args: MockMultiprocessingContext(),
    )

    monkeypatch.setattr(
        "aqt.installer.multiprocessing.Manager",
        MockMultiprocessingManager,
    )


def qtcharts_module(ver: str, arch: str) -> MockArchive:
    addons = "addons." if ver[0] == "6" else ""
    prefix = "qt" if ver.startswith("5.9.") else f"qt.qt{ver[0]}"
    return MockArchive(
        filename_7z=f"qtcharts-windows-{arch}.7z",
        update_xml_name=f"{prefix}.{ver.replace('.', '')}.{addons}qtcharts.{arch}",
        version=ver,
        # arch_dir: filled in later
        contents=(
            PatchedFile(
                filename="modules/Charts.json",
                unpatched_content=textwrap.dedent(
                    f"""\
                    {{
                        "module_name": "Charts",
                        "version": "{ver}",
                        "built_with": {{
                            "compiler_id": "GNU",
                            "compiler_target": "",
                            "compiler_version": "1.2.3.4",
                            "cross_compiled": false,
                            "target_system": "Windows"
                        }}
                    }}
                    """
                ),
                patched_content=None,  # it doesn't get patched
            ),
        ),
    )


def qtpositioning_module(ver: str, arch: str) -> MockArchive:
    addons = "addons." if ver[0] == "6" else ""
    prefix = "qt" if ver.startswith("5.9.") else f"qt.qt{ver[0]}"
    return MockArchive(
        filename_7z=f"qtlocation-windows-{arch}.7z",
        update_xml_name=f"{prefix}.{ver.replace('.', '')}.{addons}qtpositioning.{arch}",
        version=ver,
        # arch_dir: filled in later
        contents=(
            PatchedFile(
                filename="modules/Positioning.json",
                unpatched_content=textwrap.dedent(
                    f"""\
                    {{
                        "module_name": "Positioning",
                        "version": "{ver}",
                        "built_with": {{
                            "compiler_id": "GNU",
                            "compiler_target": "",
                            "compiler_version": "1.2.3.4",
                            "cross_compiled": false,
                            "target_system": "Windows"
                        }}
                    }}
                    """
                ),
                patched_content=None,  # it doesn't get patched
            ),
        ),
    )


def plain_qtbase_archive(update_xml_name: str, arch: str, host: str = "windows", should_install: bool = True) -> MockArchive:
    return MockArchive(
        filename_7z=f"qtbase-{host}-{arch}.7z",
        update_xml_name=update_xml_name,
        contents=(
            PatchedFile(
                filename="mkspecs/qconfig.pri",
                unpatched_content="... blah blah blah ...\n"
                "QT_EDITION = Not OpenSource\n"
                "QT_LICHECK = Not Empty\n"
                "... blah blah blah ...\n",
                patched_content="... blah blah blah ...\n"
                "QT_EDITION = OpenSource\n"
                "QT_LICHECK =\n"
                "... blah blah blah ...\n",
            ),
        ),
        should_install=should_install,
    )


def tool_archive(host: str, tool_name: str, variant: str, date: datetime = datetime.now()) -> MockArchive:
    return MockArchive(
        filename_7z=f"{tool_name}-{host}-{variant}.7z",
        update_xml_name=variant,
        contents=(
            PatchedFile(
                filename=f"bin/{tool_name}-{variant}.exe",
                unpatched_content="Some executable binary file",
                patched_content=None,  # it doesn't get patched
            ),
        ),
        should_install=True,
        date=date,
    )


@pytest.mark.parametrize(
    "cmd, host, target, version, arch, arch_dir, updates_url, archives, expect_out",
    (
        (
            "install-tool linux desktop tools_qtcreator qt.tools.qtcreator".split(),
            "linux",
            "desktop",
            "1.2.3-0-197001020304",
            {"std": ""},
            {"std": ""},
            {"std": "linux_x64/desktop/tools_qtcreator/Updates.xml"},
            {"std": [tool_archive("linux", "tools_qtcreator", "qt.tools.qtcreator")]},
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qt.tools.qtcreator...\n"
                r"Finished installation of tools_qtcreator-linux-qt.tools.qtcreator.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "tool linux tools_qtcreator 1.2.3-0-197001020304 qt.tools.qtcreator".split(),
            "linux",
            "desktop",
            "1.2.3",
            {"std": ""},
            {"std": ""},
            {"std": "linux_x64/desktop/tools_qtcreator/Updates.xml"},
            {"std": [tool_archive("linux", "tools_qtcreator", "qt.tools.qtcreator", datetime(1970, 1, 2, 3, 4, 5, 6))]},
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"WARNING : The command 'tool' is deprecated and marked for removal in a future version of aqt.\n"
                r"In the future, please use the command 'install-tool' instead.\n"
                r"INFO    : Downloading qt.tools.qtcreator...\n"
                r"Finished installation of tools_qtcreator-linux-qt.tools.qtcreator.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install 5.14.0 windows desktop win32_mingw73".split(),
            "windows",
            "desktop",
            "5.14.0",
            {"std": "win32_mingw73"},
            {"std": "mingw73_32"},
            {"std": "windows_x86/desktop/qt5_5140/Updates.xml"},
            {"std": [plain_qtbase_archive("qt.qt5.5140.win32_mingw73", "win32_mingw73")]},
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"WARNING : The command 'install' is deprecated"
                r" and marked for removal in a future version of aqt.\n"
                r"In the future, please use the command 'install-qt' instead.\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win32_mingw73.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (  # Mixing --modules with --archives
            "install-qt windows desktop 5.14.0 win32_mingw73 -m qtcharts --archives qtbase".split(),
            "windows",
            "desktop",
            "5.14.0",
            {"std": "win32_mingw73"},
            {"std": "mingw73_32"},
            {"std": "windows_x86/desktop/qt5_5140/Updates.xml"},
            {
                "std": [
                    plain_qtbase_archive("qt.qt5.5140.win32_mingw73", "win32_mingw73"),
                    MockArchive(
                        filename_7z="qtcharts-windows-win32_mingw73.7z",
                        update_xml_name="qt.qt5.5140.qtcharts.win32_mingw73",
                        contents=(PatchedFile(filename="lib/qtcharts.h", unpatched_content="... charts ...\n"),),
                        should_install=True,
                    ),
                    MockArchive(
                        filename_7z="qtlottie-windows-win32_mingw73.7z",
                        update_xml_name="qt.qt5.5140.qtlottie.win32_mingw73",
                        contents=(PatchedFile(filename="lib/qtlottie.h", unpatched_content="... lottie ...\n"),),
                        should_install=False,
                    ),
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win32_mingw73.7z in .*\n"
                r"INFO    : Downloading qtcharts...\n"
                r"Finished installation of qtcharts-windows-win32_mingw73.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-src windows desktop 5.14.2".split(),
            "windows",
            "desktop",
            "5.14.2",
            {"std": ""},
            {"std": ""},
            {"std": "windows_x86/desktop/qt5_5142_src_doc_examples/Updates.xml"},
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-everywhere-src-5.14.2.7z",
                        update_xml_name="qt.qt5.5142.src",
                        version="5.14.2",
                        contents=(
                            PatchedFile(
                                filename="Src/qtbase/QtBaseSource.cpp",
                                unpatched_content="int main(){ return 0; }",
                                patched_content=None,  # not patched
                            ),
                        ),
                    ),
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"WARNING : The parameter 'target' with value 'desktop' is deprecated "
                r"and marked for removal in a future version of aqt\.\n"
                r"In the future, please omit this parameter\.\n"
                r"INFO    : Downloading qtbase\.\.\.\n"
                r"Finished installation of qtbase-everywhere-src-5\.14\.2\.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-src windows 5.14.2".split(),
            "windows",
            "desktop",
            "5.14.2",
            {"std": ""},
            {"std": ""},
            {"std": "windows_x86/desktop/qt5_5142_src_doc_examples/Updates.xml"},
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-everywhere-src-5.14.2.7z",
                        update_xml_name="qt.qt5.5142.src",
                        version="5.14.2",
                        contents=(
                            PatchedFile(
                                filename="Src/qtbase/QtBaseSource.cpp",
                                unpatched_content="int main(){ return 0; }",
                                patched_content=None,  # not patched
                            ),
                        ),
                    )
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qtbase\.\.\.\n"
                r"Finished installation of qtbase-everywhere-src-5\.14\.2\.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install 5.9.0 windows desktop win32_mingw53".split(),
            "windows",
            "desktop",
            "5.9.0",
            {"std": "win32_mingw53"},
            {"std": "mingw53_32"},
            {"std": "windows_x86/desktop/qt5_59/Updates.xml"},
            {"std": [plain_qtbase_archive("qt.59.win32_mingw53", "win32_mingw53")]},
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"WARNING : The command 'install' is deprecated"
                r" and marked for removal in a future version of aqt.\n"
                r"In the future, please use the command 'install-qt' instead.\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win32_mingw53.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 5.9.0 win32_mingw53".split(),
            "windows",
            "desktop",
            "5.9.0",
            {"std": "win32_mingw53"},
            {"std": "mingw53_32"},
            {"std": "windows_x86/desktop/qt5_59/Updates.xml"},
            {"std": [plain_qtbase_archive("qt.59.win32_mingw53", "win32_mingw53")]},
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win32_mingw53.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 5.14.0 win32_mingw73".split(),
            "windows",
            "desktop",
            "5.14.0",
            {"std": "win32_mingw73"},
            {"std": "mingw73_32"},
            {"std": "windows_x86/desktop/qt5_5140/Updates.xml"},
            {"std": [plain_qtbase_archive("qt.qt5.5140.win32_mingw73", "win32_mingw73")]},
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win32_mingw73.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 5.14.0 win64_mingw73 -m qtcharts".split(),
            "windows",
            "desktop",
            "5.14.0",
            {"std": "win64_mingw73"},
            {"std": "mingw73_64"},
            {"std": "windows_x86/desktop/qt5_5140/Updates.xml"},
            {
                "std": [
                    plain_qtbase_archive("qt.qt5.5140.win64_mingw73", "win64_mingw73"),
                    qtcharts_module("5.14.0", "win64_mingw73"),
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win64_mingw73.7z in .*\n"
                r"INFO    : Downloading qtcharts...\n"
                r"Finished installation of qtcharts-windows-win64_mingw73.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 6.2.0 win64_mingw73 -m qtpositioning --noarchives".split(),
            "windows",
            "desktop",
            "6.2.0",
            {"std": "win64_mingw73"},
            {"std": "mingw73_64"},
            {"std": "windows_x86/desktop/qt6_620/Updates.xml"},
            {
                "std": [
                    plain_qtbase_archive("qt.qt6.620.win64_mingw73", "win64_mingw73", should_install=False),
                    qtpositioning_module("6.2.0", "win64_mingw73"),
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qtlocation...\n"
                r"Finished installation of qtlocation-windows-win64_mingw73.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 6.1.0 win64_mingw81 -m qtcharts".split(),
            "windows",
            "desktop",
            "6.1.0",
            {"std": "win64_mingw81"},
            {"std": "mingw81_64"},
            {"std": "windows_x86/desktop/qt6_610/Updates.xml"},
            {
                "std": [
                    plain_qtbase_archive("qt.qt6.610.win64_mingw81", "win64_mingw81"),
                    qtcharts_module("6.1.0", "win64_mingw81"),
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win64_mingw81.7z in .*\n"
                r"INFO    : Downloading qtcharts...\n"
                r"Finished installation of qtcharts-windows-win64_mingw81.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (  # Duplicates in the modules list
            "install-qt windows desktop 6.1.0 win64_mingw81 -m qtcharts qtcharts qtcharts".split(),
            "windows",
            "desktop",
            "6.1.0",
            {"std": "win64_mingw81"},
            {"std": "mingw81_64"},
            {"std": "windows_x86/desktop/qt6_610/Updates.xml"},
            {
                "std": [
                    plain_qtbase_archive("qt.qt6.610.win64_mingw81", "win64_mingw81"),
                    qtcharts_module("6.1.0", "win64_mingw81"),
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win64_mingw81.7z in .*\n"
                r"INFO    : Downloading qtcharts...\n"
                r"Finished installation of qtcharts-windows-win64_mingw81.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows android 6.1.0 android_armv7".split(),
            "windows",
            "android",
            "6.1.0",
            {"std": "android_armv7"},
            {"std": "android_armv7"},
            {"std": "windows_x86/android/qt6_610_armv7/Updates.xml"},
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-windows-android_armv7.7z",
                        update_xml_name="qt.qt6.610.android_armv7",
                        contents=(
                            # Qt 6 non-desktop should patch qconfig.pri, qmake script and target_qt.conf
                            PatchedFile(
                                filename="mkspecs/qconfig.pri",
                                unpatched_content="... blah blah blah ...\n"
                                "QT_EDITION = Not OpenSource\n"
                                "QT_LICHECK = Not Empty\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "QT_EDITION = OpenSource\n"
                                "QT_LICHECK =\n"
                                "... blah blah blah ...\n",
                            ),
                            PatchedFile(
                                filename="bin/target_qt.conf",
                                unpatched_content="Prefix=/Users/qt/work/install/target\n"
                                "HostPrefix=../../\n"
                                "HostData=target\n",
                                patched_content="Prefix={base_dir}{sep}6.1.0{sep}android_armv7{sep}target\n"
                                "HostPrefix=../../mingw1234_64\n"
                                "HostData=../android_armv7\n",
                            ),
                            PatchedFile(
                                filename="bin/qmake.bat",
                                unpatched_content="... blah blah blah ...\n"
                                "/Users/qt/work/install/bin\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "{base_dir}\\6.1.0\\mingw1234_64\\bin\n"
                                "... blah blah blah ...\n",
                            ),
                        ),
                    ),
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"WARNING : You are installing the android version of Qt, which requires that the desktop version of "
                r"Qt is also installed. You can install it with the following command:\n"
                r"          `aqt install-qt windows desktop 6.1.0 win64_mingw1234`\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-android_armv7.7z in .*\n"
                r"INFO    : Patching .*6\.1\.0[/\\]android_armv7[/\\]bin[/\\]qmake.bat\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt linux android 6.4.1 android_arm64_v8a".split(),
            "linux",
            "android",
            "6.4.1",
            {"std": "android_arm64_v8a"},
            {"std": "android_arm64_v8a"},
            {"std": "linux_x64/android/qt6_641_arm64_v8a/Updates.xml"},
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-MacOS-MacOS_12-Clang-Android-Android_ANY-ARM64.7z",
                        update_xml_name="qt.qt6.641.android_arm64_v8a",
                        contents=(
                            # Qt 6 non-desktop should patch qconfig.pri, qmake script and target_qt.conf
                            PatchedFile(
                                filename="mkspecs/qconfig.pri",
                                unpatched_content="... blah blah blah ...\n"
                                "QT_EDITION = Not OpenSource\n"
                                "QT_LICHECK = Not Empty\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "QT_EDITION = OpenSource\n"
                                "QT_LICHECK =\n"
                                "... blah blah blah ...\n",
                            ),
                            PatchedFile(
                                filename="mkspecs/qdevice.pri",
                                unpatched_content="blah blah blah...\n"
                                "DEFAULT_ANDROID_NDK_HOST = mac-x86_64\n"
                                "blah blah blah...\n",
                                patched_content="blah blah blah...\n"
                                "DEFAULT_ANDROID_NDK_HOST = linux-x86_64\n"
                                "blah blah blah...\n",
                            ),
                            PatchedFile(
                                filename="bin/target_qt.conf",
                                unpatched_content="Prefix=/Users/qt/work/install/target\n"
                                "HostPrefix=../../\n"
                                "HostData=target\n"
                                "HostLibraryExecutables=./bin\n"
                                "HostLibraryExecutables=./libexec\n",
                                patched_content="Prefix={base_dir}{sep}6.4.1{sep}android_arm64_v8a{sep}target\n"
                                "HostPrefix=../../gcc_64\n"
                                "HostData=../android_arm64_v8a\n"
                                "HostLibraryExecutables=./libexec\n"
                                "HostLibraryExecutables=./libexec\n",
                            ),
                            PatchedFile(
                                filename="bin/qmake",
                                unpatched_content="... blah blah blah ...\n"
                                "/home/qt/work/install/bin\n"
                                "/Users/qt/work/install/bin\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "{base_dir}/6.4.1/gcc_64/bin\n"
                                "{base_dir}/6.4.1/gcc_64/bin\n"
                                "... blah blah blah ...\n",
                            ),
                        ),
                    ),
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"WARNING : You are installing the android version of Qt, which requires that the desktop version of "
                r"Qt is also installed. You can install it with the following command:\n"
                r"          `aqt install-qt linux desktop 6\.4\.1 gcc_64`\n"
                r"INFO    : Downloading qtbase\.\.\.\n"
                r"Finished installation of qtbase-MacOS-MacOS_12-Clang-Android-Android_ANY-ARM64\.7z in .*\n"
                r"INFO    : Patching .*6\.4\.1[/\\]android_arm64_v8a[/\\]bin[/\\]qmake\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt linux android 6.3.0 android_arm64_v8a".split(),
            "linux",
            "android",
            "6.3.0",
            {"std": "android_arm64_v8a"},
            {"std": "android_arm64_v8a"},
            {"std": "linux_x64/android/qt6_630_arm64_v8a/Updates.xml"},
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-linux-android_arm64_v8a.7z",
                        update_xml_name="qt.qt6.630.android_arm64_v8a",
                        contents=(
                            # Qt 6 non-desktop should patch qconfig.pri, qmake script and target_qt.conf
                            PatchedFile(
                                filename="mkspecs/qconfig.pri",
                                unpatched_content="... blah blah blah ...\n"
                                "QT_EDITION = Not OpenSource\n"
                                "QT_LICHECK = Not Empty\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "QT_EDITION = OpenSource\n"
                                "QT_LICHECK =\n"
                                "... blah blah blah ...\n",
                            ),
                            PatchedFile(
                                filename="bin/target_qt.conf",
                                unpatched_content="Prefix=/home/qt/work/install/target\n"
                                "HostPrefix=../../\n"
                                "HostData=target\n",
                                patched_content="Prefix={base_dir}{sep}6.3.0{sep}android_arm64_v8a{sep}target\n"
                                "HostPrefix=../../gcc_64\n"
                                "HostData=../android_arm64_v8a\n",
                            ),
                            PatchedFile(
                                filename="bin/qmake",
                                unpatched_content="... blah blah blah ...\n"
                                "/home/qt/work/install/bin\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "{base_dir}/6.3.0/gcc_64/bin\n"
                                "... blah blah blah ...\n",
                            ),
                        ),
                    ),
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"WARNING : You are installing the android version of Qt, which requires that the desktop version of "
                r"Qt is also installed. You can install it with the following command:\n"
                r"          `aqt install-qt linux desktop 6\.3\.0 gcc_64`\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-linux-android_arm64_v8a.7z in .*\n"
                r"INFO    : Patching .*6\.3\.0[/\\]android_arm64_v8a[/\\]bin[/\\]qmake\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt mac ios 6.1.2".split(),
            "mac",
            "ios",
            "6.1.2",
            {"std": "ios"},
            {"std": "ios"},
            {"std": "mac_x64/ios/qt6_612/Updates.xml"},
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-mac-ios.7z",
                        update_xml_name="qt.qt6.612.ios",
                        contents=(
                            # Qt 6 non-desktop should patch qconfig.pri, qmake script and target_qt.conf
                            PatchedFile(
                                filename="mkspecs/qconfig.pri",
                                unpatched_content="... blah blah blah ...\n"
                                "QT_EDITION = Not OpenSource\n"
                                "QT_LICHECK = Not Empty\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "QT_EDITION = OpenSource\n"
                                "QT_LICHECK =\n"
                                "... blah blah blah ...\n",
                            ),
                            PatchedFile(
                                filename="bin/target_qt.conf",
                                unpatched_content="Prefix=/Users/qt/work/install/target\n"
                                "HostPrefix=../../\n"
                                "HostData=target\n",
                                patched_content="Prefix={base_dir}{sep}6.1.2{sep}ios{sep}target\n"
                                "HostPrefix=../../macos\n"
                                "HostData=../ios\n",
                            ),
                            PatchedFile(
                                filename="bin/qmake",
                                unpatched_content="... blah blah blah ...\n"
                                "/Users/qt/work/install/bin\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "{base_dir}/6.1.2/macos/bin\n"
                                "... blah blah blah ...\n",
                            ),
                        ),
                    ),
                ]
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"WARNING : You are installing the ios version of Qt, which requires that the desktop version of Qt is "
                r"also installed. You can install it with the following command:\n"
                r"          `aqt install-qt mac desktop 6\.1\.2 clang_64`\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-mac-ios.7z in .*\n"
                r"INFO    : Patching .*6\.1\.2[/\\]ios[/\\]bin[/\\]qmake\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt mac ios 6.1.2 --autodesktop".split(),
            "mac",
            "ios",
            "6.1.2",
            {"std": "ios", "desk": "clang_64"},
            {"std": "ios", "desk": "macos"},
            {"std": "mac_x64/ios/qt6_612/Updates.xml", "desk": "mac_x64/desktop/qt6_612/Updates.xml"},
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-mac-ios.7z",
                        update_xml_name="qt.qt6.612.ios",
                        contents=(
                            # Qt 6 non-desktop should patch qconfig.pri, qmake script and target_qt.conf
                            PatchedFile(
                                filename="mkspecs/qconfig.pri",
                                unpatched_content="... blah blah blah ...\n"
                                "QT_EDITION = Not OpenSource\n"
                                "QT_LICHECK = Not Empty\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "QT_EDITION = OpenSource\n"
                                "QT_LICHECK =\n"
                                "... blah blah blah ...\n",
                            ),
                            PatchedFile(
                                filename="bin/target_qt.conf",
                                unpatched_content="Prefix=/Users/qt/work/install/target\n"
                                "HostPrefix=../../\n"
                                "HostData=target\n",
                                patched_content="Prefix={base_dir}{sep}6.1.2{sep}ios{sep}target\n"
                                "HostPrefix=../../macos\n"
                                "HostData=../ios\n",
                            ),
                            PatchedFile(
                                filename="bin/qmake",
                                unpatched_content="... blah blah blah ...\n"
                                "/Users/qt/work/install/bin\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "{base_dir}/6.1.2/macos/bin\n"
                                "... blah blah blah ...\n",
                            ),
                        ),
                    ),
                ],
                "desk": [plain_qtbase_archive("qt.qt6.612.clang_64", "clang_64", host="mac")],
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : You are installing the ios version of Qt, which requires that the desktop version of "
                r"Qt is also installed. Now installing Qt: desktop 6\.1\.2 clang_64\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-mac-ios.7z in .*\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-mac-clang_64.7z in .*\n"
                r"INFO    : Patching .*6\.1\.2[/\\]ios[/\\]bin[/\\]qmake\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 6.2.4 wasm_32".split(),
            "windows",
            "desktop",
            "6.2.4",
            {"std": "wasm_32"},
            {"std": "wasm_32"},
            {"std": "windows_x86/desktop/qt6_624_wasm/Updates.xml"},
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-windows-wasm_32.7z",
                        update_xml_name="qt.qt6.624.wasm_32",
                        contents=(
                            # Qt 6 non-desktop should patch qconfig.pri, qmake script and target_qt.conf
                            PatchedFile(
                                filename="mkspecs/qconfig.pri",
                                unpatched_content="... blah blah blah ...\n"
                                "QT_EDITION = Not OpenSource\n"
                                "QT_LICHECK = Not Empty\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "QT_EDITION = OpenSource\n"
                                "QT_LICHECK =\n"
                                "... blah blah blah ...\n",
                            ),
                            PatchedFile(
                                filename="bin/target_qt.conf",
                                unpatched_content="Prefix=/Users/qt/work/install/target\n"
                                "HostPrefix=../../\n"
                                "HostData=target\n",
                                patched_content="Prefix={base_dir}{sep}6.2.4{sep}wasm_32{sep}target\n"
                                "HostPrefix=../../mingw1234_64\n"
                                "HostData=../wasm_32\n",
                            ),
                            PatchedFile(
                                filename="bin/qmake.bat",
                                unpatched_content="... blah blah blah ...\n"
                                "/Users/qt/work/install/bin\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "{base_dir}\\6.2.4\\mingw1234_64\\bin\n"
                                "... blah blah blah ...\n",
                            ),
                        ),
                    ),
                ],
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"WARNING : You are installing the Qt6-WASM version of Qt, which requires that the desktop version of "
                r"Qt is also installed. You can install it with the following command:\n"
                r"          `aqt install-qt windows desktop 6\.2\.4 win64_mingw1234`\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-wasm_32\.7z in .*\n"
                r"INFO    : Patching .*6\.2\.4[/\\]wasm_32[/\\]bin[/\\]qmake.bat\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
    ),
)
def test_install(
    monkeypatch,
    capsys,
    cmd: List[str],
    host: str,
    target: str,
    version: str,
    arch: Dict[str, str],
    arch_dir: Dict[str, str],
    updates_url: Dict[str, str],
    archives: Dict[str, List[MockArchive]],
    expect_out,  # type: re.Pattern
):
    # For convenience, fill in version and arch dir: prevents repetitive data declarations
    std_archives = archives["std"]
    for i in range(len(std_archives)):
        std_archives[i].version = version
        std_archives[i].arch_dir = arch_dir["std"]
    desktop_archives = archives.get("desk", [])
    for i in range(len(desktop_archives)):
        desktop_archives[i].version = version
        desktop_archives[i].arch_dir = arch_dir["desk"]

    mock_get_url, mock_download_archive = make_mock_geturl_download_archive(
        standard_archives=std_archives,
        desktop_archives=desktop_archives,
        standard_updates_url=updates_url.get("std", ""),
        desktop_updates_url=updates_url.get("desk", ""),
    )
    monkeypatch.setattr("aqt.archives.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.helper.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.installer.downloadBinaryFile", mock_download_archive)
    monkeypatch.setattr(
        "aqt.metadata.MetadataFactory.fetch_default_desktop_arch",
        lambda *args: {"windows": "win64_mingw1234", "linux": "gcc_64", "mac": "clang_64"}[host],
    )

    with TemporaryDirectory() as output_dir:
        cli = Cli()
        cli._setup_settings()

        assert 0 == cli.run(cmd + ["--outputdir", output_dir])

        out, err = capsys.readouterr()
        sys.stdout.write(out)
        sys.stderr.write(err)

        assert expect_out.match(err)

        for key in arch_dir.keys():
            installed_path = Path(output_dir) / version / arch_dir[key]
            if version == "5.9.0":
                installed_path = Path(output_dir) / "5.9" / arch_dir[key]
            assert installed_path.is_dir()
            for archive in archives[key]:
                if not archive.should_install:
                    continue
                for patched_file in archive.contents:
                    file_path = installed_path / patched_file.filename
                    assert file_path.is_file()
                    if file_path.name == "qmake":
                        assert os.access(file_path, os.X_OK), "qmake file must be executable"

                    expect_content = patched_file.expected_content(base_dir=output_dir, sep=os.sep)
                    actual_content = file_path.read_text(encoding="utf_8")
                    assert actual_content == expect_content


@pytest.mark.parametrize(
    "cmd, xml_file, expected",
    (
        (
            "install-qt windows desktop 5.16.0 win32_mingw73",
            None,
            'WARNING : Specified Qt version "5.16.0" did not exist when this version of aqtinstall was released. '
            "This may not install properly, but we will try our best.\n"
            "ERROR   : Failed to locate XML data for Qt version '5.16.0'.\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-qt windows desktop' to show versions available.\n",
        ),
        (
            "install-qt windows desktop 5.15.0 bad_arch",
            "windows-5150-update.xml",
            'WARNING : Specified target combination "windows desktop bad_arch" did not exist when this version of '
            "aqtinstall was released. This may not install properly, but we will try our best.\n"
            "ERROR   : The packages ['qt_base'] were not found while parsing XML of package information!\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-qt windows desktop --arch 5.15.0' to show architectures available.\n",
        ),
        (
            "install-qt windows desktop 5.15.0 win32_mingw73 -m nonexistent foo",
            "windows-5150-update.xml",
            "WARNING : Specified modules ['foo', 'nonexistent'] did not exist when this version of aqtinstall "
            "was released. This may not install properly, but we will try our best.\n"
            "ERROR   : The packages ['foo', 'nonexistent', 'qt_base'] were not found"
            " while parsing XML of package information!\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-qt windows desktop --arch 5.15.0' to show architectures available.\n"
            "* Please use 'aqt list-qt windows desktop --modules 5.15.0 <arch>' to show modules available.\n",
        ),
        (
            "install-doc windows desktop 5.15.0 -m nonexistent foo",
            "windows-5152-src-doc-example-update.xml",
            "WARNING : The parameter 'target' with value 'desktop' is deprecated"
            " and marked for removal in a future "
            "version of aqt.\n"
            "In the future, please omit this parameter.\n"
            "ERROR   : The packages ['doc', 'foo', 'nonexistent'] were not found"
            " while parsing XML of package information!\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-doc windows 5.15.0 --modules' to show modules available.\n",
        ),
        (
            "install-doc windows 5.15.0 -m nonexistent foo",
            "windows-5152-src-doc-example-update.xml",
            "ERROR   : The packages ['doc', 'foo', 'nonexistent'] were not found"
            " while parsing XML of package information!\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-doc windows 5.15.0 --modules' to show modules available.\n",
        ),
        (
            "install-example windows 5.15.0 -m nonexistent foo",
            "windows-5152-src-doc-example-update.xml",
            "ERROR   : The packages ['examples', 'foo', 'nonexistent'] were not found"
            " while parsing XML of package information!\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-example windows 5.15.0 --modules' to show modules available.\n",
        ),
        (
            "install-tool windows desktop tools_vcredist nonexistent",
            "windows-desktop-tools_vcredist-update.xml",
            'WARNING : Specified target combination "windows tools_vcredist nonexistent" did not exist when this version of '
            "aqtinstall was released. This may not install properly, but we will try our best.\n"
            "ERROR   : The package 'nonexistent' was not found while parsing XML of package information!\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-tool windows desktop tools_vcredist' to show tool variants available.\n",
        ),
        (
            "install-tool windows desktop tools_nonexistent nonexistent",
            None,
            'WARNING : Specified target combination "windows tools_nonexistent nonexistent" did not exist when this '
            "version of aqtinstall was released. This may not install properly, but we will try our best.\n"
            "ERROR   : Failed to locate XML data for the tool 'tools_nonexistent'.\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-tool windows desktop' to show tools available.\n",
        ),
        (
            "install-tool windows desktop tools_nonexistent",
            None,
            "ERROR   : Failed to locate XML data for the tool 'tools_nonexistent'.\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-tool windows desktop' to check what tools are available.\n",
        ),
    ),
)
def test_install_nonexistent_archives(monkeypatch, capsys, cmd, xml_file: Optional[str], expected):
    xml = (Path(__file__).parent / "data" / xml_file).read_text("utf-8") if xml_file else ""

    def mock_get_url(url, *args, **kwargs):
        if not xml_file:
            raise ArchiveDownloadError(f"Failed to retrieve file at {url}\nServer response code: 404, reason: Not Found")
        return xml

    monkeypatch.setattr("aqt.archives.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.archives.get_hash", lambda *args, **kwargs: hashlib.sha256(bytes(xml, "utf-8")).hexdigest())
    monkeypatch.setattr("aqt.metadata.get_hash", lambda *args, **kwargs: hashlib.sha256(bytes(xml, "utf-8")).hexdigest())
    monkeypatch.setattr("aqt.metadata.getUrl", mock_get_url)

    cli = Cli()
    cli._setup_settings()
    assert cli.run(cmd.split()) == 1

    out, err = capsys.readouterr()
    actual = err[err.index("\n") + 1 :]
    assert actual == expected, "{0} != {1}".format(actual, expected)


@pytest.mark.parametrize(
    "exception, settings_file, expect_end_msg, expect_return",
    (
        (
            RuntimeError(),
            "../aqt/settings.ini",
            "===========================PLEASE FILE A BUG REPORT===========================\n"
            "You have discovered a bug in aqt.\n"
            "Please file a bug report at https://github.com/miurahr/aqtinstall/issues\n"
            "Please remember to include a copy of this program's output in your report.",
            Cli.UNHANDLED_EXCEPTION_CODE,
        ),
        (
            KeyboardInterrupt(),
            "../aqt/settings.ini",
            "WARNING : Caught KeyboardInterrupt, terminating installer workers\n"
            "ERROR   : Installer halted by keyboard interrupt.",
            1,
        ),
        (
            MemoryError(),
            "../aqt/settings.ini",
            "WARNING : Caught MemoryError, terminating installer workers\n"
            "ERROR   : Out of memory when downloading and extracting archives in parallel.\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please reduce your 'concurrency' setting (see "
            "https://aqtinstall.readthedocs.io/en/stable/configuration.html#configuration)\n"
            "* Please try using the '--external' flag to specify an alternate 7z extraction tool "
            "(see https://aqtinstall.readthedocs.io/en/latest/cli.html#cmdoption-list-tool-external)",
            1,
        ),
        (
            MemoryError(),
            "data/settings_no_concurrency.ini",
            "WARNING : Caught MemoryError, terminating installer workers\n"
            "ERROR   : Out of memory when downloading and extracting archives.\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please free up more memory.\n"
            "* Please try using the '--external' flag to specify an alternate 7z extraction tool "
            "(see https://aqtinstall.readthedocs.io/en/latest/cli.html#cmdoption-list-tool-external)",
            1,
        ),
        (
            OSError(errno.ENOSPC, "No space left on device"),
            "../aqt/settings.ini",
            "WARNING : Caught OSError, terminating installer workers\n"
            "ERROR   : Insufficient disk space to complete installation.\n"
            "==============================Suggested follow-up:==============================\n"
            "* Check available disk space.\n"
            "* Check size requirements for installation.",
            1,
        ),
        (
            OSError(),
            "../aqt/settings.ini",
            "===========================PLEASE FILE A BUG REPORT===========================\n"
            "You have discovered a bug in aqt.\n"
            "Please file a bug report at https://github.com/miurahr/aqtinstall/issues\n"
            "Please remember to include a copy of this program's output in your report.",
            Cli.UNHANDLED_EXCEPTION_CODE,
        ),
        (
            PermissionError(),
            "../aqt/settings.ini",
            "WARNING : Caught PermissionError, terminating installer workers\n"
            f"ERROR   : Failed to write to base directory at {os.getcwd()}\n"
            "==============================Suggested follow-up:==============================\n"
            "* Check that the destination is writable and does not already contain files owned by another user.",
            1,
        ),
    ),
)
def test_install_pool_exception(monkeypatch, capsys, exception, settings_file, expect_end_msg, expect_return):
    def mock_installer_func(*args):
        raise exception

    host, target, ver, arch = "windows", "desktop", "6.1.0", "win64_mingw81"
    updates_url = "windows_x86/desktop/qt6_610/Updates.xml"
    archives = [plain_qtbase_archive("qt.qt6.610.win64_mingw81", "win64_mingw81")]

    cmd = ["install-qt", host, target, ver, arch]
    mock_get_url, mock_download_archive = make_mock_geturl_download_archive(
        standard_archives=archives, standard_updates_url=updates_url
    )
    monkeypatch.setattr("aqt.archives.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.helper.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.installer.installer", mock_installer_func)

    Settings.load_settings(str(Path(__file__).parent / settings_file))
    cli = Cli()
    assert expect_return == cli.run(cmd)
    out, err = capsys.readouterr()
    assert err.rstrip().endswith(expect_end_msg)


def test_install_installer_archive_extraction_err(monkeypatch):
    def mock_extractor_that_fails(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd="some command", output="out", stderr="err")

    monkeypatch.setattr("aqt.installer.get_hash", lambda *args, **kwargs: "")
    monkeypatch.setattr("aqt.installer.downloadBinaryFile", lambda *args: None)
    monkeypatch.setattr("aqt.installer.subprocess.run", mock_extractor_that_fails)

    with pytest.raises(ArchiveExtractionError) as err, TemporaryDirectory() as temp_dir:
        installer(
            qt_package=QtPackage(
                "name",
                "base_url",
                "archive_path",
                "archive",
                "package_desc",
                "pkg_update_name",
            ),
            base_dir=temp_dir,
            command="some_nonexistent_7z_extractor",
            queue=MockMultiprocessingManager.Queue(),
            archive_dest=Path(temp_dir),
            settings_ini=Settings.configfile,
            keep=False,
        )
    assert err.type == ArchiveExtractionError
    err_msg = format(err.value).rstrip()
    assert err_msg == "Extraction error: 1\nout\nerr"


@pytest.mark.parametrize(
    "cmd, host, target, version, arch, arch_dir, base_url, updates_url, archives, expect_out",
    (
        (
            "install-tool linux desktop tools_qtcreator qt.tools.qtcreator".split(),
            "linux",
            "desktop",
            "1.2.3-0-197001020304",
            "",
            "",
            "https://www.alt.qt.mirror.com",
            "linux_x64/desktop/tools_qtcreator/Updates.xml",
            [tool_archive("linux", "tools_qtcreator", "qt.tools.qtcreator")],
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qt.tools.qtcreator...\n"
                r"Finished installation of tools_qtcreator-linux-qt.tools.qtcreator.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 5.12 win32_mingw73".split(),
            "windows",
            "desktop",
            "5.12.10",
            "win32_mingw73",
            "mingw73_32",
            "https://www.alt.qt.mirror.com",
            "windows_x86/desktop/qt5_51210/Updates.xml",
            [plain_qtbase_archive("qt.qt5.51210.win32_mingw73", "win32_mingw73")],
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Resolved spec '5\.12' to 5\.12\.10\n"
                r"INFO    : Downloading qtbase\.\.\.\n"
                r"Finished installation of qtbase-windows-win32_mingw73\.7z in .*\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
    ),
)
def test_installer_passes_base_to_metadatafactory(
    monkeypatch,
    capsys,
    cmd: List[str],
    host: str,
    target: str,
    version: str,
    arch: str,
    arch_dir: str,
    base_url: str,
    updates_url: str,
    archives: List[MockArchive],
    expect_out,  # type: re.Pattern
):
    # For convenience, fill in version and arch dir: prevents repetitive data declarations
    for i in range(len(archives)):
        archives[i].version = version
        archives[i].arch_dir = arch_dir

    basic_mock_get_url, mock_download_archive = make_mock_geturl_download_archive(
        standard_archives=archives, standard_updates_url=updates_url
    )

    def mock_get_url(url: str, *args, **kwargs) -> str:
        # If we are fetching an index.html file, get it from tests/data/
        if url == f"{base_url}/online/qtsdkrepository/{host}_x{'86' if host == 'windows' else '64'}/{target}/":
            return (Path(__file__).parent / "data" / f"{host}-{target}.html").read_text("utf-8")

        # Intercept and check the base url, but only if it's not a hash.
        # Hashes must come from trusted mirrors only.
        if not url.endswith(".sha256"):
            assert url.startswith(base_url)

        return basic_mock_get_url(url, *args, **kwargs)

    monkeypatch.setattr("aqt.archives.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.helper.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.installer.downloadBinaryFile", mock_download_archive)

    monkeypatch.setattr("aqt.metadata.getUrl", mock_get_url)

    with TemporaryDirectory() as output_dir:
        cli = Cli()
        cli._setup_settings()

        assert 0 == cli.run(cmd + ["--base", base_url, "--outputdir", output_dir])

        out, err = capsys.readouterr()
        sys.stdout.write(out)
        sys.stderr.write(err)

        assert expect_out.match(err)

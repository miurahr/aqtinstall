import logging
import os
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import py7zr
import pytest
from pytest_socket import disable_socket

from aqt.installer import Cli


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
            assert False, "Did not expect to call terminate during unit test"


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


FILENAME = "filename"
UNPATCHED_CONTENT = "unpatched-content"
PATCHED_CONTENT = "expected-content"

GET_URL_TYPE = Callable[[str, Any], str]
DOWNLOAD_ARCHIVE_TYPE = Callable[[str, str, str, bytes, Any], None]


def make_mock_geturl_download_archive(
    archive_filename: str,
    qt_version: str,
    arch: str,
    arch_dir: str,
    os_name: str,
    updates_url: str,
    compressed_files: Iterable[Dict[str, str]],
) -> Tuple[GET_URL_TYPE, DOWNLOAD_ARCHIVE_TYPE]:
    """
    Returns a mock 'getUrl' and a mock 'downloadArchive' function.
    """
    assert archive_filename.endswith(".7z")

    def mock_getUrl(url: str, *args) -> str:
        if url.endswith(updates_url):
            qt_major_nodot = "59" if qt_version == "5.9.0" else f"qt{qt_version[0]}.{qt_version.replace('.', '')}"
            _xml = textwrap.dedent(
                f"""\
                <Updates>
                 <PackageUpdate>
                  <Name>qt.{qt_major_nodot}.{arch}</Name>
                  <Description>>Qt {qt_version} for {arch}</Description>
                  <Version>{qt_version}-0-{datetime.now().strftime("%Y%m%d%H%M")}</Version>
                  <DownloadableArchives>{archive_filename}</DownloadableArchives>
                 </PackageUpdate>
                </Updates>
                """
            )

            return _xml
        elif url.endswith(".sha1"):
            return ""  # Skip the checksum
        assert False

    def mock_download_archive(url: str, out: str, *args):
        """Make a mocked 7z archive at out_filename"""
        assert out == archive_filename

        with TemporaryDirectory() as temp_dir, py7zr.SevenZipFile(archive_filename, "w") as archive:
            temp_path = Path(temp_dir)

            for folder in ("bin", "lib", "mkspecs"):
                (temp_path / arch_dir / folder).mkdir(parents=True, exist_ok=True)

            # Use `compressed_files` to write qmake binary, qmake script, QtCore binaries, etc
            for file in compressed_files:
                full_path = temp_path / arch_dir / file[FILENAME]
                if not full_path.parent.exists():
                    full_path.parent.mkdir(parents=True)
                full_path.write_text(file[UNPATCHED_CONTENT], "utf_8")

            archive.writeall(path=temp_path, arcname=qt_version)

    return mock_getUrl, mock_download_archive


@pytest.fixture(autouse=True)
def disable_sockets_and_multiprocessing(monkeypatch):
    # This blocks all network connections, causing test failure if we used monkeypatch wrong
    disable_socket()

    # This blocks all multiprocessing, which would otherwise spawn processes that are not monkeypatched
    monkeypatch.setattr(
        "aqt.installer.multiprocessing.get_context",
        lambda *args: MockMultiprocessingContext(),
    )

    monkeypatch.setattr(
        "aqt.installer.multiprocessing.Manager",
        MockMultiprocessingManager,
    )


@pytest.mark.parametrize(
    "cmd, host, target, version, arch, arch_dir, updates_url, files, expect_out",
    (
        (
            "install 5.14.0 windows desktop win32_mingw73".split(),
            "windows",
            "desktop",
            "5.14.0",
            "win32_mingw73",
            "mingw73_32",
            "windows_x86/desktop/qt5_5140/Updates.xml",
            (
                {
                    FILENAME: "mkspecs/qconfig.pri",
                    UNPATCHED_CONTENT: "... blah blah blah ...\n"
                    "QT_EDITION = Not OpenSource\n"
                    "QT_LICHECK = Not Empty\n"
                    "... blah blah blah ...\n",
                    PATCHED_CONTENT: "... blah blah blah ...\n"
                    "QT_EDITION = OpenSource\n"
                    "QT_LICHECK =\n"
                    "... blah blah blah ...\n",
                },
            ),
            re.compile(
                r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"Warning: The command 'install' is deprecated and marked for removal in a future version of aqt.\n"
                r"In the future, please use the command 'install-qt' instead.\n"
                r"Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win32_mingw73.7z in .*\n"
                r"Finished installation\n"
                r"Time elapsed: .* second"
            ),
        ),
        (
            "install 5.9.0 windows desktop win32_mingw53".split(),
            "windows",
            "desktop",
            "5.9.0",
            "win32_mingw53",
            "mingw53_32",
            "windows_x86/desktop/qt5_59/Updates.xml",
            (
                {
                    FILENAME: "mkspecs/qconfig.pri",
                    UNPATCHED_CONTENT: "... blah blah blah ...\n"
                    "QT_EDITION = Not OpenSource\n"
                    "QT_LICHECK = Not Empty\n"
                    "... blah blah blah ...\n",
                    PATCHED_CONTENT: "... blah blah blah ...\n"
                    "QT_EDITION = OpenSource\n"
                    "QT_LICHECK =\n"
                    "... blah blah blah ...\n",
                },
            ),
            re.compile(
                r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"Warning: The command 'install' is deprecated and marked for removal in a future version of aqt.\n"
                r"In the future, please use the command 'install-qt' instead.\n"
                r"Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win32_mingw53.7z in .*\n"
                r"Finished installation\n"
                r"Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 5.9.0 win32_mingw53".split(),
            "windows",
            "desktop",
            "5.9.0",
            "win32_mingw53",
            "mingw53_32",
            "windows_x86/desktop/qt5_59/Updates.xml",
            (
                {
                    FILENAME: "mkspecs/qconfig.pri",
                    UNPATCHED_CONTENT: "... blah blah blah ...\n"
                    "QT_EDITION = Not OpenSource\n"
                    "QT_LICHECK = Not Empty\n"
                    "... blah blah blah ...\n",
                    PATCHED_CONTENT: "... blah blah blah ...\n"
                    "QT_EDITION = OpenSource\n"
                    "QT_LICHECK =\n"
                    "... blah blah blah ...\n",
                },
            ),
            re.compile(
                r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win32_mingw53.7z in .*\n"
                r"Finished installation\n"
                r"Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 5.14.0 win32_mingw73".split(),
            "windows",
            "desktop",
            "5.14.0",
            "win32_mingw73",
            "mingw73_32",
            "windows_x86/desktop/qt5_5140/Updates.xml",
            (
                {
                    FILENAME: "mkspecs/qconfig.pri",
                    UNPATCHED_CONTENT: "... blah blah blah ...\n"
                    "QT_EDITION = Not OpenSource\n"
                    "QT_LICHECK = Not Empty\n"
                    "... blah blah blah ...\n",
                    PATCHED_CONTENT: "... blah blah blah ...\n"
                    "QT_EDITION = OpenSource\n"
                    "QT_LICHECK =\n"
                    "... blah blah blah ...\n",
                },
            ),
            re.compile(
                r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win32_mingw73.7z in .*\n"
                r"Finished installation\n"
                r"Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows android 6.1.0 android_armv7".split(),
            "windows",
            "android",
            "6.1.0",
            "android_armv7",
            "android_armv7",
            "windows_x86/android/qt6_610_armv7/Updates.xml",
            (
                # Qt 6 non-desktop should patch qconfig.pri, qmake script and target_qt.conf
                {
                    FILENAME: "mkspecs/qconfig.pri",
                    UNPATCHED_CONTENT: "... blah blah blah ...\n"
                    "QT_EDITION = Not OpenSource\n"
                    "QT_LICHECK = Not Empty\n"
                    "... blah blah blah ...\n",
                    PATCHED_CONTENT: "... blah blah blah ...\n"
                    "QT_EDITION = OpenSource\n"
                    "QT_LICHECK =\n"
                    "... blah blah blah ...\n",
                },
                {
                    FILENAME: "bin/target_qt.conf",
                    UNPATCHED_CONTENT: "Prefix=/Users/qt/work/install/target\n" "HostPrefix=../../\n" "HostData=target\n",
                    PATCHED_CONTENT: "Prefix={base_dir}{sep}6.1.0{sep}android_armv7{sep}target\n"
                    "HostPrefix=../../mingw81_64\n"
                    "HostData=../android_armv7\n",
                },
                {
                    FILENAME: "bin/qmake.bat",
                    UNPATCHED_CONTENT: "... blah blah blah ...\n" "/Users/qt/work/install/bin\n" "... blah blah blah ...\n",
                    PATCHED_CONTENT: "... blah blah blah ...\n"
                    "{base_dir}\\6.1.0\\mingw81_64\\bin\n"
                    "... blah blah blah ...\n",
                },
            ),
            re.compile(
                r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-android_armv7.7z in .*\n"
                r"Patching .*/bin/qmake.bat\n"
                r"Finished installation\n"
                r"Time elapsed: .* second"
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
    arch: str,
    arch_dir: str,
    updates_url: str,
    files: Iterable[Dict[str, str]],
    expect_out,  # type: re.Pattern
):

    archive_filename = f"qtbase-{host}-{arch}.7z"
    mock_get_url, mock_download_archive = make_mock_geturl_download_archive(
        archive_filename, version, arch, arch_dir, host, updates_url, files
    )
    monkeypatch.setattr("aqt.archives.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.installer.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.installer.downloadBinaryFile", mock_download_archive)

    with TemporaryDirectory() as output_dir:
        cli = Cli()
        cli._setup_settings()

        cli.run(cmd + ["--outputdir", output_dir])

        out, err = capsys.readouterr()
        sys.stdout.write(out)
        sys.stderr.write(err)

        assert expect_out.match(err)

        installed_path = Path(output_dir) / version / arch_dir
        assert installed_path.is_dir()
        for patched_file in files:
            file_path = installed_path / patched_file[FILENAME]
            assert file_path.is_file()
            expect_content = patched_file[PATCHED_CONTENT].format(base_dir=output_dir, sep=os.sep)
            patched_content = file_path.read_text(encoding="utf_8")
            assert patched_content == expect_content

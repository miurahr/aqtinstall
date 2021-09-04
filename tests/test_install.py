import logging
import os
import re
import sys
import textwrap
from dataclasses import dataclass
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


GET_URL_TYPE = Callable[[str, Any], str]
DOWNLOAD_ARCHIVE_TYPE = Callable[[str, str, str, bytes, Any], None]
LIST_OF_FILES_AND_CONTENTS = Iterable[Dict[str, str]]


@dataclass
class PatchedFile:
    filename: str
    unpatched_content: str
    patched_content: Optional[str]

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

    def xml_package_update(self) -> str:
        return textwrap.dedent(
            f"""\
             <PackageUpdate>
              <Name>{self.update_xml_name}</Name>
              <Version>{self.version}-0-{datetime.now().strftime("%Y%m%d%H%M")}</Version>
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
    archives: Iterable[MockArchive],
    arch: str,
    os_name: str,
    updates_url: str,
) -> Tuple[GET_URL_TYPE, DOWNLOAD_ARCHIVE_TYPE]:
    """
    Returns a mock 'getUrl' and a mock 'downloadArchive' function.
    """
    for _arc in archives:
        assert _arc.filename_7z.endswith(".7z")

    def mock_getUrl(url: str, *args) -> str:
        if url.endswith(updates_url):
            return "<Updates>\n{}\n</Updates>".format("\n".join([archive.xml_package_update() for archive in archives]))
        elif url.endswith(".sha1"):
            return ""  # Skip the checksum
        assert False

    def mock_download_archive(url: str, out: str, *args):
        """Make a mocked 7z archive at out_filename"""

        def locate_archive() -> MockArchive:
            for arc in archives:
                if out == arc.filename_7z:
                    return arc
            assert False, "Requested an archive that was not mocked"

        locate_archive().write_compressed_archive(Path("./"))

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


def plain_qtbase_archive(update_xml_name: str, arch: str) -> MockArchive:
    return MockArchive(
        filename_7z=f"qtbase-windows-{arch}.7z",
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
    )


@pytest.mark.parametrize(
    "cmd, host, target, version, arch, arch_dir, updates_url, archives, expect_out",
    (
        (
            "install 5.14.0 windows desktop win32_mingw73".split(),
            "windows",
            "desktop",
            "5.14.0",
            "win32_mingw73",
            "mingw73_32",
            "windows_x86/desktop/qt5_5140/Updates.xml",
            [
                plain_qtbase_archive("qt.qt5.5140.win32_mingw73", "win32_mingw73"),
            ],
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
            [
                plain_qtbase_archive("qt.59.win32_mingw53", "win32_mingw53"),
            ],
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
            [
                plain_qtbase_archive("qt.59.win32_mingw53", "win32_mingw53"),
            ],
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
            [
                plain_qtbase_archive("qt.qt5.5140.win32_mingw73", "win32_mingw73"),
            ],
            re.compile(
                r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win32_mingw73.7z in .*\n"
                r"Finished installation\n"
                r"Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 5.14.0 win64_mingw73 -m qtcharts".split(),
            "windows",
            "desktop",
            "5.14.0",
            "win64_mingw73",
            "mingw73_64",
            "windows_x86/desktop/qt5_5140/Updates.xml",
            [
                plain_qtbase_archive("qt.qt5.5140.win64_mingw73", "win64_mingw73"),
                qtcharts_module("5.14.0", "win64_mingw73"),
            ],
            re.compile(
                r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win64_mingw73.7z in .*\n"
                r"Downloading qtcharts...\n"
                r"Finished installation of qtcharts-windows-win64_mingw73.7z in .*\n"
                r"Finished installation\n"
                r"Time elapsed: .* second"
            ),
        ),
        (
            "install-qt windows desktop 6.1.0 win64_mingw81 -m qtcharts".split(),
            "windows",
            "desktop",
            "6.1.0",
            "win64_mingw81",
            "mingw81_64",
            "windows_x86/desktop/qt6_610/Updates.xml",
            [
                plain_qtbase_archive("qt.qt6.610.win64_mingw81", "win64_mingw81"),
                qtcharts_module("6.1.0", "win64_mingw81"),
            ],
            re.compile(
                r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"Downloading qtbase...\n"
                r"Finished installation of qtbase-windows-win64_mingw81.7z in .*\n"
                r"Downloading qtcharts...\n"
                r"Finished installation of qtcharts-windows-win64_mingw81.7z in .*\n"
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
            [
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
                            "HostPrefix=../../mingw81_64\n"
                            "HostData=../android_armv7\n",
                        ),
                        PatchedFile(
                            filename="bin/qmake.bat",
                            unpatched_content="... blah blah blah ...\n"
                            "/Users/qt/work/install/bin\n"
                            "... blah blah blah ...\n",
                            patched_content="... blah blah blah ...\n"
                            "{base_dir}\\6.1.0\\mingw81_64\\bin\n"
                            "... blah blah blah ...\n",
                        ),
                    ),
                ),
            ],
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
    archives: List[MockArchive],
    expect_out,  # type: re.Pattern
):

    # For convenience, fill in version and arch dir: prevents repetitive data declarations
    for i in range(len(archives)):
        archives[i].version = version
        archives[i].arch_dir = arch_dir

    mock_get_url, mock_download_archive = make_mock_geturl_download_archive(archives, arch, host, updates_url)
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
        if version == "5.9.0":
            installed_path = Path(output_dir) / "5.9" / arch_dir
        assert installed_path.is_dir()
        for archive in archives:
            for patched_file in archive.contents:
                file_path = installed_path / patched_file.filename
                assert file_path.is_file()

                expect_content = patched_file.expected_content(base_dir=output_dir, sep=os.sep)
                actual_content = file_path.read_text(encoding="utf_8")
                assert actual_content == expect_content


@pytest.mark.parametrize(
    "cmd, xml_file, expected_re, expect_missing",
    (
        (
            "install-qt windows desktop 5.15.0 win32_mingw73 -m nonexistent foo",
            "windows-5150-update.xml",
            # Match output: Note that the set of missing package names will be in random order.
            re.compile(
                r"^aqtinstall\(aqt\) v.+\n"
                r"Some of specified modules are unknown\.\n"
                r"The packages {(.+)} were not found while parsing XML of package information!$"
            ),
            {"qt_base", "nonexistent", "foo"},
        ),
        (
            "install-src windows desktop 5.15.0 -m nonexistent foo",
            "windows-5152-src-doc-example-update.xml",
            # Match output: Note that the set of missing package names will be in random order.
            re.compile(
                r"^aqtinstall\(aqt\) v.+\n" r"The packages {(.+)} were not found while parsing XML of package information!$"
            ),
            {"src", "nonexistent", "foo"},
        ),
        # (
        #     "install-tool windows desktop tools_nonexistent nonexistent",
        #     # Match output: Note that the set of missing package names will be in random order.
        #     re.compile(
        #         r"^aqtinstall\(aqt\) v.+\n"
        #         r"Specified target combination is not valid: windows tools_nonexistent nonexistent\n"
        #         r"The packages {(.+)} were not found while parsing XML of package information!$"
        #     ),
        #     {'nonexistent'}
        # )
    ),
)
def test_install_bad_tools_modules(monkeypatch, capsys, cmd, xml_file, expected_re, expect_missing):
    xml = (Path(__file__).parent / "data" / xml_file).read_text("utf-8")

    def mock_get_url(self, url):
        return xml

    monkeypatch.setattr("aqt.archives.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.installer.getUrl", mock_get_url)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        cli = Cli()
        cli._setup_settings()
        cli.run(cmd.split())
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1

    out, err = capsys.readouterr()
    match = expected_re.match(err)
    assert match
    actual = set(map(lambda x: x[1:-1], match.group(1).split(", ")))
    assert actual == expect_missing

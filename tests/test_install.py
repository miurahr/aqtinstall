import errno
import hashlib
import logging
import os
import posixpath
import re
import subprocess
import sys
import tarfile
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
    extract_target: Optional[str] = None
    date: datetime = datetime.now()

    def xml_package_update(self) -> str:
        if self.extract_target:
            return textwrap.dedent(
                f"""\
                 <PackageUpdate>
                  <Name>{self.update_xml_name}</Name>
                  <Version>{self.version}-0-{self.date.strftime("%Y%m%d%H%M")}</Version>
                  <Description>none</Description>
                  <DownloadableArchives>{self.filename_7z}</DownloadableArchives>
                  <Operations>
                   <Operation name="Extract">
                    <Argument>{self.extract_target}</Argument>
                    <Argument>{self.filename_7z}</Argument>
                   </Operation>
                  </Operations>
                 </PackageUpdate>"""
            )
        else:
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
        def open_writable_archive():
            if self.filename_7z.endswith(".7z"):
                return py7zr.SevenZipFile(dest / self.filename_7z, "w")
            elif self.filename_7z.endswith(".tar.xz"):
                return tarfile.open(dest / self.filename_7z, "w:xz")
            # elif self.filename_7z.endswith(".zip"):
            #     return tarfile.open(dest / "DUMMY-NOT-USED", "w")
            else:
                assert False, "Archive type not supported"

        def write_to_archive(arc, src, arcname):
            if self.filename_7z.endswith(".7z"):
                arc.writeall(path=src, arcname=arcname)
            elif self.filename_7z.endswith(".tar.xz"):
                arc.add(name=src, arcname=arcname)
            # elif self.filename_7z.endswith(".zip"):
            #     shutil.make_archive(str(dest / self.filename_7z), "zip", src)

        with TemporaryDirectory() as temp_dir, open_writable_archive() as archive:
            # if the Updates.xml file uses Operations/Operation[@name='Extract'] elements then the names
            # of archive members do not include the version and arch_dir path segments, instead they are
            # supplied by an Argument element which is used when the archive is extracted.
            temp_path = Path(temp_dir)
            arch_dir = self.arch_dir if not self.extract_target else ""

            # Create directories first
            for folder in ("bin", "lib", "mkspecs"):
                (temp_path / arch_dir / folder).mkdir(parents=True, exist_ok=True)

            # Write all content files and make executable if in bin/
            for patched_file in self.contents:
                full_path = temp_path / arch_dir / patched_file.filename
                if not full_path.parent.exists():
                    full_path.parent.mkdir(parents=True)
                full_path.write_text(patched_file.unpatched_content, "utf_8")
                if "bin/" in patched_file.filename:
                    # Make all files in bin executable
                    full_path.chmod(full_path.stat().st_mode | 0o111)

            if self.extract_target:
                archive_name = "."
            else:
                archive_name = "5.9" if self.version == "5.9.0" else self.version
            write_to_archive(archive, temp_path, arcname=archive_name)


def make_mock_geturl_download_archive(
    *,
    standard_archives: List[MockArchive],
    desktop_archives: Optional[List[MockArchive]] = None,
    extpdf_archives: Optional[List[MockArchive]] = None,
    extweb_archives: Optional[List[MockArchive]] = None,
    standard_updates_url: str,
    desktop_updates_url: str = "",
    extpdf_updates_url: str = "",
    extweb_updates_url: str = "",
) -> Tuple[GET_URL_TYPE, DOWNLOAD_ARCHIVE_TYPE]:
    """
    Returns a mock 'getUrl' and a mock 'downloadArchive' function.
    """
    if desktop_archives is None:
        desktop_archives = []
    if extpdf_archives is None:
        extpdf_archives = []
    if extweb_archives is None:
        extweb_archives = []
    for _archive in [*standard_archives, *desktop_archives, *extpdf_archives, *extweb_archives]:
        assert re.match(r".*\.(7z|tar\.xz)$", _archive.filename_7z), "Unsupported file type"

    def _generate_package_update_xml(archive: MockArchive) -> str:
        """Helper to generate package XML with proper addon structure for Qt 6.8"""
        is_qt68_addon = (
            archive.version.startswith("6.8")
            and "addons" in archive.update_xml_name
            and not archive.update_xml_name.endswith(("_64", "_arm64", "_32", "wasm_singlethread"))
        )

        return textwrap.dedent(
            f"""\
            <PackageUpdate>
             <Name>{archive.update_xml_name}</Name>
             <Version>{archive.version}-0-{archive.date.strftime("%Y%m%d%H%M")}</Version>
             <Description>{getattr(archive, 'package_desc', 'none')}</Description>
             <DownloadableArchives>{archive.filename_7z}</DownloadableArchives>
             {f'<Dependencies>qt.qt6.680.gcc_64</Dependencies>' if is_qt68_addon else ''}
            </PackageUpdate>"""
        )

    standard_xml = "<Updates>\n{}\n</Updates>".format(
        "\n".join([_generate_package_update_xml(archive) for archive in standard_archives])
    )
    desktop_xml = "<Updates>\n{}\n</Updates>".format(
        "\n".join([_generate_package_update_xml(archive) for archive in desktop_archives])
    )
    extpdf_xml = "<Updates>\n{}\n</Updates>".format("\n".join([archive.xml_package_update() for archive in extpdf_archives]))
    extweb_xml = "<Updates>\n{}\n</Updates>".format("\n".join([archive.xml_package_update() for archive in extweb_archives]))
    merged_xml = "<Updates>\n{}{}\n</Updates>".format(
        "\n".join([_generate_package_update_xml(archive) for archive in standard_archives]),
        "\n".join([_generate_package_update_xml(archive) for archive in desktop_archives]),
    )

    # Empty extension XML response
    empty_extension_xml = "<Updates></Updates>"

    # Extension URLs and their corresponding XMLs for Qt {}+
    qt68_extensions = {
        # Desktop extensions
        "/extensions/qtwebengine/680/x86_64/": empty_extension_xml,
        "/extensions/qtpdf/680/x86_64/": empty_extension_xml,
        # WASM extensions
        "/extensions/qtwebengine/680/wasm_singlethread/": empty_extension_xml,
        "/extensions/qtpdf/680/wasm_singlethread/": empty_extension_xml,
    }

    def mock_getUrl(url: str, *args, **kwargs) -> str:
        # Handle main Updates.xml files
        if standard_updates_url == desktop_updates_url and url.endswith(standard_updates_url):
            return merged_xml
        for xml, updates_url in (
            (standard_xml, standard_updates_url),
            (desktop_xml, desktop_updates_url),
            (extpdf_xml, extpdf_updates_url),
            (extweb_xml, extweb_updates_url),
        ):
            basename = posixpath.dirname(updates_url)
            if not updates_url:
                continue
            elif url.endswith(updates_url):
                return xml
            elif basename in url and url.endswith(".sha256"):
                filename = url.split("/")[-1][: -len(".sha256")]
                return f"{hashlib.sha256(bytes(xml, 'utf-8')).hexdigest()} {filename}"

        # Handle extension URLs
        for ext_path, ext_xml in qt68_extensions.items():
            if ext_path in url:
                if url.endswith(".sha256"):
                    return f"{hashlib.sha256(bytes(ext_xml, 'utf-8')).hexdigest()} Updates.xml"
                elif url.endswith("Updates.xml"):
                    return ext_xml

        """
        extensions urls may or may not exist.
        """
        if "/extensions/" in url:
            raise ArchiveDownloadError(f"Failed to retrieve file at {url}\nServer response code: 404, reason: Not Found")

        assert False, f"No mocked url available for '{url}'"

    def mock_download_archive(url: str, out: str, *args):
        """Make a mocked 7z archive at out_filename"""

        def locate_archive() -> MockArchive:
            for archive in [*standard_archives, *desktop_archives, *extpdf_archives, *extweb_archives]:
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
    os_name = {
        "linux_gcc_64": "linux",
        "gcc_64": "linux",
        "linux_gcc_arm64": "linux",
        "wasm_singlethread": "windows",  # Keep windows for wasm
        "wasm_multithread": "windows",
    }.get(arch, "windows")

    return MockArchive(
        filename_7z=f"qtcharts-{os_name}-{arch}.7z",  # Use os_name lookup
        update_xml_name=f"{prefix}.{ver.replace('.', '')}.{addons}qtcharts.{arch}",
        version=ver,
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
                            "target_system": "{os_name.title()}"
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
    os_name = {
        "linux_gcc_64": "linux",
        "gcc_64": "linux",
        "linux_gcc_arm64": "linux",
        "wasm_singlethread": "windows",  # Keep windows for wasm
        "wasm_multithread": "windows",
    }.get(arch, "windows")
    return MockArchive(
        filename_7z=f"qtlocation-{os_name}-{arch}.7z",  # Use os_name lookup
        update_xml_name=f"{prefix}.{ver.replace('.', '')}.{addons}qtpositioning.{arch}",
        version=ver,
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
                            "target_system": "{os_name.title()}"
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
            "install-tool linux desktop sdktool qt.tools.qtcreator".split(),
            "linux",
            "desktop",
            "10.0.1-0-202305050734",
            {"std": ""},
            {"std": ""},
            {"std": "linux_x64/desktop/sdktool/Updates.xml"},
            {"std": [tool_archive("linux", "sdktool", "qt.tools.qtcreator")]},
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qt.tools.qtcreator...\n"
                r"Finished installation of sdktool-linux-qt.tools.qtcreator.7z in .*\n"
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
            "install-src linux desktop 6.5.0".split(),
            "linux",
            "desktop",
            "6.5.0",
            {"std": ""},
            {"std": ""},
            {"std": "linux_x64/desktop/qt6_650_src_doc_examples/Updates.xml"},
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-everywhere-src-6.5.0.tar.xz",
                        update_xml_name="qt.qt6.650.src",
                        version="6.5.0",
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
                r"([^\n]*Extracting may be unsafe; consider updating Python to 3.11.4 or greater\n)?"
                r"Finished installation of qtbase-everywhere-src-6\.5\.0\.tar\.xz in .*\n"
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
                r"INFO    : Patching .*6\.1\.0[/\\]android_armv7[/\\]bin[/\\]target_qt.conf\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        # --autodesktop test edited
        (
            "install-qt windows desktop 6.5.2 win64_msvc2019_arm64 --autodesktop".split(),
            "windows",
            "desktop",
            "6.5.2",
            {"std": "win64_msvc2019_arm64", "desk": "win64_msvc2019_64"},
            {"std": "msvc2019_arm64", "desk": "msvc2019_64"},
            {
                "std": "windows_x86/desktop/qt6_652/Updates.xml",
                "desk": "windows_x86/desktop/qt6_652/Updates.xml",
            },
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-windows-win64_msvc2019_arm64.7z",
                        update_xml_name="qt.qt6.652.win64_msvc2019_arm64",
                        contents=(
                            # Qt 6 msvc-arm64 should patch qconfig.pri, qmake script and target_qt.conf
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
                                patched_content="Prefix={base_dir}{sep}6.5.2{sep}msvc2019_arm64{sep}target\n"
                                "HostPrefix=../../msvc2019_64\n"
                                "HostData=../msvc2019_arm64\n",
                            ),
                            PatchedFile(
                                filename="bin/qmake.bat",
                                unpatched_content="... blah blah blah ...\n"
                                "/Users/qt/work/install/bin\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "{base_dir}\\6.5.2\\msvc2019_64\\bin\n"
                                "... blah blah blah ...\n",
                            ),
                            PatchedFile(
                                filename="bin/qtpaths.bat",
                                unpatched_content="... blah blah blah ...\n"
                                "/Users/qt/work/install/bin\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "{base_dir}\\6.5.2\\msvc2019_64\\bin\n"
                                "... blah blah blah ...\n",
                            ),
                            PatchedFile(
                                filename="bin/qmake6.bat",
                                unpatched_content="... blah blah blah ...\n"
                                "/Users/qt/work/install/bin\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "{base_dir}\\6.5.2\\msvc2019_64\\bin\n"
                                "... blah blah blah ...\n",
                            ),
                            PatchedFile(
                                filename="bin/qtpaths6.bat",
                                unpatched_content="... blah blah blah ...\n"
                                "/Users/qt/work/install/bin\n"
                                "... blah blah blah ...\n",
                                patched_content="... blah blah blah ...\n"
                                "{base_dir}\\6.5.2\\msvc2019_64\\bin\n"
                                "... blah blah blah ...\n",
                            ),
                        ),
                    ),
                ],
                "desk": [plain_qtbase_archive("qt.qt6.652.win64_msvc2019_64", "win64_msvc2019_64", host="windows")],
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : You are installing the MSVC Arm64 version of Qt\n"
                r"INFO    : Downloading qtbase...\n"
                r"(?:.*\n)*?"
                r"(INFO    : Patching .*?[/\\]6\.5\.2[/\\]msvc2019_arm64[/\\]bin[/\\](?:qmake|qtpaths)(?:6)?\.bat\n)*"
                r"INFO    : \n"
                r"INFO    : Autodesktop will now install windows desktop 6\.5\.2 "
                r"win64_msvc2019_64 as required by MSVC Arm64\n"
                r"INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qtbase...\n"
                r"(?:.*\n)*$"
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
                            PatchedFile(
                                filename="bin/qtpaths",
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
                r"INFO    : Patching .*6\.4\.1[/\\]android_arm64_v8a[/\\]bin[/\\]qtpaths\n"
                r"INFO    : Patching .*6\.4\.1[/\\]android_arm64_v8a[/\\]bin[/\\]target_qt.conf\n"
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
                            PatchedFile(
                                filename="bin/qtpaths",
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
                r"INFO    : Patching .*6\.3\.0[/\\]android_arm64_v8a[/\\]bin[/\\]qtpaths\n"
                r"INFO    : Patching .*6\.3\.0[/\\]android_arm64_v8a[/\\]bin[/\\]target_qt.conf\n"
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
                r"INFO    : Patching .*6\.1\.2[/\\]ios[/\\]bin[/\\]target_qt.conf\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        # --autodesktop test edited
        (
            "install-qt mac ios 6.1.2 --autodesktop".split(),
            "mac",
            "ios",
            "6.1.2",
            {"std": "ios", "desk": "clang_64"},
            {"std": "ios", "desk": "macos"},
            {
                "std": "mac_x64/ios/qt6_612/Updates.xml",
                "desk": "mac_x64/desktop/qt6_612/Updates.xml",
            },
            {
                "std": [
                    MockArchive(
                        filename_7z="qtbase-mac-ios.7z",
                        update_xml_name="qt.qt6.612.ios",
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
                r"INFO    : You are installing the ios version of Qt\n"
                r"INFO    : Downloading qtbase...\n"
                r"(?:.*\n)*?"
                r"INFO    : Patching .*?[/\\]6\.1\.2[/\\]ios[/\\]bin[/\\]qmake\n"
                r"INFO    : Patching .*?[/\\]6\.1\.2[/\\]ios[/\\]bin[/\\]target_qt.conf\n"
                r"INFO    : \n"
                r"INFO    : Autodesktop will now install mac desktop 6\.1\.2 clang_64 as required by ios\n"
                r"INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Downloading qtbase...\n"
                r"(?:.*\n)*$"
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
                            PatchedFile(
                                filename="bin/qtpaths.bat",
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
                r"INFO    : Patching .*6\.2\.4[/\\]wasm_32[/\\]bin[/\\]qtpaths.bat\n"
                r"INFO    : Patching .*6\.2\.4[/\\]wasm_32[/\\]bin[/\\]target_qt.conf\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (  # extensions availability: qtpdf and qtwebengine
            "install-qt windows desktop 6.8.1 win64_msvc2022_64 -m qtwebengine".split(),
            "windows",
            "desktop",
            "6.8.1",
            {"std": "win64_msvc2022_64", "extpdf": "win64_msvc2022_64", "extweb": "win64_msvc2022_64"},
            {"std": "msvc2022_64", "extpdf": "msvc2022_64", "extweb": "msvc2022_64"},
            {
                "std": "windows_x86/desktop/qt6_681/qt6_681/Updates.xml",
                "extpdf": "windows_x86/extensions/qtpdf/681/msvc2022_64/Updates.xml",
                "extweb": "windows_x86/extensions/qtwebengine/681/msvc2022_64/Updates.xml",
            },
            {
                "std": [
                    plain_qtbase_archive(
                        "qt.qt6.681.win64_msvc2022_64",
                        "Windows-Windows_11_23H2-X86_64",
                        host="Windows-Windows_11_23H2-MSVC2022",
                    )
                ],
                "extpdf": [
                    MockArchive(
                        filename_7z="qtpdf-Windows-Windows_11_23H2-MSVC2022-Windows-Windows_11_23H2-X86_64.7z",
                        update_xml_name="extensions.qtpdf.681.win64_msvc2022_64",
                        contents=(),
                        should_install=False,
                        extract_target="@TargetDir@/6.8.1/msvc2022_64",
                    ),
                ],
                "extweb": [
                    MockArchive(
                        filename_7z="qtwebengine-Windows-Windows_11_23H2-MSVC2022-Windows-Windows_11_23H2-X86_64.7z",
                        update_xml_name="extensions.qtwebengine.681.win64_msvc2022_64",
                        contents=(
                            PatchedFile(filename="lib/Qt6WebEngineCore.prl", unpatched_content="... qtwebengine ...\n"),
                        ),
                        should_install=False,
                        extract_target="@TargetDir@/6.8.1/msvc2022_64",
                    ),
                ],
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Found extension qtwebengine\n"
                r"INFO    : Found extension qtpdf\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of "
                r"qtbase-Windows-Windows_11_23H2-MSVC2022-Windows-Windows_11_23H2-X86_64.7z in .*\n"
                r"INFO    : Downloading qtwebengine...\n"
                r"Finished installation of "
                r"qtwebengine-Windows-Windows_11_23H2-MSVC2022-Windows-Windows_11_23H2-X86_64.7z in .*\n"
                r"INFO    : Patching .*/6.8.1/msvc2022_64/lib/Qt6WebEngineCore.prl\n"
                r"INFO    : Finished installation\n"
                r"INFO    : Time elapsed: .* second"
            ),
        ),
        (  # extension availability: qtpdf only
            "install-qt windows desktop 6.8.1 win64_mingw -m qtpdf".split(),
            "windows",
            "desktop",
            "6.8.1",
            {"std": "win64_mingw", "extpdf": "win64_mingw"},
            {"std": "mingw_64", "extpdf": "mingw_64"},
            {
                "std": "windows_x86/desktop/qt6_681/qt6_681/Updates.xml",
                "extpdf": "windows_x86/extensions/qtpdf/681/mingw/Updates.xml",
            },
            {
                "std": [
                    plain_qtbase_archive(
                        "qt.qt6.681.win64_mingw",
                        "Windows-Windows_10_22H2-X86_64",
                        host="Windows-Windows_10_22H2-Mingw",
                    )
                ],
                "extpdf": [
                    MockArchive(
                        filename_7z="qtpdf-Windows-Windows_10_22H2-Mingw-Windows-Windows_10_22H2-X86_64.7z",
                        update_xml_name="extensions.qtpdf.681.win64_mingw",
                        contents=(),
                        should_install=False,
                        extract_target="@TargetDir@/6.8.1/mingw_64",
                    ),
                ],
            },
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Found extension qtpdf\n"
                r"INFO    : Downloading qtbase...\n"
                r"Finished installation of qtbase-Windows-Windows_10_22H2-Mingw-Windows-Windows_10_22H2-X86_64.7z in .*\n"
                r"INFO    : Downloading qtpdf...\n"
                r"Finished installation of qtpdf-Windows-Windows_10_22H2-Mingw-Windows-Windows_10_22H2-X86_64.7z in .*\n"
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
    extpdf_archives = archives.get("extpdf", [])
    for i in range(len(extpdf_archives)):
        extpdf_archives[i].version = version
        extpdf_archives[i].arch_dir = arch_dir["extpdf"]
    extweb_archives = archives.get("extweb", [])
    for i in range(len(extweb_archives)):
        extweb_archives[i].version = version
        extweb_archives[i].arch_dir = arch_dir["extweb"]

    mock_get_url, mock_download_archive = make_mock_geturl_download_archive(
        standard_archives=std_archives,
        desktop_archives=desktop_archives,
        extpdf_archives=extpdf_archives,
        extweb_archives=extweb_archives,
        standard_updates_url=updates_url.get("std", ""),
        desktop_updates_url=updates_url.get("desk", ""),
        extpdf_updates_url=updates_url.get("extpdf", ""),
        extweb_updates_url=updates_url.get("extweb", ""),
    )
    monkeypatch.setattr("aqt.archives.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.helper.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.installer.downloadBinaryFile", mock_download_archive)
    monkeypatch.setattr(
        "aqt.metadata.MetadataFactory.fetch_arches",
        lambda *args: [{"windows": "win64_mingw1234", "linux": "gcc_64", "mac": "clang_64"}[host]],
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
    "version, str_version, wasm_arch",
    [
        ("6.8.0", "680", "wasm_singlethread"),
    ],
)
def test_install_qt6_wasm_autodesktop(monkeypatch, capsys, version, str_version, wasm_arch):
    """Test installing Qt 6.8 WASM with autodesktop, which requires special handling for addons"""

    # WASM archives
    wasm_archives = [
        # WASM base package
        MockArchive(
            filename_7z=f"qtbase-{wasm_arch}.7z",
            update_xml_name=f"qt.qt6.{str_version}.{wasm_arch}",  # Base doesn't have addons
            version=version,
            arch_dir=wasm_arch,
            contents=(),
        ),
        # WASM modules - add 'addons' to match XML structure
        MockArchive(
            filename_7z="qtcharts-Windows-Windows_10_22H2-Clang-Windows-WebAssembly-X86_64.7z",
            update_xml_name=f"qt.qt6.{str_version}.addons.qtcharts.{wasm_arch}",
            version=version,
            arch_dir=wasm_arch,
            contents=(),
        ),
        MockArchive(
            filename_7z="qtquick3d-Windows-Windows_10_22H2-Clang-Windows-WebAssembly-X86_64.7z",
            update_xml_name=f"qt.qt6.{str_version}.addons.qtquick3d.{wasm_arch}",
            version=version,
            arch_dir=wasm_arch,
            contents=(),
        ),
    ]

    # Desktop archives for each possible host OS
    desk_archives_by_host = {
        "linux": (
            [
                plain_qtbase_archive(f"qt.qt6.{str_version}.linux_gcc_64", "linux_gcc_64", host="linux"),
                MockArchive(
                    filename_7z="qtcharts-linux-gcc_64.7z",
                    update_xml_name=f"qt.qt6.{str_version}.qtcharts.gcc_64",
                    version=version,
                    arch_dir="gcc_64",
                    contents=(
                        PatchedFile(
                            filename="modules/Charts.json",
                            unpatched_content='{"module_name": "Charts"}',
                            patched_content=None,
                        ),
                    ),
                ),
                MockArchive(
                    filename_7z="qtquick3d-linux-gcc_64.7z",
                    update_xml_name=f"qt.qt6.{str_version}.qtquick3d.gcc_64",
                    version=version,
                    arch_dir="gcc_64",
                    contents=(
                        PatchedFile(
                            filename="modules/Quick3D.json",
                            unpatched_content='{"module_name": "Quick3D"}',
                            patched_content=None,
                        ),
                    ),
                ),
            ],
            "linux_x64",
            "gcc_64",
        ),
        "darwin": (
            [
                plain_qtbase_archive(f"qt.qt6.{str_version}.clang_64", "clang_64", host="mac"),
                MockArchive(
                    filename_7z="qtcharts-mac-clang_64.7z",
                    update_xml_name=f"qt.qt6.{str_version}.qtcharts.clang_64",
                    version=version,
                    arch_dir="clang_64",
                    contents=(
                        PatchedFile(
                            filename="modules/Charts.json",
                            unpatched_content='{"module_name": "Charts"}',
                            patched_content=None,
                        ),
                    ),
                ),
                MockArchive(
                    filename_7z="qtquick3d-mac-clang_64.7z",
                    update_xml_name=f"qt.qt6.{str_version}.qtquick3d.clang_64",
                    version=version,
                    arch_dir="clang_64",
                    contents=(
                        PatchedFile(
                            filename="modules/Quick3D.json",
                            unpatched_content='{"module_name": "Quick3D"}',
                            patched_content=None,
                        ),
                    ),
                ),
            ],
            "mac_x64",
            "clang_64",
        ),
        "win32": (
            [
                plain_qtbase_archive(f"qt.qt6.{str_version}.win64_mingw", "win64_mingw", host="windows"),
                MockArchive(
                    filename_7z="qtcharts-windows-win64_mingw.7z",
                    update_xml_name=f"qt.qt6.{str_version}.qtcharts.win64_mingw",
                    version=version,
                    arch_dir="mingw_64",
                    contents=(
                        PatchedFile(
                            filename="modules/Charts.json",
                            unpatched_content='{"module_name": "Charts"}',
                            patched_content=None,
                        ),
                    ),
                ),
                MockArchive(
                    filename_7z="qtquick3d-windows-win64_mingw.7z",
                    update_xml_name=f"qt.qt6.{str_version}.qtquick3d.win64_mingw",
                    version=version,
                    arch_dir="mingw_64",
                    contents=(
                        PatchedFile(
                            filename="modules/Quick3D.json",
                            unpatched_content='{"module_name": "Quick3D"}',
                            patched_content=None,
                        ),
                    ),
                ),
            ],
            "windows_x86",
            "mingw_64",
        ),
    }

    if sys.platform.startswith("linux"):
        desktop_archives, platform_dir, desk_arch = desk_archives_by_host["linux"]
    elif sys.platform == "darwin":
        desktop_archives, platform_dir, desk_arch = desk_archives_by_host["darwin"]
    else:
        desktop_archives, platform_dir, desk_arch = desk_archives_by_host["win32"]

    def mock_get_url(url: str, *args, **kwargs) -> str:
        wasm_base = f"all_os/wasm/qt6_{str_version}/qt6_{str_version}_{wasm_arch}"
        desktop_base = f"{platform_dir}/desktop/qt6_{str_version}/qt6_{str_version}"

        if url.endswith(".sha256"):
            base = url[:-7]  # Remove .sha256
            if any(base.endswith(path) for path in [f"{wasm_base}/Updates.xml", f"{desktop_base}/Updates.xml"]):
                # For main Updates.xml files, read the appropriate file and generate its hash
                if "wasm" in base:
                    xml = (Path(__file__).parent / "data" / "all_os-680-wasm-single-update.xml").read_text()
                else:
                    if platform_dir == "linux_x64":
                        xml = (Path(__file__).parent / "data" / "linux-680-desktop-update.xml").read_text()
                    else:
                        xml = (Path(__file__).parent / "data" / "windows-680-desktop-update.xml").read_text()
                return f"{hashlib.sha256(bytes(xml, 'utf-8')).hexdigest()} Updates.xml"
            return f"{hashlib.sha256(b'mock').hexdigest()} {url.split('/')[-1][:-7]}"

        # Handle extension URLs for Qt 6.8
        if "/extensions/" in url:
            if url.endswith("Updates.xml"):
                return "<Updates></Updates>"
            if url.endswith(".sha256"):
                return f"{hashlib.sha256(b'mock').hexdigest()} Updates.xml"

        # Handle main Updates.xml files
        if url.endswith(f"{wasm_base}/Updates.xml"):
            return (Path(__file__).parent / "data" / "all_os-680-wasm-single-update.xml").read_text()
        elif url.endswith(f"{desktop_base}/Updates.xml"):
            if platform_dir == "linux_x64":
                return (Path(__file__).parent / "data" / "linux-680-desktop-update.xml").read_text()
            else:
                return (Path(__file__).parent / "data" / "windows-680-desktop-update.xml").read_text()

        assert False, f"No mocked url available for '{url}'"

    def mock_download_archive(url: str, out: Path, *args, **kwargs):
        try:
            # Try to match against our known archives first
            for archives in (wasm_archives, desktop_archives):
                for archive in archives:
                    if Path(out).name == archive.filename_7z:
                        archive.write_compressed_archive(Path(out).parent)
                        return

            # For unknown archives, create basic structure
            with py7zr.SevenZipFile(out, "w") as archive:
                # Determine if this is a desktop archive and get the appropriate arch
                arch_dir = wasm_arch
                for desk_indicator in ["gcc_64", "clang_64", "mingw"]:
                    if desk_indicator in url:
                        if "linux" in url.lower():
                            arch_dir = "gcc_64"
                        elif "mac" in url.lower():
                            arch_dir = "clang_64"
                        else:
                            arch_dir = "mingw_64"
                        break

                # Set the appropriate path prefix
                prefix = f"6.8.0/{arch_dir}"

                basic_files = {
                    f"{prefix}/mkspecs/qconfig.pri": "QT_EDITION = OpenSource\nQT_LICHECK =\n",
                    f"{prefix}/bin/target_qt.conf": "Prefix=...\n",  # Basic config
                    f"{prefix}/bin/qmake": '#!/bin/sh\necho "Mock qmake"\n',
                    f"{prefix}/bin/qmake6": '#!/bin/sh\necho "Mock qmake6"\n',
                    f"{prefix}/bin/qtpaths": '#!/bin/sh\necho "Mock qtpaths"\n',
                    f"{prefix}/bin/qtpaths6": '#!/bin/sh\necho "Mock qtpaths6"\n',
                    f"{prefix}/lib/dummy": "",  # Empty file in lib
                }
                for filepath, content in basic_files.items():
                    archive.writestr(content.encode("utf-8"), filepath)

        except Exception as e:
            sys.stderr.write(f"Warning: Error in mock_download_archive: {e}\n")
            # Even in case of error, create minimal structure
            with py7zr.SevenZipFile(out, "w") as archive:
                # Determine if this is a desktop archive
                if any(desk_indicator in url for desk_indicator in ["gcc_64", "clang_64", "mingw"]):
                    if "linux" in url.lower():
                        prefix = "6.8.0/gcc_64"
                    elif "mac" in url.lower():
                        prefix = "6.8.0/clang_64"
                    else:
                        prefix = "6.8.0/mingw_64"
                else:
                    prefix = f"6.8.0/{wasm_arch}"

                archive.writestr(b"QT_EDITION = OpenSource\nQT_LICHECK =\n", f"{prefix}/mkspecs/qconfig.pri")
                archive.writestr(b'#!/bin/sh\necho "Mock qmake6"\n', f"{prefix}/bin/qmake6")
                archive.writestr(b'#!/bin/sh\necho "Mock qmake"\n', f"{prefix}/bin/qmake")
                archive.writestr(b'#!/bin/sh\necho "Mock qtpaths6"\n', f"{prefix}/bin/qtpaths6")
                archive.writestr(b'#!/bin/sh\necho "Mock qtpaths"\n', f"{prefix}/bin/qtpaths")
                archive.writestr(b"Prefix=...\n", f"{prefix}/bin/target_qt.conf")
        return

    # Setup mocks
    monkeypatch.setattr("aqt.archives.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.helper.getUrl", mock_get_url)
    monkeypatch.setattr("aqt.installer.downloadBinaryFile", mock_download_archive)

    # Run the installation
    with TemporaryDirectory() as output_dir:
        cli = Cli()
        cli._setup_settings()

        result = cli.run(
            [
                "install-qt",
                "all_os",
                "wasm",
                version,
                wasm_arch,
                "-m",
                "qtcharts",
                "qtquick3d",
                "--autodesktop",
                "--outputdir",
                output_dir,
            ]
        )

        assert result == 0

    # Check output format
    out, err = capsys.readouterr()
    sys.stdout.write(out)
    sys.stderr.write(err)

    # Use regex that works for all platforms
    expected_pattern = re.compile(
        r"^INFO    : aqtinstall\(aqt\) v.*? on Python 3.*?\n"
        r"INFO    : You are installing the Qt6-WASM version of Qt\n"
        r"(?:INFO    : Found extension .*?\n)*"
        r"(?:INFO    : Downloading (?:qt[^\n]*|icu[^\n]*)\n"
        r"Finished installation of .*?\.7z in \d+\.\d+\n)*"
        r"(?:INFO    : Patching (?:/tmp/[^/]+|[A-Za-z]:[\\/].*?)/6\.8\.0/wasm_singlethread/bin/(?:qmake(?:6)?|qtpaths(?:6)?|target_qt\.conf)\n)*"
        r"INFO    : \n"
        r"INFO    : Autodesktop will now install linux desktop 6\.8\.0 linux_gcc_64 as required by Qt6-WASM\n"
        r"INFO    : aqtinstall\(aqt\) v.*? on Python 3.*?\n"
        r"(?:INFO    : Found extension .*?\n)*"
        r"(?:INFO    : Downloading (?:qt[^\n]*|icu[^\n]*)\n"
        r"Finished installation of .*?\.7z in \d+\.\d+\n)*"
        r"INFO    : Finished installation\n"
        r"INFO    : Time elapsed: \d+\.\d+ second\n$"
    )

    assert expected_pattern.match(err)


@pytest.mark.parametrize(
    "cmd, xml_file, expected",
    (
        (
            "install-qt windows desktop 5.16.0 win32_mingw73",
            None,
            "ERROR   : Failed to locate XML data for Qt version '5.16.0'.\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-qt windows desktop' to show versions available.\n",
        ),
        (
            "install-qt windows desktop 5.15.0 bad_arch",
            "windows-5150-update.xml",
            "ERROR   : The packages ['qt_base'] were not found while parsing XML of package information!\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-qt windows desktop --arch 5.15.0' to show architectures available.\n",
        ),
        (
            "install-qt windows desktop 5.15.0 win32_mingw73 -m nonexistent foo",
            "windows-5150-update.xml",
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
            "ERROR   : The package 'nonexistent' was not found while parsing XML of package information!\n"
            "==============================Suggested follow-up:==============================\n"
            "* Please use 'aqt list-tool windows desktop tools_vcredist' to show tool variants available.\n",
        ),
        (
            "install-tool windows desktop tools_nonexistent nonexistent",
            None,
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
    monkeypatch.setattr(
        "aqt.archives.get_hash",
        lambda *args, **kwargs: hashlib.sha256(bytes(xml, "utf-8")).hexdigest(),
    )
    monkeypatch.setattr(
        "aqt.metadata.get_hash",
        lambda *args, **kwargs: hashlib.sha256(bytes(xml, "utf-8")).hexdigest(),
    )
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
        with open(Path(temp_dir) / "archive", "w"):
            pass
        installer(
            qt_package=QtPackage(
                "name",
                "base_url",
                "archive_path",
                "archive",
                "archive_install_path",
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
        (
            "install-qt linux_arm64 desktop 6.7 linux_gcc_arm64".split(),
            "linux_arm64",
            "desktop",
            "6.7.0",
            "linux_gcc_arm64",
            "gcc_arm64",
            "https://www.alt.qt.mirror.com",
            "linux_arm64/desktop/qt6_670/Updates.xml",
            [plain_qtbase_archive("qt.qt6.670.linux_gcc_arm64", "linux_gcc_arm64", host="linux_arm64")],
            re.compile(
                r"^INFO    : aqtinstall\(aqt\) v.* on Python 3.*\n"
                r"INFO    : Resolved spec '6\.7' to 6\.7\.0\n"
                r"INFO    : Downloading qtbase\.\.\.\n"
                r"Finished installation of qtbase-linux_arm64-linux_gcc_arm64\.7z in .*\n"
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
        if host == "linux_arm64":
            repo_dir = "linux_arm64"
        elif host == "windows":
            repo_dir = "windows_x86"
        else:
            repo_dir = f"{host}_x64"
        if url == f"{base_url}/online/qtsdkrepository/{repo_dir}/{target}/":
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

        assert expect_out.match(err), err

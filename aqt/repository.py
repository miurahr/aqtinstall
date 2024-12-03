import re
from functools import reduce
from pathlib import Path
from typing import List, Optional, Tuple

from semantic_version import SimpleSpec
from semantic_version import Version as SemanticVersion


class Version(SemanticVersion):
    """Override semantic_version.Version class
    to accept Qt versions and tools versions
    If the version ends in `-preview`, the version is treated as a preview release.
    """

    def __init__(
        self,
        version_string=None,
        major=None,
        minor=None,
        patch=None,
        prerelease=None,
        build=None,
        partial=False,
    ):
        if version_string is None:
            super(Version, self).__init__(
                version_string=None,
                major=major,
                minor=minor,
                patch=patch,
                prerelease=prerelease,
                build=build,
                partial=partial,
            )
            return
        # test qt versions
        match = re.match(r"^(\d+)\.(\d+)(\.(\d+)|-preview)$", version_string)
        if not match:
            # bad input
            raise ValueError("Invalid version string: '{}'".format(version_string))
        major, minor, end, patch = match.groups()
        is_preview = end == "-preview"
        super(Version, self).__init__(
            major=int(major),
            minor=int(minor),
            patch=int(patch) if patch else 0,
            prerelease=("preview",) if is_preview else None,
        )

    def __str__(self):
        if self.prerelease:
            return "{}.{}-preview".format(self.major, self.minor)
        return super(Version, self).__str__()

    @classmethod
    def permissive(cls, version_string: str):
        """Converts a version string with dots (5.X.Y, etc) into a semantic version.
        If the version omits either the patch or minor versions, they will be filled in with zeros,
        and the remaining version string becomes part of the prerelease component.
        If the version cannot be converted to a Version, a ValueError is raised.

        This is intended to be used on Version tags in an Updates.xml file.

        '1.33.1-202102101246' => Version('1.33.1-202102101246')
        '1.33-202102101246' => Version('1.33.0-202102101246')    # tools_conan
        '2020-05-19-1' => Version('2020.0.0-05-19-1')            # tools_vcredist
        """

        match = re.match(r"^(\d+)(\.(\d+)(\.(\d+))?)?(-(.+))?$", version_string)
        if not match:
            raise ValueError("Invalid version string: '{}'".format(version_string))
        major, dot_minor, minor, dot_patch, patch, hyphen_build, build = match.groups()
        return cls(
            major=int(major),
            minor=int(minor) if minor else 0,
            patch=int(patch) if patch else 0,
            build=(build,) if build else None,
        )


class QtRepoProperty:
    """
    Describes properties of the Qt repository at https://download.qt.io/online/qtsdkrepository.
    Intended to help decouple the logic of aqt from specific properties of the Qt repository.
    """

    CATEGORIES = ("tools", "qt")
    HOSTS = ("windows", "windows_arm64", "mac", "linux", "linux_arm64", "all_os")
    TARGETS_FOR_HOST = {
        "windows": ["android", "desktop", "winrt"],
        "windows_arm64": ["desktop"],
        "mac": ["android", "desktop", "ios"],
        "linux": ["android", "desktop"],
        "linux_arm64": ["desktop"],
        "all_os": ["qt", "wasm"],
    }
    EXTENSIONS_REQUIRED_ANDROID_QT6 = {"x86_64", "x86", "armv7", "arm64_v8a"}
    ALL_EXTENSIONS = {"", "wasm", "src_doc_examples", *EXTENSIONS_REQUIRED_ANDROID_QT6}

    @staticmethod
    def arch_conversion_map():
        # Extension arch conversion table from Qt SDK layout
        return {
            # Linux x64
            ("linux", "gcc_64"): ("x86_64", "linux_gcc_64"),
            ("linux", "linux_gcc_64"): ("x86_64", "linux_gcc_64"),
            # Linux ARM64
            ("linux_arm64", "gcc_arm64"): ("arm64", "linux_gcc_arm64"),
            ("linux_arm64", "linux_gcc_arm64"): ("arm64", "linux_gcc_arm64"),
            # Windows
            ("windows", "win64_msvc2022_64"): ("msvc2022_64", "win64_msvc2022_64"),
            ("windows", "win64_mingw"): ("mingw", "win64_mingw"),
            ("windows", "win64_llvm_mingw"): ("llvm_mingw", "win64_llvm_mingw"),
            # macOS
            ("mac", "clang_64"): ("clang_64", "clang_64"),
            ("mac", "ios"): ("ios", "ios"),
            # Android (all_os)
            ("all_os", "android_x86_64"): ("qt6_680_x86_64", "android_x86_64"),
            ("all_os", "android_x86"): ("qt6_680_x86", "android_x86"),
            ("all_os", "android_armv7"): ("qt6_680_armv7", "android_armv7"),
            ("all_os", "android_arm64_v8a"): ("qt6_680_arm64_v8a", "android_arm64_v8a"),
        }

    @staticmethod
    def convert_arch_for_extension(os_name: str, arch: str) -> Tuple[str, str]:
        """Convert architecture name for extensions path and package name
        Returns (folder_arch, package_arch) where:
        - folder_arch: used in the path: <os>_x64/extensions/<module>/<version>/<folder_arch>
        - package_arch: used in package name: extensions.<module>.<version>.<package_arch>
        """
        conversions = QtRepoProperty.arch_conversion_map()
        if (os_name, arch) in conversions:
            return conversions[(os_name, arch)]

        # Default to original arch for both path and package
        return arch, arch

    @staticmethod
    def known_extensions() -> List[str]:
        """Known Qt 6.8.0+ extensions"""
        return ["qtpdf", "qtwebengine"]

    @staticmethod
    def dir_for_version(ver: Version) -> str:
        return "5.9" if ver == Version("5.9.0") else f"{ver.major}.{ver.minor}.{ver.patch}"

    @staticmethod
    def get_arch_dir_name(host: str, arch: str, version: Version) -> str:
        if arch.startswith("win64_mingw"):
            return arch[6:] + "_64"
        elif arch.startswith("win64_llvm"):
            return "llvm-" + arch[11:] + "_64"
        elif arch.startswith("win32_mingw"):
            return arch[6:] + "_32"
        elif arch.startswith("win"):
            m = re.match(r"win\d{2}_(?P<msvc>msvc\d{4})_(?P<winrt>winrt_x\d{2})", arch)
            if m:
                return f"{m.group('winrt')}_{m.group('msvc')}"
            elif arch.endswith("_cross_compiled"):
                return arch[6:-15]
            else:
                return arch[6:]
        elif host == "mac" and arch == "clang_64":
            return QtRepoProperty.default_mac_desktop_arch_dir(version)
        elif host == "linux" and arch in ("gcc_64", "linux_gcc_64"):
            return "gcc_64"
        elif host == "linux_arm64" and arch == "linux_gcc_arm64":
            return "gcc_arm64"
        else:
            return arch

    @staticmethod
    def default_linux_desktop_arch_dir() -> Tuple[str, str]:
        return ("gcc_64", "gcc_arm64")

    @staticmethod
    def default_win_msvc_desktop_arch_dir(_version: Version) -> str:
        if _version >= Version("6.8.0"):
            return "msvc2022_64"
        else:
            return "msvc2019_64"

    @staticmethod
    def default_mac_desktop_arch_dir(version: Version) -> str:
        return "macos" if version in SimpleSpec(">=6.1.2") else "clang_64"

    @staticmethod
    def extension_for_arch(architecture: str, is_version_ge_6: bool) -> str:
        if architecture == "wasm_32":
            return "wasm"
        elif architecture == "wasm_singlethread":
            return "wasm_singlethread"
        elif architecture == "wasm_multithread":
            return "wasm_multithread"
        elif architecture.startswith("android_") and is_version_ge_6:
            ext = architecture[len("android_"):]
            if ext in QtRepoProperty.EXTENSIONS_REQUIRED_ANDROID_QT6:
                return ext
        return ""

    @staticmethod
    def possible_extensions_for_arch(arch: str) -> List[str]:
        """Assumes no knowledge of the Qt version"""
        # ext_ge_6: the extension if the version is greater than or equal to 6.0.0
        # ext_lt_6: the extension if the version is less than 6.0.0
        ext_lt_6, ext_ge_6 = [QtRepoProperty.extension_for_arch(arch, is_ge_6) for is_ge_6 in (False, True)]
        if ext_lt_6 == ext_ge_6:
            return [ext_lt_6]
        return [ext_lt_6, ext_ge_6]

    # Architecture, as reported in Updates.xml
    MINGW_ARCH_PATTERN = re.compile(r"^win(?P<bits>\d+)_mingw(?P<version>\d+)?$")
    # Directory that corresponds to an architecture
    MINGW_DIR_PATTERN = re.compile(r"^mingw(?P<version>\d+)?_(?P<bits>\d+)$")

    @staticmethod
    def select_default_mingw(mingw_arches: List[str], is_dir: bool) -> Optional[str]:
        """
        Selects a default architecture from a non-empty list of mingw architectures, matching the pattern
        MetadataFactory.MINGW_ARCH_PATTERN. Meant to be called on a list of installed mingw architectures,
        or a list of architectures available for installation.
        """
        ArchBitsVer = Tuple[str, int, Optional[int]]
        pattern = QtRepoProperty.MINGW_DIR_PATTERN if is_dir else QtRepoProperty.MINGW_ARCH_PATTERN

        def mingw_arch_with_bits_and_version(arch: str) -> Optional[ArchBitsVer]:
            match = pattern.match(arch)
            if not match:
                return None
            bits = int(match.group("bits"))
            ver = None if not match.group("version") else int(match.group("version"))
            return arch, bits, ver

        def select_superior_arch(lhs: ArchBitsVer, rhs: ArchBitsVer) -> ArchBitsVer:
            _, l_bits, l_ver = lhs
            _, r_bits, r_ver = rhs
            if l_bits != r_bits:
                return lhs if l_bits > r_bits else rhs
            elif r_ver is None:
                return lhs
            elif l_ver is None:
                return rhs
            return lhs if l_ver > r_ver else rhs

        candidates: List[ArchBitsVer] = list(filter(None, map(mingw_arch_with_bits_and_version, mingw_arches)))
        if len(candidates) == 0:
            return None
        default_arch, _, _ = reduce(select_superior_arch, candidates)
        return default_arch

    @staticmethod
    def find_installed_desktop_qt_dir(host: str, base_path: Path, version: Version, is_msvc: bool = False) -> Optional[Path]:
        """
        Locates the default installed desktop qt directory, somewhere in base_path.
        """
        installed_qt_version_dir = base_path / QtRepoProperty.dir_for_version(version)
        if host == "mac":
            arch_path = installed_qt_version_dir / QtRepoProperty.default_mac_desktop_arch_dir(version)
            return arch_path if (arch_path / "bin/qmake").is_file() else None
        elif host == "linux":
            for arch_dir in QtRepoProperty.default_linux_desktop_arch_dir():
                arch_path = installed_qt_version_dir / arch_dir
                if (arch_path / "bin/qmake").is_file():
                    return arch_path
            return None
        elif host == "windows" and is_msvc:
            arch_path = installed_qt_version_dir / QtRepoProperty.default_win_msvc_desktop_arch_dir(version)
            return arch_path if (arch_path / "bin/qmake.exe").is_file() else None

        def contains_qmake_exe(arch_path: Path) -> bool:
            return (arch_path / "bin/qmake.exe").is_file()

        paths = [d for d in installed_qt_version_dir.glob("mingw*")]
        directories = list(filter(contains_qmake_exe, paths))
        arch_dirs = [d.name for d in directories]
        selected_dir = QtRepoProperty.select_default_mingw(arch_dirs, is_dir=True)
        return installed_qt_version_dir / selected_dir if selected_dir else None

    @staticmethod
    def is_in_wasm_range(host: str, version: Version) -> bool:
        if version >= Version("6.7.0"):
            return True
        return (
            version in SimpleSpec(">=6.2.0,<6.5.0")
            or (host == "linux" and version in SimpleSpec(">=5.13,<6"))
            or version in SimpleSpec(">=5.13.1,<6")
        )

    @staticmethod
    def is_in_wasm_threaded_range(version: Version) -> bool:
        return version in SimpleSpec(">=6.5.0")

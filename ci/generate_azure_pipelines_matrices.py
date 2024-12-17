"""
This sets variables for a matrix of QT versions to test downloading against with Azure Pipelines
"""
import collections
import json
import secrets as random
import re
from itertools import product
from typing import Dict, Optional

MIRRORS = [
    "https://ftp.jaist.ac.jp/pub/qtproject",
    "https://ftp1.nluug.nl/languages/qt",
    "https://mirrors.dotsrc.org/qtproject",
]


class BuildJob:

    EMSDK_FOR_QT = {
        "6.2": "2.0.14",
        "6.3": "3.0.0",
        "6.4": "3.1.14",
        "6.5": "3.1.25",
        "6.6": "3.1.37",
        "6.7": "3.1.50",
        "6.8": "3.1.56",
    }

    def __init__(
        self,
        command,
        qt_version,
        host,
        target,
        arch,
        archdir,
        *,
        module=None,
        mirror=None,
        subarchives=None,
        output_dir=None,
        list_options=None,
        spec=None,
        mingw_variant: str = "",
        is_autodesktop: bool = False,
        tool_options: Optional[Dict[str, str]] = None,
        check_output_cmd: Optional[str] = None,
        emsdk_version: str = "sdk-fastcomp-1.38.27-64bit@3.1.29", # did not change for safety, created func self.emsdk_version()
        autodesk_arch_folder: Optional[str] = None,
    ):
        self.command = command
        self.qt_version = qt_version
        self.host = host
        self.target = target
        self.arch = arch
        self.archdir = archdir
        self.module = module
        self.mirror = mirror
        self.subarchives = subarchives
        self.mingw_variant: str = mingw_variant
        self.is_autodesktop: bool = is_autodesktop
        self.list_options = list_options if list_options else {}
        self.tool_options: Dict[str, str] = tool_options if tool_options else {}
        # `steps.yml` assumes that qt_version is the highest version that satisfies spec
        self.spec = spec
        self.output_dir = output_dir
        self.check_output_cmd = check_output_cmd
        self.emsdk_version = emsdk_version
        self.autodesk_arch_folder = autodesk_arch_folder

    def qt_bindir(self, *, sep='/') -> str:
        out_dir = f"$(Build.BinariesDirectory){sep}Qt" if not self.output_dir else self.output_dir
        version_dir = self.qt_version
        return f"{out_dir}{sep}{version_dir}{sep}{self.archdir}{sep}bin"

    def win_qt_bindir(self) -> str:
        return self.qt_bindir(sep='\\')

    def autodesk_qt_bindir(self, *, sep='/') -> str:
        out_dir = f"$(Build.BinariesDirectory){sep}Qt" if not self.output_dir else self.output_dir
        version_dir = self.qt_version
        return f"{out_dir}{sep}{version_dir}{sep}{self.autodesk_arch_folder or self.archdir}{sep}bin"

    def win_autodesk_qt_bindir(self) -> str:
        return self.autodesk_qt_bindir(sep='\\')

    def mingw_folder(self) -> str:
        """
        Tool variant         -> folder name
        --------------------    -----------------
        win64_llvm_mingw1706 -> llvm-mingw1706_64
        win64_mingw1310      -> mingw1310_64
        win64_mingw900       -> mingw1120_64 (tool contains mingw 11.2.0 instead of 9.0.0)
        win64_mingw810       -> mingw810_64
        """
        if not self.mingw_variant:
            return ""
        match = re.match(r"^win(?P<bits>\d+)_(?P<llvm>llvm_)?(?P<mingw>mingw\d+)$", self.mingw_variant)
        if match.group('llvm'):
            return f"llvm-{match.group('mingw')}_{match.group('bits')}"
        if match.group('mingw') == "mingw900":  # tool contains mingw 11.2.0, not 9.0.0
            return f"mingw1120_{match.group('bits')}"
        return f"{match.group('mingw')}_{match.group('bits')}"

    def mingw_tool_name(self) -> str:
        if self.mingw_variant == "win64_mingw900":
            return "tools_mingw90"
        elif self.mingw_variant == "win64_mingw1310":
            return "tools_mingw1310"
        elif self.mingw_variant == "win64_llvm_mingw1706":
            return "tools_llvm_mingw1706"
        else:
            return "tools_mingw"

    def emsdk_version(self) -> str:
        return BuildJob.emsdk_version_for_qt(self.qt_version)

    @staticmethod
    def emsdk_version_for_qt(version_of_qt: str) -> str:
        qt_major_minor = ".".join(version_of_qt.split(".")[:2])

        if qt_major_minor in BuildJob.EMSDK_FOR_QT:
            return BuildJob.EMSDK_FOR_QT[qt_major_minor]

        # Find the latest version using string comparison
        latest_version = "0.0"
        for version in BuildJob.EMSDK_FOR_QT.keys():
            if version > latest_version:
                latest_version = version

        return BuildJob.EMSDK_FOR_QT[latest_version]


class PlatformBuildJobs:
    def __init__(self, platform, build_jobs):
        self.platform = platform
        self.build_jobs = build_jobs


python_versions = ["3.12"]

qt_versions = ["6.8.1"]

linux_build_jobs = []
linux_arm64_build_jobs = []
mac_build_jobs = []
windows_build_jobs = []

all_platform_build_jobs = [
    PlatformBuildJobs("linux", linux_build_jobs),
    PlatformBuildJobs("linux_arm64", linux_arm64_build_jobs),
    PlatformBuildJobs("mac", mac_build_jobs),
    PlatformBuildJobs("windows", windows_build_jobs),
]

# Linux Desktop
for qt_version in qt_versions:
    linux_build_jobs.append(
        BuildJob("install-qt", qt_version, "linux", "desktop", "gcc_64", "gcc_64")
    )
linux_arm64_build_jobs.append(BuildJob("install-qt", "6.7.0", "linux_arm64", "desktop", "linux_gcc_arm64", "gcc_arm64"))

# Mac Desktop
for qt_version in qt_versions:
    mac_build_jobs.append(
        BuildJob("install-qt", qt_version, "mac", "desktop", "clang_64", "macos")
    )
mac_build_jobs.append(BuildJob(
            "install-qt",
            "6.2.0",
            "mac",
            "desktop",
            "clang_64",
            "macos",
            module="qtcharts qtnetworkauth", ))

# Windows Desktop
for qt_version in qt_versions:
    windows_build_jobs.append(BuildJob("install-qt", qt_version, "windows", "desktop", "win64_msvc2022_64", "msvc2022_64"))
windows_build_jobs.extend(
    [
        BuildJob(
            "install-qt",
            "6.5.3",
            "windows",
            "desktop",
            "win64_msvc2019_arm64",
            "msvc2019_arm64",
            is_autodesktop=True,  # Should install win64_msvc2019_arm64 in parallel
        ),
        BuildJob(
            "install-qt",
            "6.7.3",
            "windows",
            "desktop",
            "win64_llvm_mingw",
            "llvm-mingw_64",
            mingw_variant="win64_llvm_mingw1706",
            is_autodesktop=False,
        ),
        BuildJob(
            # Archives stored as .zip
            "install-src", "6.4.3", "windows", "desktop", "gcc_64", "gcc_64", subarchives="qtlottie",
            # Fail the job if this path does not exist:
            check_output_cmd="ls -lh ./6.4.3/Src/qtlottie/",
        ),
    ]
)

# Extra modules test
linux_build_jobs.extend(
    [
       BuildJob(
            # Archives stored as .7z
            "install-src", "6.1.0", "linux", "desktop", "gcc_64", "gcc_64", subarchives="qtlottie",
            # Fail the job if this path does not exist:
            check_output_cmd="ls -lh ./6.1.0/Src/qtlottie/",
        ),
        BuildJob(
            # Archives stored as .tar.gz
            "install-src", "6.4.3", "linux", "desktop", "gcc_64", "gcc_64", subarchives="qtlottie",
            # Fail the job if this path does not exist:
            check_output_cmd="ls -lh ./6.4.3/Src/qtlottie/",
        ),
        # Should install the `qtlottie` module, even though the archive `qtlottieanimation` is not specified:
        BuildJob(
            "install-doc", "6.1.3", "linux", "desktop", "gcc_64", "gcc_64",
            subarchives="qtdoc", module="qtlottie",
            # Fail the job if these paths do not exist:
            check_output_cmd="ls -lh ./Docs/Qt-6.1.3/qtdoc/ ./Docs/Qt-6.1.3/qtlottieanimation/",
        ),
        # Should install the `qtcharts` module, even though the archive `qtcharts` is not specified:
        BuildJob(
            "install-example", "6.1.3", "linux", "desktop", "gcc_64", "gcc_64",
            subarchives="qtdoc", module="qtcharts",
            # Fail the job if these paths do not exist:
            check_output_cmd="ls -lh ./Examples/Qt-6.1.3/charts/ ./Examples/Qt-6.1.3/demos/ ./Examples/Qt-6.1.3/tutorials/",
        ),
        # test for list commands
        BuildJob('list-qt', '6.1.0', 'linux', 'desktop', 'gcc_64', '', spec=">6.0,<6.1.1", list_options={'HAS_WASM': "False"}),
        BuildJob('list-qt', '6.1.0', 'linux', 'android', 'android_armv7', '', spec=">6.0,<6.1.1", list_options={}),
    ]
)

# WASM
linux_build_jobs.append(
    BuildJob("install-qt", "6.4.0", "linux", "desktop", "wasm_32", "wasm_32",
             is_autodesktop=True, emsdk_version="sdk-3.1.14-64bit", autodesk_arch_folder="gcc_64")
)
for job_queue, host, desk_arch in (
    (linux_build_jobs, "linux", "gcc_64"),
    (mac_build_jobs, "mac", "clang_64"),
    (windows_build_jobs, "windows", "mingw_64"),
):
    for wasm_arch in ("wasm_singlethread", "wasm_multithread"):
        job_queue.append(
            BuildJob("install-qt", "6.5.0", host, "desktop", wasm_arch, wasm_arch,
                     is_autodesktop=True, emsdk_version="sdk-3.1.25-64bit", autodesk_arch_folder=desk_arch)
        )
mac_build_jobs.append(
    BuildJob("install-qt", "6.4.3", "mac", "desktop", "wasm_32", "wasm_32",
             is_autodesktop=True, emsdk_version="sdk-3.1.14-64bit", autodesk_arch_folder="clang_64")
)
windows_build_jobs.append(
    BuildJob("install-qt", "6.4.3", "windows", "desktop", "wasm_32", "wasm_32",
             is_autodesktop=True, emsdk_version="sdk-3.1.14-64bit", autodesk_arch_folder="mingw_64",
             mingw_variant="win64_mingw900")
)

# WASM post 6.7.x
linux_build_jobs.append(
    BuildJob("install-qt", "6.7.3", "all_os", "wasm", "wasm_multithread", "wasm_multithread",
             is_autodesktop=True, emsdk_version=f"sdk-{BuildJob.emsdk_version_for_qt("6.7.3")}-64bit", autodesk_arch_folder="gcc_64")
)
for job_queue, host, desk_arch, target, qt_version in (
    (linux_build_jobs, "all_os", "linux_gcc_64", "wasm", qt_versions[0]),
    (mac_build_jobs, "all_os", "clang_64", "wasm", qt_versions[0]),
    (windows_build_jobs, "all_os", "mingw_64", "wasm", qt_versions[0]),
):
    for wasm_arch in ("wasm_singlethread", "wasm_multithread"):
        job_queue.append(
            BuildJob("install-qt", qt_version, host, target, wasm_arch, wasm_arch,
                     is_autodesktop=True, emsdk_version=f"sdk-{BuildJob.emsdk_version_for_qt(qt_version)}-64bit", autodesk_arch_folder=desk_arch)
        )

# mobile SDK
mac_build_jobs.extend(
    [
        BuildJob("install-qt", "6.4.3", "mac", "ios", "ios", "ios", module="qtsensors", is_autodesktop=True),
        BuildJob("install-qt", "6.2.4", "mac", "ios", "ios", "ios", module="qtsensors", is_autodesktop=False),
        BuildJob("install-qt", "6.4.3", "mac", "android", "android_armv7", "android_armv7", is_autodesktop=True),
    ]
)
linux_build_jobs.extend(
    [
        BuildJob("install-qt", "6.1.3", "linux", "android", "android_armv7", "android_armv7", is_autodesktop=True),
        BuildJob("install-qt", "6.4.3", "linux", "android", "android_arm64_v8a", "android_arm64_v8a", is_autodesktop=True),
    ]
)

# Qt 6.3.0 for Windows-Android has win64_mingw available, but not win64_mingw81.
# This will test that the path to mingw is not hardcoded.
windows_build_jobs.extend(
    [
        BuildJob("install-qt", "6.3.2", "windows", "android", "android_armv7", "android_armv7", is_autodesktop=True),
        BuildJob("install-qt", "6.4.3", "windows", "android", "android_x86_64", "android_x86_64", is_autodesktop=True),
    ]
)

qt_creator_bin_path = "./Tools/QtCreator/bin/"
qt_creator_mac_bin_path = "./Qt Creator.app/Contents/MacOS/"
qt_ifw_bin_path = "./Tools/QtInstallerFramework/*/bin/"
tool_options = {
    "TOOL1_ARGS": "tools_qtcreator qt.tools.qtcreator",
    "LIST_TOOL1_CMD": f"ls {qt_creator_bin_path}",
    "TEST_TOOL1_CMD": f"{qt_creator_bin_path}qbs --version",
    "TOOL2_ARGS": "tools_ifw",
    "TEST_TOOL2_CMD": f"{qt_ifw_bin_path}archivegen --version",
    "LIST_TOOL2_CMD": f"ls {qt_ifw_bin_path}",
}
# Mac Qt Creator is a .app, or "Package Bundle", so the path is changed:
tool_options_mac = {
    **tool_options,
    "TEST_TOOL1_CMD": f'"{qt_creator_mac_bin_path}qbs" --version',
    "LIST_TOOL1_CMD": f'ls "{qt_creator_mac_bin_path}"',
}
windows_build_jobs.append(
    BuildJob("install-tool", "", "windows", "desktop", "", "", tool_options=tool_options)
)
linux_build_jobs.append(
    BuildJob("install-tool", "", "linux", "desktop", "", "", tool_options=tool_options)
)
mac_build_jobs.append(
    BuildJob("install-tool", "", "mac", "desktop", "", "", tool_options=tool_options_mac)
)

matrices = {}

for platform_build_job in all_platform_build_jobs:
    matrix_dictionary = collections.OrderedDict()

    for build_job, python_version in product(
        platform_build_job.build_jobs, python_versions
    ):
        key = "{} {} {} for {}".format(
            build_job.command, build_job.qt_version, build_job.arch, build_job.target
        )
        if build_job.spec:
            key = '{} (spec="{}")'.format(key, build_job.spec)
        if build_job.module:
            key = "{} ({})".format(key, build_job.module)
        if build_job.subarchives:
            key = "{} ({})".format(key, build_job.subarchives)
        if build_job.output_dir:
            key = "{} ({})".format(key, build_job.output_dir)
        matrix_dictionary[key] = collections.OrderedDict(
            [
                ("PYTHON_VERSION", python_version),
                ("SUBCOMMAND", build_job.command),
                ("QT_VERSION", build_job.qt_version),
                ("HOST", build_job.host),
                ("TARGET", build_job.target),
                ("ARCH", build_job.arch),
                ("ARCHDIR", build_job.archdir),
                ("MODULE", build_job.module if build_job.module else ""),
                ("QT_BASE_MIRROR", build_job.mirror if build_job.mirror else ""),
                ("SUBARCHIVES", build_job.subarchives if build_job.subarchives else ""),
                ("SPEC", build_job.spec if build_job.spec else ""),
                ("MINGW_VARIANT", build_job.mingw_variant),
                ("MINGW_TOOL_NAME", build_job.mingw_tool_name()),
                ("MINGW_FOLDER", build_job.mingw_folder()),
                ("IS_AUTODESKTOP", str(build_job.is_autodesktop)),
                ("HAS_WASM", build_job.list_options.get("HAS_WASM", "True")),
                ("OUTPUT_DIR", build_job.output_dir if build_job.output_dir else ""),
                ("QT_BINDIR", build_job.qt_bindir()),
                ("WIN_QT_BINDIR", build_job.win_qt_bindir()),
                ("EMSDK_VERSION", (build_job.emsdk_version+"@main").split('@')[0]),
                ("EMSDK_TAG",  (build_job.emsdk_version+"@main").split('@')[1]),
                ("WIN_AUTODESK_QT_BINDIR", build_job.win_autodesk_qt_bindir()),
                ("TOOL1_ARGS", build_job.tool_options.get("TOOL1_ARGS", "")),
                ("LIST_TOOL1_CMD", build_job.tool_options.get("LIST_TOOL1_CMD", "")),
                ("TEST_TOOL1_CMD", build_job.tool_options.get("TEST_TOOL1_CMD", "")),
                ("TOOL2_ARGS", build_job.tool_options.get("TOOL2_ARGS", "")),
                ("LIST_TOOL2_CMD", build_job.tool_options.get("LIST_TOOL2_CMD", "")),
                ("TEST_TOOL2_CMD", build_job.tool_options.get("TEST_TOOL2_CMD", "")),
                ("CHECK_OUTPUT_CMD", build_job.check_output_cmd or "")
            ]
        )

    matrices[platform_build_job.platform] = matrix_dictionary

print("Setting Variables below")
print(
    f"##vso[task.setVariable variable=linux;isOutput=true]{json.dumps(matrices['linux'])}"
)
print(
    f"##vso[task.setVariable variable=linux_arm64;isOutput=true]{json.dumps(matrices['linux_arm64'])}"
)
print(
    f"##vso[task.setVariable variable=windows;isOutput=true]{json.dumps(matrices['windows'])}"
)
print(
    f"##vso[task.setVariable variable=mac;isOutput=true]{json.dumps(matrices['mac'])}"
)

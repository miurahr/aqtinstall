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
        tool_options: Optional[Dict[str, str]] = None,
        check_output_cmd: Optional[str] = None,
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
        self.list_options = list_options if list_options else {}
        self.tool_options: Dict[str, str] = tool_options if tool_options else {}
        # `steps.yml` assumes that qt_version is the highest version that satisfies spec
        self.spec = spec
        self.output_dir = output_dir
        self.check_output_cmd = check_output_cmd

    def qt_bindir(self, *, sep='/') -> str:
        out_dir = f"$(Build.BinariesDirectory){sep}Qt" if not self.output_dir else self.output_dir
        version_dir = "5.9" if self.qt_version == "5.9.0" else self.qt_version
        return f"{out_dir}{sep}{version_dir}{sep}{self.archdir}{sep}bin"

    def win_qt_bindir(self) -> str:
        return self.qt_bindir(sep='\\')

    def mingw_folder(self) -> str:
        if not self.mingw_variant:
            return ""
        match = re.match(r"^win(\d+)_(mingw\d+)$", self.mingw_variant)
        return f"{match[2]}_{match[1]}"


class PlatformBuildJobs:
    def __init__(self, platform, build_jobs):
        self.platform = platform
        self.build_jobs = build_jobs


python_versions = [
    "3.8",
]

qt_versions = ["5.13.2", "5.15.2"]

linux_build_jobs = []
mac_build_jobs = []
windows_build_jobs = []

all_platform_build_jobs = [
    PlatformBuildJobs("linux", linux_build_jobs),
    PlatformBuildJobs("mac", mac_build_jobs),
    PlatformBuildJobs("windows", windows_build_jobs),
]

# Linux Desktop
for qt_version in qt_versions:
    linux_build_jobs.append(
        BuildJob("install-qt", qt_version, "linux", "desktop", "gcc_64", "gcc_64")
    )

# Mac Desktop
for qt_version in qt_versions:
    mac_build_jobs.append(
        BuildJob("install-qt", qt_version, "mac", "desktop", "clang_64", "clang_64")
    )

# Windows Desktop
windows_build_jobs.extend(
    [
        BuildJob(
            "install-qt",
            "5.15.2",
            "windows",
            "desktop",
            "win32_msvc2019",
            "msvc2019",
            mirror=random.choice(MIRRORS),
        ),
        BuildJob(
            "install-qt",
            "5.14.2",
            "windows",
            "desktop",
            "win32_mingw73",
            "mingw73_32",
            mingw_variant="win32_mingw730",
            mirror=random.choice(MIRRORS),
        ),
        BuildJob(
            "install-qt",
            "5.13.2",
            "windows",
            "desktop",
            "win64_msvc2015_64",
            "msvc2015_64",
            mirror=random.choice(MIRRORS),
        ),
        BuildJob(
            "install-qt",
            "5.15.2",
            "windows",
            "desktop",
            "win64_mingw81",
            "mingw81_64",
            mingw_variant="win64_mingw810",
            mirror=random.choice(MIRRORS),
        ),
        # Known issue with Azure-Pipelines environment: it has a pre-installed mingw81 which cause link error.
        # BuildJob('install', '5.15.0', 'windows', 'desktop', 'win32_mingw81', 'mingw81_32', mirror=MIRROR),
        BuildJob(
            "install-qt",
            "5.15.2",
            "windows",
            "desktop",
            "win64_msvc2019_64",
            "msvc2019_64",
            module="qtcharts qtnetworkauth",
            mirror=random.choice(MIRRORS),
        ),
        BuildJob(
            "install-qt",
            "5.9.0",
            "windows",
            "desktop",
            "win64_msvc2015_64",
            "msvc2015_64",
            module="qtcharts qtnetworkauth",
            mirror=random.choice(MIRRORS),
        ),
        BuildJob(
            "install-qt",
            "5.14.2",
            "windows",
            "desktop",
            "win64_mingw73",
            "mingw73_64",
            mingw_variant="win64_mingw730",
            spec=">1,<5.15",  # Don't redirect output! Must be wrapped in quotes!
            mirror=random.choice(MIRRORS),
        ),
    ]
)

# Extra modules test
linux_build_jobs.extend(
    [
        BuildJob(
            "install-qt",
            "5.15.2",
            "linux",
            "desktop",
            "gcc_64",
            "gcc_64",
            module="qtcharts qtnetworkauth",
        ),
        BuildJob(
            "install-qt", "5.14.2", "linux", "desktop", "gcc_64", "gcc_64", module="all"
        ),
        BuildJob(
            "install-qt",
            "5.15.2",
            "linux",
            "desktop",
            "gcc_64",
            "gcc_64",
            subarchives="qtbase qttools qt icu",
        ),
        BuildJob(
            "install-src", "6.1.0", "linux", "desktop", "gcc_64", "gcc_64", subarchives="qtlottie",
            # Fail the job if this path does not exist:
            check_output_cmd="ls -lh ./6.1.0/Src/qtlottie/",
        ),
        # Should install the `qtlottie` module, even though the archive `qtlottieanimation` is not specified:
        BuildJob(
            "install-doc", "6.1.0", "linux", "desktop", "gcc_64", "gcc_64",
            subarchives="qtdoc", module="qtlottie",
            # Fail the job if these paths do not exist:
            check_output_cmd="ls -lh ./Docs/Qt-6.1.0/qtdoc/ ./Docs/Qt-6.1.0/qtlottieanimation/",
        ),
        # Should install the `qtcharts` module, even though the archive `qtcharts` is not specified:
        BuildJob(
            "install-example", "6.1.0", "linux", "desktop", "gcc_64", "gcc_64",
            subarchives="qtdoc", module="qtcharts",
            # Fail the job if these paths do not exist:
            check_output_cmd="ls -lh ./Examples/Qt-6.1.0/charts/ ./Examples/Qt-6.1.0/demos/ ./Examples/Qt-6.1.0/tutorials/",
        ),
        # test for list commands
        BuildJob('list', '5.15.2', 'linux', 'desktop', 'gcc_64', '', spec="<6", list_options={
            'HAS_EXTENSIONS': "True",
        }),
        BuildJob('list', '6.1.0', 'linux', 'android', 'android_armv7', '', spec=">6.0,<6.1.1", list_options={
            'HAS_EXTENSIONS': "True",
            'USE_EXTENSION': "armv7",
        }),
        # tests run on linux but query data about other platforms
        BuildJob('list', '5.14.1', 'mac', 'ios', 'ios', '', spec="<=5.14.1", list_options={}),
        BuildJob('list', '5.13.1', 'windows', 'winrt', 'win64_msvc2015_winrt_x64', '', spec=">5.13.0,<5.13.2", list_options={}),
    ]
)
mac_build_jobs.extend(
    [
        BuildJob(
            "install-qt",
            "6.2.0",
            "mac",
            "desktop",
            "clang_64",
            "macos",
            module="qtcharts qtnetworkauth",
        ),
        BuildJob(
            "install-qt",
            "5.14.2",
            "mac",
            "desktop",
            "clang_64",
            "clang_64",
            module="qtcharts qtnetworkauth",
        ),
    ]
)

# WASM
linux_build_jobs.append(
    BuildJob("install-qt", "5.14.2", "linux", "desktop", "wasm_32", "wasm_32")
)
mac_build_jobs.append(
    BuildJob("install-qt", "5.14.2", "mac", "desktop", "wasm_32", "wasm_32")
)

# mobile SDK
mac_build_jobs.extend(
    [
        BuildJob("install-qt", "5.15.2", "mac", "ios", "ios", "ios"),
        BuildJob("install-qt", "6.2.2", "mac", "ios", "ios", "ios", module="qtsensors"),
        BuildJob(
            "install-qt", "6.1.0", "mac", "android", "android_armv7", "android_armv7"
        ),
    ]
)
linux_build_jobs.extend(
    [BuildJob("install-qt", "6.1.0", "linux", "android", "android_armv7", "android_armv7")]
)

# Test binary patch of qmake
linux_build_jobs.extend(
    [
        # New output dir is shorter than the default value; qmake could fail to
        # locate prefix dir if the value is patched wrong
        BuildJob(
            "install-qt",
            "5.12.11",
            "linux",
            "desktop",
            "gcc_64",
            "gcc_64",
            output_dir="/t/Q",
        ),
        # New output dir is longer than the default value.
        # This case is meant to work without any bugfix; if this fails, the test is setup wrong
        BuildJob(
            "install-qt",
            "5.12.11",
            "linux",
            "desktop",
            "gcc_64",
            "gcc_64",
            output_dir="/some/super/long/arbitrary/path/to" * 5,
        ),
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
                ("MINGW_FOLDER", build_job.mingw_folder()),
                ("HAS_EXTENSIONS", build_job.list_options.get("HAS_EXTENSIONS", "False")),
                ("USE_EXTENSION", build_job.list_options.get("USE_EXTENSION", "None")),
                ("OUTPUT_DIR", build_job.output_dir if build_job.output_dir else ""),
                ("QT_BINDIR", build_job.qt_bindir()),
                ("WIN_QT_BINDIR", build_job.win_qt_bindir()),
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
    f"##vso[task.setVariable variable=windows;isOutput=true]{json.dumps(matrices['windows'])}"
)
print(
    f"##vso[task.setVariable variable=mac;isOutput=true]{json.dumps(matrices['mac'])}"
)

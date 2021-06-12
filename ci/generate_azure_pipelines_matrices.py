"""
This sets variables for a matrix of QT versions to test downloading against with Azure Pipelines
"""
import collections
import json
import random
from itertools import product

MIRRORS = [
    "https://mirrors.ocf.berkeley.edu/qt",
    "https://ftp.jaist.ac.jp/pub/qtproject",
    "http://ftp1.nluug.nl/languages/qt",
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
        self.output_dir = output_dir


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
        BuildJob("install", qt_version, "linux", "desktop", "gcc_64", "gcc_64")
    )

# Mac Desktop
for qt_version in qt_versions:
    mac_build_jobs.append(
        BuildJob("install", qt_version, "mac", "desktop", "clang_64", "clang_64")
    )

# Windows Desktop
windows_build_jobs.extend(
    [
        BuildJob(
            "install",
            "5.14.2",
            "windows",
            "desktop",
            "win64_msvc2017_64",
            "msvc2017_64",
            mirror=random.choice(MIRRORS),
        ),
        BuildJob(
            "install",
            "5.14.2",
            "windows",
            "desktop",
            "win32_msvc2017",
            "msvc2017",
            mirror=random.choice(MIRRORS),
        ),
        BuildJob(
            "install",
            "5.13.2",
            "windows",
            "desktop",
            "win64_msvc2015_64",
            "msvc2015_64",
            mirror=random.choice(MIRRORS),
        ),
        BuildJob(
            "install",
            "5.15.2",
            "windows",
            "desktop",
            "win64_mingw81",
            "mingw81_64",
            mirror=random.choice(MIRRORS),
        ),
        # Known issue with Azure-Pipelines environment: it has a pre-installed mingw81 which cause link error.
        # BuildJob('install', '5.15.0', 'windows', 'desktop', 'win32_mingw81', 'mingw81_32', mirror=MIRROR),
        BuildJob(
            "install",
            "5.15.2",
            "windows",
            "desktop",
            "win64_msvc2019_64",
            "msvc2019_64",
            module="qcharts qtnetworkauth",
            mirror=random.choice(MIRRORS),
        ),
    ]
)

# Extra modules test
linux_build_jobs.extend(
    [
        BuildJob(
            "install",
            "5.15.2",
            "linux",
            "desktop",
            "gcc_64",
            "gcc_64",
            module="qcharts qtnetworkauth",
        ),
        BuildJob(
            "install", "5.14.2", "linux", "desktop", "gcc_64", "gcc_64", module="all"
        ),
        BuildJob(
            "install",
            "5.15.2",
            "linux",
            "desktop",
            "gcc_64",
            "gcc_64",
            subarchives="qtbase qttools qt icu",
        ),
        BuildJob(
            "src", "6.1.0", "linux", "desktop", "gcc_64", "gcc_64", subarchives="qt"
        ),
        BuildJob(
            "doc", "6.1.0", "linux", "desktop", "gcc_64", "gcc_64", subarchives="qtdoc"
        ),
        # test for list commands
        BuildJob("list", "6.1.0", "linux", "desktop", "", ""),
    ]
)
mac_build_jobs.append(
    BuildJob(
        "install",
        "5.14.2",
        "mac",
        "desktop",
        "clang_64",
        "clang_64",
        module="qcharts qtnetworkauth",
    )
)

# WASM
linux_build_jobs.append(
    BuildJob("install", "5.14.2", "linux", "desktop", "wasm_32", "wasm_32")
)
mac_build_jobs.append(
    BuildJob("install", "5.14.2", "mac", "desktop", "wasm_32", "wasm_32")
)

# mobile SDK
mac_build_jobs.extend(
    [
        BuildJob("install", "5.15.2", "mac", "ios", "ios", "ios"),
        BuildJob(
            "install", "6.1.0", "mac", "android", "android_armv7", "android_armv7"
        ),
    ]
)
linux_build_jobs.extend(
    [BuildJob("install", "6.1.0", "linux", "android", "android_armv7", "android_armv7")]
)

# Test binary patch of qmake
linux_build_jobs.extend(
    [
        # New output dir is shorter than the default value; qmake could fail to
        # locate prefix dir if the value is patched wrong
        BuildJob(
            "install",
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
            "install",
            "5.12.11",
            "linux",
            "desktop",
            "gcc_64",
            "gcc_64",
            output_dir="/some/super/long/arbitrary/path/to" * 5,
        ),
    ]
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
                ("OUTPUT_DIR", build_job.output_dir if build_job.output_dir else ""),
                (
                    "QT_BINDIR",
                    "{0}/{1.qt_version}/{1.archdir}/bin".format(
                        "$(Build.BinariesDirectory)/Qt"
                        if not build_job.output_dir
                        else build_job.output_dir,
                        build_job,
                    ),
                ),
                (
                    "WIN_QT_BINDIR",
                    "{0}\\{1.qt_version}\\{1.archdir}\\bin".format(
                        "$(Build.BinariesDirectory)\\Qt"
                        if not build_job.output_dir
                        else build_job.output_dir,
                        build_job,
                    ),
                ),
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

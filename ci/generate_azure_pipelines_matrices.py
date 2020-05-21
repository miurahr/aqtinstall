"""
This sets variables for a matrix of QT versions to test downloading against with Azure Pipelines
"""
import collections
import json
from itertools import product


class BuildJob:
    def __init__(self, qt_version, host, target, arch, archdir, module=None):
        self.qt_version = qt_version
        self.host = host
        self.target = target
        self.arch = arch
        self.archdir = archdir
        self.module = module


class PlatformBuildJobs:
    def __init__(self, platform, build_jobs):
        self.platform = platform
        self.build_jobs = build_jobs


python_versions = [
    '3.7',
]

qt_versions = [
    '5.13.2',
    '5.14.0'
]

linux_build_jobs = []
mac_build_jobs = []
windows_build_jobs = []

all_platform_build_jobs = [
    PlatformBuildJobs('linux', linux_build_jobs),
    PlatformBuildJobs('mac', mac_build_jobs),
    PlatformBuildJobs('windows', windows_build_jobs),
]

# Linux Desktop
for qt_version in qt_versions:
    linux_build_jobs.append(
        BuildJob(qt_version, 'linux', 'desktop', 'gcc_64', 'gcc_64')
    )

# Mac Desktop
for qt_version in qt_versions:
    mac_build_jobs.append(
        BuildJob(qt_version, 'mac', 'desktop', 'clang_64', "clang_64")
    )

# Mac iOS, android
mac_build_jobs.extend(
    [
        BuildJob('5.13.2', 'mac', 'ios', 'ios', 'ios'),
        BuildJob('5.14.1', 'mac', 'android', 'android', 'android')
    ]
)

# Windows Desktop
windows_build_jobs.extend(
    [
        BuildJob('5.14.2', 'windows', 'desktop', 'win64_msvc2017_64', 'msvc2017_64'),
        BuildJob('5.14.2', 'windows', 'desktop', 'win32_msvc2017', 'msvc2017'),
        BuildJob('5.13.2', 'windows', 'desktop', 'win64_msvc2015_64', 'msvc2015_64'),
        BuildJob('5.15.0', 'windows', 'desktop', 'win64_mingw81', 'mingw81_64'),
        # Known issue with Azure-Pipelines environment: it has a pre-installed mingw81 which cause link error.
        # BuildJob('5.15.0', 'windows', 'desktop', 'win32_mingw81', 'mingw81_32'),
        BuildJob('5.15.0', 'windows', 'desktop', 'win64_msvc2019_64', 'msvc2019_64', module='qcharts qtnetworkauth'),
    ]
)

# Extra modules test
linux_build_jobs.extend(
    [
        BuildJob('5.15.0', 'linux', 'desktop', 'gcc_64', 'gcc_64', module='qcharts qtnetworkauth'),
        BuildJob('5.14.2', 'linux', 'desktop', 'gcc_64', 'gcc_64', module='all')
    ]
)
mac_build_jobs.append(
    BuildJob('5.14.2', 'mac', 'desktop', 'clang_64', 'clang_64', module='qcharts qtnetworkauth')
)

# WASM
linux_build_jobs.append(
    BuildJob('5.14.0', 'linux', 'desktop', 'wasm_32', "wasm_32")
)
mac_build_jobs.append(
    BuildJob('5.14.0', 'mac', 'desktop', 'wasm_32', "wasm_32")
)
windows_build_jobs.append(
    BuildJob('5.14.2', 'windows', 'desktop', 'wasm_32', "wasm_32")
)

# android
linux_build_jobs.append(
    BuildJob('5.14.1', 'linux', 'android', 'android', 'android')
)

matrices = {}

for platform_build_job in all_platform_build_jobs:
    matrix_dictionary = collections.OrderedDict()

    for build_job, python_version in product(platform_build_job.build_jobs, python_versions):
        key = '{} {} for {} on {}'.format(build_job.qt_version, build_job.arch, build_job.target, build_job.host)
        if build_job.module:
            key = "{} ({})".format(key, build_job.module)
        matrix_dictionary[key] = collections.OrderedDict(
            [
                ('PYTHON_VERSION', python_version),
                ('QT_VERSION', build_job.qt_version),
                ('HOST', build_job.host),
                ('TARGET', build_job.target),
                ('ARCH', build_job.arch),
                ('ARCHDIR', build_job.archdir),
                ('MODULE', build_job.module if build_job.module else '')
            ]
        )

    matrices[platform_build_job.platform] = matrix_dictionary

print("Setting Variables below")
print(f"##vso[task.setVariable variable=linux;isOutput=true]{json.dumps(matrices['linux'])}")
print(f"##vso[task.setVariable variable=windows;isOutput=true]{json.dumps(matrices['windows'])}")
print(f"##vso[task.setVariable variable=mac;isOutput=true]{json.dumps(matrices['mac'])}")

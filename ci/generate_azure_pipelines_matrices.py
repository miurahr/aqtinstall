"""
This sets variables for a matrix of QT versions to test downloading against with Azure Pipelines
"""
import collections
import json
from itertools import product


class BuildJob:
    def __init__(self, qt_version, host, target, arch, archdir):
        self.qt_version = qt_version
        self.host = host
        self.target = target
        self.arch = arch
        self.archdir = archdir


class PlatformBuildJobs:
    def __init__(self, platform, build_jobs):
        self.platform = platform
        self.build_jobs = build_jobs


python_versions = [
    '3.7',
]

qt_versions = [
    '5.12.5',
    '5.13.1',
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

# Mac iOS
mac_build_jobs.append(
    BuildJob('5.13.0', 'mac', 'ios', 'ios', 'ios')
)

# Windows Desktop
windows_build_jobs.extend(
    [
        BuildJob('5.12.5', 'windows', 'desktop', 'win64_msvc2017_64', 'msvc2017_64'),
        BuildJob('5.12.5', 'windows', 'desktop', 'win32_msvc2017', 'msvc2017'),
    ]
)

windows_build_jobs.extend(
    [
        BuildJob('5.13.1', 'windows', 'desktop', 'win64_msvc2017_64', 'msvc2017_64'),
        BuildJob('5.13.1', 'windows', 'desktop', 'win64_msvc2015_64', 'msvc2015_64'),
        BuildJob('5.13.1', 'windows', 'desktop', 'win64_mingw73', 'mingw73_64'),
        BuildJob('5.13.1', 'windows', 'desktop', 'win32_msvc2017', 'msvc2017'),
        BuildJob('5.13.1', 'windows', 'desktop', 'win32_mingw73', 'mingw73_32'),
    ]
)

windows_build_jobs.extend(
    [
        BuildJob('5.14.0', 'windows', 'desktop', 'win64_msvc2015_64', 'msvc2015_64'),
        BuildJob('5.14.0', 'windows', 'desktop', 'win32_msvc2017', 'msvc2017'),
    ]
)

# Androids for Linux platforms
# aqt is for CI/CD systems!
# Users might develop on Win/Mac, but are most likely to use Linux for CI/CD with
# the Android ecosystem.

for android_arch in ['android_x86', 'android_armv7']:
    linux_build_jobs.append(
        BuildJob('5.13.1', 'linux', 'android', android_arch, android_arch)
    )

matrices = {}

for platform_build_job in all_platform_build_jobs:
    matrix_dictionary = collections.OrderedDict()

    for build_job, python_version in product(platform_build_job.build_jobs, python_versions):
        key = 'QT {} {} {} {}'.format(build_job.qt_version, build_job.host, build_job.target,
                                      build_job.arch)
        matrix_dictionary[key] = collections.OrderedDict(
            [
                ('PYTHON_VERSION', python_version),
                ('QT_VERSION', build_job.qt_version),
                ('HOST', build_job.host),
                ('TARGET', build_job.target),
                ('ARCH', build_job.arch),
                ('ARCHDIR', build_job.archdir),
            ]
        )

    matrices[platform_build_job.platform] = matrix_dictionary

print("Setting Variables below")
print(f"##vso[task.setVariable variable=linux;isOutput=true]{json.dumps(matrices['linux'])}")
print(f"##vso[task.setVariable variable=windows;isOutput=true]{json.dumps(matrices['windows'])}")
print(f"##vso[task.setVariable variable=mac;isOutput=true]{json.dumps(matrices['mac'])}")

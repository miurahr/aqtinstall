"""
This generates a matrix of QT versions to test downloading against
"""

from itertools import product
import os
from ruamel.yaml import YAML


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
    '5.11.3',
    '5.12.3',
    '5.13.0'
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
        BuildJob('5.11.3', 'windows', 'desktop', 'win64_msvc2017_64', 'msvc2017_64'),
        BuildJob('5.11.3', 'windows', 'desktop', 'win32_msvc2015', 'msvc2015'),
    ]
)

windows_build_jobs.extend(
    [
        BuildJob('5.12.3', 'windows', 'desktop', 'win64_msvc2017_64', 'msvc2017_64'),
        BuildJob('5.12.3', 'windows', 'desktop', 'win32_msvc2017', 'msvc2017'),
    ]
)

windows_build_jobs.extend(
    [
        BuildJob('5.13.0', 'windows', 'desktop', 'win64_msvc2017_64', 'msvc2017_64'),
        BuildJob('5.13.0', 'windows', 'desktop', 'win64_msvc2015_64', 'msvc2015_64'),
        BuildJob('5.13.0', 'windows', 'desktop', 'win64_mingw73', 'mingw73'),
        BuildJob('5.13.0', 'windows', 'desktop', 'win32_msvc2017', 'msvc2017'),
        BuildJob('5.13.0', 'windows', 'desktop', 'win32_mingw73', 'mingw73'),
    ]
)

# All Androids for all platforms

for android_arch in [ 'android_x86', 'android_armv7', ]:
    for platform_build_jobs in all_platform_build_jobs:
        platform_build_jobs.build_jobs.append(
            BuildJob('5.13.0', platform_build_jobs.platform, 'android', android_arch, android_arch)
        )

matrices = {}

for platform_build_job in all_platform_build_jobs:
    yaml_dictionary = {
        'matrix': {}
    }
    for build_job, python_version in product(platform_build_job.build_jobs, python_versions):
        key = 'Python {} QT {} {} {} {}'.format(python_version, build_job.qt_version, build_job.host, build_job.target,
                                                build_job.arch)
        yaml_dictionary['matrix'][key] = \
            {
                'PYTHON_VERSION': python_version,
                'QT_VERSION': build_job.qt_version,
                'HOST': build_job.host,
                'TARGET': build_job.target,
                'ARCH': build_job.arch,
                'ARCHDIR': build_job.archdir,
            }
    matrices[platform_build_job.platform.capitalize()] = yaml_dictionary

root_dir = os.path.abspath(os.path.dirname(__file__))

# Load azure-pipelines.tmpl.yml
with open(os.path.join(root_dir, 'ci', 'azure-pipelines.tmpl.yml'), 'r') as f:
    azure_pipelines_yaml = YAML().load(f.read())

# Attach strategies to their respective jobs
for job_yaml in azure_pipelines_yaml['jobs']:
    if job_yaml['job'] in matrices:
        job_yaml['strategy'] = matrices[job_yaml['job']]

with open(os.path.join(root_dir, 'azure-pipelines.yml'), 'w') as f:
    YAML().dump(azure_pipelines_yaml, f)

pass

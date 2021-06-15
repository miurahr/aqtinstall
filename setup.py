#!/usr/bin/env python

from setuptools import setup

setup(
    use_scm_version={
        "write_to": "aqt/version.py",
        "write_to_template": '__version__ = "{version}"\n',
        "tag_regex": r"^(?P<prefix>v)?(?P<version>[^\+]+)(?P<suffix>.*)?$",
        "local_scheme": "no-local-version",
    }
)

#!/usr/bin/env python

import io
import os

from setuptools import setup


def readme():
    with io.open(os.path.join(os.path.dirname(__file__), 'README.rst'), mode="r", encoding="UTF-8") as readmef:
        return readmef.read()


setup(name='aqtinstall',
      version='0.3.0',
      description='Another unofficial Qt installer',
      url='http://github.com/miurahr/aqtinstall',
      license='MIT',
      long_description=readme(),
      author='Hioshi Miura',
      author_email='miurahr@linux.com',
      packages=["aqt"],
      scripts=["aqtinst"]
      )

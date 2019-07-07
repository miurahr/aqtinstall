#!/usr/bin/env python

import io
import os

from setuptools import setup


def readme():
    with io.open(os.path.join(os.path.dirname(__file__), 'README.rst'), mode="r", encoding="UTF-8") as readmef:
        return readmef.read()


setup(name='aqtinstall',
      version='0.4.1',
      description='Another unofficial Qt installer',
      url='http://github.com/miurahr/aqtinstall',
      license='MIT',
      long_description=readme(),
      author='Hioshi Miura',
      author_email='miurahr@linux.com',
      packages=["aqt"],
      install_requires=['requests', 'six', 'py7zr'],
      extras_require={
        'dev': [
            'pytest',
            'pytest-pep8',
            'pytest-cov',
            'flake8'
        ]
      },
      scripts=["bin/aqt"],
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Environment :: X11 Applications :: Qt',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Programming Language :: C++',
          'Topic :: Software Development',
          'Topic :: Software Development :: Libraries',
          ],
      )

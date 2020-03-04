====================
aqtinstall changeLog
====================

All notable changes to this project will be documented in this file.

***************
Current changes
***************

`Unreleased`_
=============

Added
-----

Changed
-------

Fixed
-----

Deprecated
----------

Removed
-------

Security
--------

`v0.7.8`_ (5, Mar., 2020)
=========================

* Same as v0.7.6


`v0.7.6`_ (4, Mar., 2020)
=========================

Fixed
-----

* Work around for http://download.qt.io returns wrong meta4 data.


`v0.7.5`_ (27, Feb., 2020)
==========================

Changed
-------

* Requirements of py7zr is v0.5.3 or later, which include no more os.chdir() patch.


`v0.7.4`_ (21, Feb., 2020)
==========================

Changed
-------

* Limit requirement of py7zr version to 0.5.*. Try to fix issue #86.


`v0.7.3`_ (14, Feb., 2020)
==========================

Added
-----

* Github Actions workflows for publishing.

Changed
-------

* Remove run script from source.
  Now it is automatically generated when build.(#85)
* Update requirement py7zr >=0.5

Fixed
-----

* README: fix reStructured text syntax.


`v0.7.2`_ (11, Feb., 2020)
==========================


Changed
-------

* Replace 'multiprocessing.dummy' with 'concurrent.futures'.
    - download with multi-threading(I/O bound)
    - extract with multi-processing(CPU bound)

Fixed
-----

* '-E | --external' option handling which cause path is not str error.



`v0.7.1`_ (13, Jan., 2020)
==========================

Fixed
-----

* Fix installation of extra modules for Qt5.9.


`v0.7`_ (13, Jan., 2020)
==========================

Changed
-------

* Move project metadata to setup.cfg from setup.py.


`v0.7b1`_ (10, Jan., 2020)
==========================

Changed
-------

* Bamp up dependency py7zr >=v0.5b5.
* Use py7zr in default to extract packages.
* Drop --internal command line option.


`v0.7a2`_ (7, Jan., 2020)
==========================

Added
-----

* Add special module name 'all' for extra module option.

Fixed
-----

* CI conditions, update target version.

`v0.7a1`_ (29, Nov., 2019)
==========================

Added
-----

* Introduce helper module.
* Introduce 'settings.ini' file which has a configuration for
  aqt module.

Changed
-------

* Version numbering with setuptools_scm.
* Now don't install extra modules when installing 'wasm_32' arch.
  You should explicitly specify it with '-m' option.

Fixed
-----

* Error when mirror site is not http, but https and ftp.

`v0.6b1`_ (23, Nov., 2019)
==========================

Changed
-------

* Just warn when argument combination check is failed.
* CI: Compress sample project for build test with 7zip.
* CI: Place sample script in ci directory.


`v0.6a2`_ (19, Nov., 2019)
==========================

Added
-----

* Test: Unit test against command line.
* Android target variants.

Changed
-------

* Use logging configuration with logging.ini

Fixed
-----

* qconfig.pri: fix QT_LICHECK line.

Removed
-------

* Logging configuration file logging.yml
* Drop dependency for pyyaml.

`v0.6a1`_ (17, Nov., 2019)
==========================

Added
-----

* More build test with sample project which uses an extra module.(#56)
* Add support for installation of WebAssembly component by specifying
  'wasm_32' as an arch argument.(#53, #55)

Changed
-------

* Optional modules are installed explicitly. Users need to specify extra modules with -m option.(#52, #56)

Fixed
-----

* Dependency for py7zr only for python > 3.5. Now it works with python2.7.

`v0.5`_ (10, Nov., 2019)
========================

Changed
-------

* Introduce combination DB in json form. User and developer now easily add new
  component for installation checking.

Fixed
-----

* requires `py7zr`_ >= 0.4.1 because v0.4 can fails to extract file.


`v0.5b2`_ (8, Oct., 2019)
=========================

Changed
-------

* Change install path from <target>/Qt/Qt<version>/<version> to <target>/<version> (#48).
  - Also update CI test to specify --outputdir <target> that is $(BinariesDirectory)/Qt

`v0.5b1`_ (8, Oct., 2019)
=========================

Added
-----

* Add feature to support installation of Qt Tools
* Add CI test for tool installation

Changed
-------

* CI test target
  - add 5.14.0
  - remove 5.11.3
  - change patch_levels to up-to-date


`v0.4.3`_ (25, Sep, 2019)
=========================

Fixed
-----

* Allow multiple redirection to mirror site.(#41)


`v0.4.2`_ (28, Jul, 2019)
=========================

Changed
-------

* README: update badge layout.
* CI: Improve azure-pipelines configurations by Nelson (#20)
* Check parameter combination allowance and add winrt variant.
* Support installation of mingw runtime package.
* Add '--internal' option to use `py7zr`_ instead of
  external `7zip`_ command for extracting package archives.(WIP)


`v0.4.1`_ (01, Jun, 2019)
=========================

Added
-----

* Option -b | --base to specify mirror site.(#24)

Changed
-------

* CI: add script to generate auzre-pipelines.yml (#27, #28, #29)
* CI: use powershell script for linux, mac and windows. (#26)

Fixed
-----

* Avoid blacklisted mirror site that cause CI fails.(#25)


`v0.4.0`_ (29, May, 2019)
=========================

Added
-----

* cli: output directory option.
* sphinx document.
* test packaging on CI.
* Handler for metalink information and intelligent mirror selection.

Changed
-------

* Change project directory structure.
* cli command name changed from 'aqtinst' to 'aqt' and now you can run 'aqt install'
* Introduce Cli class
* Massive regression test on azure pipelines(#20)
* blacklist against http://mirrors.tuna.tsinghua.edu.cn and http://mirrors.geekpie.club/
  from mirror site.
* Run 7zip command with '-o{directory}' option.

Fixed
-----

* Fix File Not Found Error when making qt.conf against win64_mingw73 and win32_mingw73


`v0.3.1`_ (15, March, 2019)
===========================

Added
-----

* Qmake build test code in CI environment.(#14)

Fixed
-----

* Connect to Qt download server through proxy with authentication.(#17)

Changed
-------

* Change QtInstaller.install() function signature not to take any parameter.
* Replace standard urllib to requests library.(#18)
* Use 7zr external command instead of 7z in Linux and mac OSX envitonment.

Removed
-------

* requirements.txt file.


`v0.3.0`_ (8, March, 2019)
==========================

Added
-----

* Allow execute both 'aqtinst'  and 'python -m aqt' form.

Changed
-------

* Project URL is changed.
* Generate universal wheel support both python2.7 and python 3.x.

Fixed
-----

* Update README wordings.
* Remove dependency for python3 with 'aqtinst' command utility.
* Fix command name in help message.



`v0.2.0`_ (7, March, 2019)
==========================

Added
-----

* Released on pypi.org

Changed
-------

* Install not only basic packages also optional packages.
* Rename project/command to aqt - Another QT installer

Fixed
-----

* Update mkspecs/qconfig.pri to indicate QT_EDITION is OpenSource
* Support Python2

`v0.1.0`_ (5, March, 2019)
==========================

Changed
-------

* Support  multiprocess concurrent download and installation.

`v0.0.2`_ (4, March, 2019)
==========================

Added
=====

* CI test on Azure-pipelines

Changed
=======

* Refactoring code
* Install QtSDK into (cwd)/Qt<version>/<version>/gcc_64/
* Drop dependency for `requests`_ library
* Use standard `argparse`_ for command line argument.

Fixed
=====

* Support windows.
* looking for 7zip in standard directory.

`v0.0.1`_ (2, March, 2019)
==========================

* Fork from https://git.kaidan.im/lnj/qli-installer


.. _py7zr: https://github.com/miurahr/py7zr
.. _7zip: https://www.7-zip.org/
.. _requests: https://pypi.org/project/requests
.. _argparse: https://pypi.org/project/argparse/

.. _Unreleased: https://github.com/miurahr/aqtinstall/compare/v0.7.8...HEAD
.. _v0.7.8: https://github.com/miurahr/aqtinstall/compare/v0.7.6...v0.7.8
.. _v0.7.6: https://github.com/miurahr/aqtinstall/compare/v0.7.5...v0.7.6
.. _v0.7.5: https://github.com/miurahr/aqtinstall/compare/v0.7.4...v0.7.5
.. _v0.7.4: https://github.com/miurahr/aqtinstall/compare/v0.7.3...v0.7.4
.. _v0.7.3: https://github.com/miurahr/aqtinstall/compare/v0.7.2...v0.7.3
.. _v0.7.2: https://github.com/miurahr/aqtinstall/compare/v0.7.1...v0.7.2
.. _v0.7.1: https://github.com/miurahr/aqtinstall/compare/v0.7...v0.7.1
.. _v0.7: https://github.com/miurahr/aqtinstall/compare/v0.7b1...v0.7
.. _v0.7b1: https://github.com/miurahr/aqtinstall/compare/v0.7a2...v0.7b1
.. _v0.7a2: https://github.com/miurahr/aqtinstall/compare/v0.7a1...v0.7a2
.. _v0.7a1: https://github.com/miurahr/aqtinstall/compare/v0.6b1...v0.7a1
.. _v0.6b1: https://github.com/miurahr/aqtinstall/compare/v0.6a2...v0.6b1
.. _v0.6a2: https://github.com/miurahr/aqtinstall/compare/v0.6a1...v0.6a2
.. _v0.6a1: https://github.com/miurahr/aqtinstall/compare/v0.5...v0.6a1
.. _v0.5: https://github.com/miurahr/aqtinstall/compare/v0.5b2...v0.5
.. _v0.5b2: https://github.com/miurahr/aqtinstall/compare/v0.5b1...v0.5b2
.. _v0.5b1: https://github.com/miurahr/aqtinstall/compare/v0.4.3...v0.5b1
.. _v0.4.3: https://github.com/miurahr/aqtinstall/compare/v0.4.2...v0.4.3
.. _v0.4.2: https://github.com/miurahr/aqtinstall/compare/v0.4.1...v0.4.2
.. _v0.4.1: https://github.com/miurahr/aqtinstall/compare/v0.4.0...v0.4.1
.. _v0.4.0: https://github.com/miurahr/aqtinstall/compare/v0.3.1...v0.4.0
.. _v0.3.1: https://github.com/miurahr/aqtinstall/compare/v0.3.0...v0.3.1
.. _v0.3.0: https://github.com/miurahr/aqtinstall/compare/v0.2.0...v0.3.0
.. _v0.2.0: https://github.com/miurahr/aqtinstall/compare/v0.1.0...v0.2.0
.. _v0.1.0: https://github.com/miurahr/aqtinstall/compare/v0.0.2...v0.1.0
.. _v0.0.2: https://github.com/miurahr/aqtinstall/compare/v0.0.1...v0.0.2
.. _v0.0.1: https://github.com/miurahr/aqtinstall/releases/tag/v0.0.1

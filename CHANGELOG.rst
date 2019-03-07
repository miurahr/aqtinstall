=======================
qli-installer changeLog
=======================

All notable changes to this project will be documented in this file.

***************
Current changes
***************

`Unreleased`_
=============

Added
-----

* Allow execute though command line `python -m aqt 5.12.1 linux desktop`

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
========================

Added
=====

* CI test on Azure-pipelines

Changed
=======

* Refactoring code
* Install QtSDK into (cwd)/Qt<version>/<version>/gcc_64/
* Drop dependency for `requests` library
* Use standard `argparser` for command line argument.

Fixed
=====

* Support windows.
* looking for 7zip in standard directory.

`v0.0.1`_ (2, March, 2019)
==========================

* Fork from https://git.kaidan.im/lnj/qli-installer

.. _Unreleased: https://github.com/miurahr/qli-installer/compare/v0.2.0...HEAD
.. _v0.2.0: https://github.com/miurahr/qli-installer/compare/v0.1.0...v0.2.0
.. _v0.1.0: https://github.com/miurahr/qli-installer/compare/v0.0.2...v0.1.0
.. _v0.0.2: https://github.com/miurahr/qli-installer/compare/v0.0.1...v0.0.2
.. _v0.0.1: https://github.com/miurahr/qli-installer/releases/tag/v0.0.1

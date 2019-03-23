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

* sphnix document.

Changed
-------

* Project directory structure.
* cli command name changed ot `aqt` and now you can run `aqt install`

Fixed
-----

Deprecated
----------

Removed
-------

Security
--------

`v0.3.1`_ (15, March, 2019)
==========================

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

* Allow execute both `aqtinst`  and `python -m aqt` form.

Changed
-------

* Project URL is changed.
* Generate universal wheel support both python2.7 and python 3.x.

Fixed
-----

* Update README wordings.
* Remove dependency for python3 with `aqtinst` command utility.
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

.. _Unreleased: https://github.com/miurahr/qli-installer/compare/v0.3.1...HEAD
.. _v0.3.1: https://github.com/miurahr/qli-installer/compare/v0.3.0...v0.3.1
.. _v0.3.0: https://github.com/miurahr/qli-installer/compare/v0.2.0...v0.3.0
.. _v0.2.0: https://github.com/miurahr/qli-installer/compare/v0.1.0...v0.2.0
.. _v0.1.0: https://github.com/miurahr/qli-installer/compare/v0.0.2...v0.1.0
.. _v0.0.2: https://github.com/miurahr/qli-installer/compare/v0.0.1...v0.0.2
.. _v0.0.1: https://github.com/miurahr/qli-installer/releases/tag/v0.0.1

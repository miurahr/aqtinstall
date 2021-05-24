====================
aqtinstall changeLog
====================

All notable changes to this project will be documented in this file.

`Unreleased`_
=============

Added
-----
* Support for installation of old versions(#236, #239)
* Add -c/--config option to specify custom settings.ini(#246)
* Document for settings.ini configuration parameters(#246)

Changed
-------
* Check MD5 checksum when download(#238)
* Config settings.ini parser and URL list format(#246)
* Refactoring network connection code, consolidated to helper.py(#244)
* Refactoring exceptions, introduce exceptions.py(#244)
* Update known Qt versions combinations.(#243)

Fixed
-----
* Prettify help message format(#237)
* CI: fix check workflow(#248)
* CI: fix error on Azure/Windows(connection error)(#246)

Deprecated
----------

Removed
-------

Security
--------

`v1.1.6`_ (2, May. 2021)
========================

Fixed
-----
* doc subcommand failed in argument parse(#234)


`v1.1.5`_ (8, Apr. 2021)
=========================

Added
-----
* README: describe advanced installation method.

Changed
-------
* Change tox.ini: docs test output folder
* Remove changelog from pypi page

Fixed
-----
* Drop dependency for wheel


`v1.1.4`_ (2, Apr. 2021)
=========================

Changed
-------
* Code reformatting by black and check by black.
* Check linting by github actions.

Fixed
-----
* Fix document error on README(#228, #226).


`v1.1.3`_ (26, Feb. 2021)
=========================

Fixed
-----

* Key error on 3.6.13, 3.7.10, 3.8.8, and 3.9.2(#221)

`v1.1.2`_ (20, Feb. 2021)
=========================

Fixed
-----

* Fix leaked multiprocessing resource(#220)
* Catch both read timeout and connection timeout.


`v1.1.1`_ (13, Feb. 2021)
=========================

Fixed
-----

* Catch timeout error and fallback to mirror (#215,#217)


`v1.1.0`_ (12, Feb. 2021)
=========================

Added
-----

* Patching android installation for Qt6
  - patch target_qt.conf

Changed
-------

* CI test with Qt6
* Docs: update avaiable conbinations

Fixed
-----

* Skip QtCore patching for 5.14.0 and later(Fix regression)(#211)



`v1.0.0`_ (4, Feb. 2021)
========================

Added
-----

* Add --noarchives option to allow user to add modules to existed installation(#174,#204)
* No patching when it does not install qtbase package by --noarchives and --archives option.(#204)
* Azure: test with jom build on windows.
* Patch pkgconfig configurations(#199)
* Patch libQt5Core and libQt6Core for linux(#201)

Changed
-------

* Update document to show available Qt versions
* Update README to add more references.
* Suppress debug log and exist silently when specified package not found.


Fixed
-----

* Catch exception on qmake -query execution(#201)
* Fix Qt6/Android installation handling.(#193, #200)



.. _Unreleased: https://github.com/miurahr/aqtinstall/compare/v1.1.6...HEAD
.. _v1.1.6: https://github.com/miurahr/aqtinstall/compare/v1.1.5...v1.1.6
.. _v1.1.5: https://github.com/miurahr/aqtinstall/compare/v1.1.4...v1.1.5
.. _v1.1.4: https://github.com/miurahr/aqtinstall/compare/v1.1.3...v1.1.4
.. _v1.1.3: https://github.com/miurahr/aqtinstall/compare/v1.1.2...v1.1.3
.. _v1.1.2: https://github.com/miurahr/aqtinstall/compare/v1.1.1...v1.1.2
.. _v1.1.1: https://github.com/miurahr/aqtinstall/compare/v1.1.0...v1.1.1
.. _v1.1.0: https://github.com/miurahr/aqtinstall/compare/v1.0.0...v1.1.0
.. _v1.0.0: https://github.com/miurahr/aqtinstall/compare/v0.11.1...v1.0.0

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


`v0.11.0`_ (11, Dec. 2020)
==========================

Added
-----

* Automatically fallback to mirror site when main https://download.qt.io down.(#194, #196)


`v0.10.1`_ (11, Dec. 2020)
==========================

Added
-----

* Add LTS vresions as known version.(#188)

Changed
-------

* Tool: Version comparison by startswith.
  When specified 4.0 but download server hold 4.0.1, it catch 4.0.1.(related #187)
* README: explicitly show python version requirements.



`v0.10.0`_ (25, Nov. 2020)
==========================

Added
-----

* Add v5.12.2, v6.0.0 as known versions.(#176, #177)
* Support --archives option on src installation.

Changed
-------

* Use multiprocessing.Pool instead of concurrent.futures(#178)
* Refactoring whole modules. (#179)
* Split old changelogs to CHNAGELOG_prerelease.rst
* Drop an upper limitaion (<0.11) for py7zr.(#183)

Fixed
-----

* When we used "-m all" to download doc or examples, Qt sources are also downloaded(@Gamso)(#182)


v0.9.8 (4, Nov. 2020)
=====================

Added
-----

* Added new combinations for tools_ifw

Fixed
-----

* When we start an installation, all packages are downloaded whatever the specified platform.(#159)



.. _Unreleased: https://github.com/miurahr/aqtinstall/compare/v0.11.0...HEAD
.. _v0.11.0: https://github.com/miurahr/aqtinstall/compare/v0.10.1...v0.11.0
.. _v0.10.1: https://github.com/miurahr/aqtinstall/compare/v0.10.0...v0.10.1
.. _v0.10.0: https://github.com/miurahr/aqtinstall/compare/v0.9.8...v0.10.0

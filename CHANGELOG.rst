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


Deprecated
----------

Removed
-------

Security
--------


v0.9.8 (4, Nov. 2020)
=====================

Added
-----

* Added new combinations for tools_ifw

Fixed
-----

* When we start an installation, all packages are downloaded whatever the specified platform.(#159)



.. _Unreleased: https://github.com/miurahr/aqtinstall/compare/v0.9.8...HEAD

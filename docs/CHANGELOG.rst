:tocdepth: 1

.. default-role:: any

.. _changes:

==========
ChangeLog
==========

All notable changes to this project will be documented in this file.

`Unreleased`_
=============

`v3.1.1`_ (10, Feb. 2023)
=========================

Fixed
-----
* CI: Pin EMSDK version (#641)
* Test: update tox.ini config (#634)
* Fix errors in install-* caused by duplicate modules (#633)


`v3.1.0`_ (5, Dec. 2022)
========================

Fixed
-----
* Support Qt 6.4.1 Android installation (#621,#626,#627)
* Fix URL of Nelson's blog on README

Changed
-------
* Update pyproject.toml and drop setup.cfg
* Standalone binary build with PyInstaller directly(#598)
* Bump dependencies versions
   - py7zr>=0.20.2
   - flake8<6
   - flake8-isort>=4.2.0
* metadata: change link to changelog
* docs: move CHANGELOG.rst into docs/
* Refactoring internals and now check types with mypy

Deprecated
----------
* Drop support for python 3.6


`v3.0.2`_ (26, Oct. 2022)
=========================

* Fix installation of Qt6/WASM arch on windows (#583,#584)
* Docs: allow localization (#588)
* Docs: Add Japanese translation (#595)

`v3.0.1`_ (30, Sep. 2022)
=========================

* Actions: Fix standalone executable upload (#581)
* Actions: Bump versions (#579)
  - pypa/gh-action-pypi-publish@v1
  - actions/setup-python@v4

`v3.0.0`_ (29, Sep. 2022)
=========================

Added
-----
* Automatically install desktop qt when required for android/ios qt installations(#540)

Fixed
-----
* Tolerate empty DownloadArchive tags while parsing XML(#563)
* Fix standalone executable build for windows (#565,#567)

Changed
-------
* Update Security policy
* Update combinations.json(#566)
* CI: now test on MacOS 12(#541)

`v2.2.3`_ (17, Aug. 2022)
=========================

Fixed
-----
* Building standalone executable: aqt.exe (#556,#557)

Added
-----
* Docs: add explanation of ``list-qt --long-modules`` (#555)


`v2.2.2`_ (11, Aug. 2022)
=========================

Added
-----
* Add ``aqt list-qt --long-modules`` (#543,#547)

Fixed
-----
* Fix kwargs passed up AqtException inheritance tree (#550)


`v2.2.1`_ (9, Aug. 2022)
------------------------

Changed
-------
* ``install-qt`` command respect ``--base`` argument option when
  retrieve metadata XML files by making ``MetadataFactory``
  respect ``baseurl`` set. (#545)

`v2.2.0`_ (2, Aug. 2022)
========================

Added
-----
* Add code of conduct (#535)

Changed
-------
* test: prevent use of flake8@5.0 (#544)
* Improve tox and pytest config(#544)
* Properly retrieve folder names from html pages of all mirrors(#520)
* Log: left align the level name (#539)
* Update combinations (#537)
* Introduce Updates.xml data class and parser (#533)
* archives: do not keep update.xml text in field (#534)
* docs: Bump sphinx@5.0 (#524)

Fixed
-----
* Update readthedocs config (#535)
* Fix readme description of list-qt (#527)

Deprecated
----------
* Deprecate setup.py file (#531)

`v2.1.0`_ (14, Apr. 2022)
=========================

Changed
-------
* Change security policy(#506):
  Supported 2.0.x
  Unsupported 1.2.x and before
* Bump py7zr@0.18.3(#509)
* pyproject.toml configuration
  * project section(#507)
  * setuptools_scm settings(#508)
* Use SHA256 hash from trusted mirror for integrity check (#493)
* Update combinations.xml
  * QtDesignStudio generation2 (#486)
  * IFW version (from 42 to 43) change (#495)
  * Support Qt 6.2.4 (#502)
* Update fallback mirror list (#485)

Fixed
-----
* Fix patching of Qt6.2.2-ios(#510, #503)
* Test: Conditionally install dependencies on Ubuntu (#494)

Added
-----
* doc: warn about unrelated aqt package (#490)
* doc: add explanation of --config flag in CLI docs (#491)
* doc: note about MSYS2/Mingw64 environment

Security
--------
* Use secrets for secure random numbers(#498)
* Use defusedxml to parse Updates.xml file to avoid attack(#498)
* Improve get_hash function(#504)
* Check Update.xml file with SHA256 hash (#493)


.. _Unreleased: https://github.com/miurahr/aqtinstall/compare/v3.1.1...HEAD
.. _v3.1.1: https://github.com/miurahr/aqtinstall/compare/v3.1.0...v3.1.1
.. _v3.1.0: https://github.com/miurahr/aqtinstall/compare/v3.0.2...v3.1.0
.. _v3.0.2: https://github.com/miurahr/aqtinstall/compare/v3.0.1...v3.0.2
.. _v3.0.1: https://github.com/miurahr/aqtinstall/compare/v3.0.0...v3.0.1
.. _v3.0.0: https://github.com/miurahr/aqtinstall/compare/v2.2.3...v3.0.0
.. _v2.2.3: https://github.com/miurahr/aqtinstall/compare/v2.2.2...v2.2.3
.. _v2.2.2: https://github.com/miurahr/aqtinstall/compare/v2.2.1...v2.2.2
.. _v2.2.1: https://github.com/miurahr/aqtinstall/compare/v2.2.0...v2.2.1
.. _v2.2.0: https://github.com/miurahr/aqtinstall/compare/v2.1.0...v2.2.0
.. _v2.1.0: https://github.com/miurahr/aqtinstall/compare/v2.0.6...v2.1.0

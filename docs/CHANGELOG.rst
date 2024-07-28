:tocdepth: 1

.. default-role:: any

.. _changes:

==========
ChangeLog
==========

All notable changes to this project will be documented in this file.

`Unreleased`_
=============

`v3.1.17`_ (28, July 2024)
==========================

Fixed
-----
* list and install Qt 6.8.0 and windows_arm64(#800)
* installation of android for Qt 6.8.0 (#801)

`v3.1.16`_ (16, June 2024)
==========================

Fixed
-----
* Install Qt for Android 6.7.* (#791)
* Override host/target for src/docs if Qt > 6.7.0 (#776)

Deprecated
----------
* Drop support for python 3.7(#741)

`v3.1.15`_ (4, May 2024)
========================

Fixed
-----
* Fix unintentional broken pyproject.toml

`v3.1.14`_ (27, Apr. 2024)
==========================

Fixed
-----
* Fix binary release CD provisioning

`v3.1.13`_ (13, Apr. 2024)
==========================

Added
-----
- Add support for arm64 architecture on linux desktop (#766)

Changed
-------
- Add Qt 6.6.3 as known version (#773)

Document
--------
- Add example command line that show combinations of sub-commands (#759)

`v3.1.12`_ (2, Mar. 2024)
=========================

Fixed
-----
- Fix generating combination issue with Linux Qt 6.7 (#756,#757)

Added
-----
- Add docs clarifying list-doc and install-doc (#754)

Changed
-------
- Add Qt 6.7(#758)
- Update mingw variations (#758)
- Update IFW version to 47 (#763)
- Update Flake8@7.0.0

`v3.1.11`_ (28, Nov. 2023)
==========================

Fixed
-----
- Patch ``*.prl`` and ``*.pc`` for mingw (#640, #739)

Changed
-------
- Add Qt 6.6.1 as known version (#740)
- chore: Improved CI to catch the problem with incorrect PRL files (#738)
- chore: Update CI execution trigger/schedule (#735)
    - Full tests weekly on master
        - mac, windows and linux
        - Qt 5.12.12, 5.15.14, 6.5.3
        - Python 3.9, 3.10, 3.11 and 3.12
        - check sample app built
    - Change trigger for GitHub actions
        - mac, windows and linux
        - Qt 4.9.9, 6.1.0
        - Python 3.9 and 3.12
        - check qmake works

`v3.1.10`_ (14, Nov. 2023)
==========================

Fixed
-----
- list_* commands ignore base url setting (#731,#732)

Changed
-------
- chore: support build on git export (#730)

`v3.1.9`_ (6, Nov. 2023)
========================

Security
--------
* CVE-2023-32681: Bump requests@2.31.0 (#724)

Changed
-------
* Remove a specific mirror from fallback (#688)
* add ``debug`` extras for test and check (#725)
* Bump pytest-remotedata@0.4.1
* Bump flake8,flake8-isort@6.0.0 (#726)
* docs: change interpreted text to inline literals (#728)

Added
-----
* macOS binary build (#722)
* ``ignore_hash`` and ``hash_algorithm`` options (#684)

`v3.1.8`_ (1, Nov. 2023)
========================

Changed
-------
- Add 6.5.3 and openssl as known versions (#718)
- Docs: remove deprecated configuration description (#714)
- Test: test on python 3.8, 3.9 and 3.11 (#715)
- Docs: Update documentation for ``--autodesktop`` flag (#713)
- Use 'tar' filter when extracting tarfiles (#707)
- Log a warning when aqtinstall falls back to an external 7z extraction tool (#705)
- Bump py7zr@0.20.6(#702)

Fixed
-----
- Fix failed CI (#716)
- Fix installation of win64_msvc2019_arm64 arch (#711)
- Fix ``test_install`` that fails on Python<3.11.4 (#708)
- Fix failing documentation builds (#706)
- Fix: exception when target path is relative (#702)

`v3.1.7`_ (1, Aug. 2023)
========================

Added
-----
Add support for standalone sdktool installation(#677)

Fixed
-----
- Fixed command to check tools_mingw90 (#680)
- Fixed help text for list-tool

Changed
-------
* Add Qt 6.6.0, 6.5.2 and 6.5.1 as known version(#685,#698)
* Default blacklist setting(#689)
* Add test for sdktool(#678)


`v3.1.6`_ (4, May, 2023)
========================

Added
-----
* Add opensslv3 as known module (#674)
* Add code signature for standalone binary

`v3.1.5`_ (30, Mar. 2023)
=========================

Fixed
-----
* Fix failure to install Qt 6.4.3 source and docs on Windows(#665)
* Fix failed .tar.gz extraction in ``install-src`` and ``install-doc`` (#663)

`v3.1.4`_ (25, Mar. 2023)
=========================

Changed
-------
* Add Qt 6.4.3 as known version(#661)
* Catch OSError(errno.ENOSPC) and PermissionError (#657)
* Update security policy


`v3.1.3`_ (2, Mar. 2023)
========================

Changed
-------
* make the message about "unknown" Qt versions and modules
  more friendly and easy to understand (#646,#654)


`v3.1.2`_ (17, Feb. 2023)
=========================

Fixed
-----
* CI: Pin checkout at v3 in all workflows(#649)
* Fix list-qt and install-qt handling of WASM for Qt 6.5.0 (#648)

Changed
-------
* Update combinations.xml (#650)
* Update documentation for ``--autodesktop`` flag (#638)

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


.. _Unreleased: https://github.com/miurahr/aqtinstall/compare/v3.1.17...HEAD
.. _v3.1.17: https://github.com/miurahr/aqtinstall/compare/v3.1.16...v3.1.17
.. _v3.1.16: https://github.com/miurahr/aqtinstall/compare/v3.1.15...v3.1.16
.. _v3.1.15: https://github.com/miurahr/aqtinstall/compare/v3.1.14...v3.1.15
.. _v3.1.14: https://github.com/miurahr/aqtinstall/compare/v3.1.13...v3.1.14
.. _v3.1.13: https://github.com/miurahr/aqtinstall/compare/v3.1.12...v3.1.13
.. _v3.1.12: https://github.com/miurahr/aqtinstall/compare/v3.1.11...v3.1.12
.. _v3.1.11: https://github.com/miurahr/aqtinstall/compare/v3.1.10...v3.1.11
.. _v3.1.10: https://github.com/miurahr/aqtinstall/compare/v3.1.9...v3.1.10
.. _v3.1.9: https://github.com/miurahr/aqtinstall/compare/v3.1.8...v3.1.9
.. _v3.1.8: https://github.com/miurahr/aqtinstall/compare/v3.1.7...v3.1.8
.. _v3.1.7: https://github.com/miurahr/aqtinstall/compare/v3.1.6...v3.1.7
.. _v3.1.6: https://github.com/miurahr/aqtinstall/compare/v3.1.5...v3.1.6
.. _v3.1.5: https://github.com/miurahr/aqtinstall/compare/v3.1.4...v3.1.5
.. _v3.1.4: https://github.com/miurahr/aqtinstall/compare/v3.1.3...v3.1.4
.. _v3.1.3: https://github.com/miurahr/aqtinstall/compare/v3.1.2...v3.1.3
.. _v3.1.2: https://github.com/miurahr/aqtinstall/compare/v3.1.1...v3.1.2
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

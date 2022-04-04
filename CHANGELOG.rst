====================
aqtinstall changeLog
====================

All notable changes to this project will be documented in this file.

`Unreleased`_
=============

Changed
-------
* Change security policy:
  Supported 2.0.x
  Unsupported 1.2.x and before
* Bump py7zr@0.18.3(#509)
* setuptools_scm configuraiton on pyproject.toml(#508)
* Use SHA256 hash from trusted mirror for integrity check (#493)
* Check Update.xml file with SHA256 hash (#493)
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


`v2.0.6`_ (7, Feb. 2022)
========================

Fixed
-----
* Fix archives flag(#459)
* Accept the case Update.xml in Server has delimiter without space(#479)
* Fix getUrl function to use property http session and retry(#473)

Added
-----
* 32bit release binary(#471)

Changed
-------
* Update combinations.xml
  * Qt 6.2.2, 6.2.3, 6.3.0(#481,#484)

`v2.0.5`_ (11, Dec. 2021)
=========================

Changed
-------
* Reduce memory consumption: garbage collection on install subprocess(#464)
* Cache PowerShell modules on Azure Pipeline(#465)

`v2.0.4`_ (5, Dec. 2021)
=========================

Fixed
=====
* Allow duplicated install on the directory previously installed(#438,#462)
* Memory error on 32bit python on Windows(#436,#462)

Changed
=======
* Change list-src, list-doc and list-example command(#453)

`v2.0.3`_ (25, Nov. 2021)
=========================

Added
-----
* Improve --keep and new --archive-dest options(#458)

Fixed
-----
* Fix cross-platform installation failure (#450)
* CI: update OSes, Windows-2019, macOS-10.15(#444,#456)
* CI: fix failure of uploading coveralls(#446)
* CI: test for QtIFW(#451)

Changed
-------
* combinations matrix json(#452)

`v2.0.2`_ (1, Nov. 2021)
=========================

Added
-----
* Support Qt 6.2.1 (#441)

Fixed
-----
* Degraded install-tool (#442,#443)

Changed
-------
* Add suggestion to use ``--external`` for MemoryError (#439)


`v2.0.1`_ (29, Oct. 2021)
=========================

Added
-----
* Allow retries on checksum error(#420)
* Run on Python 3.10(#424)
* Add more mirrors for fallback(#432)
* Add fallback URL message(#434)

Fixed
-----
* ``--noarchives`` inconsistency(#429)
* Allow multiprocessing error propagation(#419)
* Legacy command behavior, reproduce also old bugs (#414)
* Fix crash on ``crash install-qt <host> <tgt> <spec>`` with no specified arch(#435)

Changed
-------
* Print working directory and version in error message(#418)

Security
--------
* Use HTTPS for mirror site(#430)


`v2.0.0`_ (29, Sep. 2021)
=========================

Added
-----
* Add error messages when user inputs an invalid semantic version(#291)
* Security Policy document(#341)
* CodeQL static code analysis(#341)
* CI: generate combination json in actions (#318,#343)
* Test: add and improve unit tests(#327,#359)
* Docs: getting started section(#351)
* Docs: recommend python3 for old systems(#349)
* Automatically update combinations.json (#343,#344,#345,#386,#390,#395)
* CI: test with Qt6.2 with modules(#346)
* README: link documentation for stable(#329)
* Support WASM on Qt 6.2.0(#384)
* Add Binary distribution for Windows(#393,#397)
* Add list-qt --archives feature(#400)
* Require architecture when listing modules(#401)

Changed
-------
* list subcommand now support tool information(#235)
* list subcommand can show versions, architectures and modules.(#235)
* C: bundle jom.zip in source(#295)
* Add max_retries configuration for connection(#296)
* Change settings.ini to introduce [requests] section(#297)
* Change log format for logging file.
* Extension validation for tool subcommand(#314)
* list subcommand has --tool-long option(#304, #319)
* tool subcommand now install without version spec(#299)
* README example command is now easy to copy-and-paste(#322)
* list subcommand update(#331)
* Improve handle of Ctrl-C keyboard interruption(#337)
* Update combinations.json(#344,#386)
* Turn warnings into errors when building docs(#360)
* Update documentations(#358,#357)
* Test: consolidate lint configuration to pyproject.toml(#356)
* Test: black configuration to max_line_length=125 (#356)
* New subcommand syntax (#354,#355)
* Failed on missing modules(#374)
* Failed on missing tools(#375)
* Remove 'addons' prefix for some modules for Qt6+ (#368)
* Fix inappropriate warnings(#370)
* Update README to fix version 2 (#377)
* list-qt: Specify version by SimpleSpec(#392)
* Add helpful error messages when modules/tools/Qt version does not exist(#402)

Fixed
-----
* Fix helper.getUrl() to handle several response statuses(#292)
* Fix Qt 6.2.0 target path for macOS.(#289)
* Fix WinRT installation patching(#311)
* Fix Qt 5.9.0 installation (#312)
* Link documentations for stable/latest on README
* Check python version when starting command (#352)
* README: remove '$' from example command line(#321)
* README: fix command line example lexer(#322)
* CI: fix release script launch conditions(#298)
* Handle special case for Qt 5.9.0(#364)
* Running python2 -m aqt does not trigger Python version check (#372,#373)
* docs(cli): correct the parameter of "list-tool" in an example(#399)
* Doc: Fix broken mirror link in cli.rst (#403)
* CI: fix release action fails with no files found(#405)


`v1.2.5`_ (14, Aug. 2021)
=========================

Fixed
-----
* Handle Qt 5.9 installation special case(#363,#365)


`v1.2.4`_ (17, Jul. 2021)
=========================

Fixed
-----
* Fix crash when installing Qt6.1.2 on mac(#288,#320)

`v1.2.3`_ (14, Jul. 2021)
=========================

Changed
-------
* helper: set max_retries (#296)

Fixed
-----
* Patching for winrt packages(#311)
* CI: Fix release note script
* CI: bundle jom.zip for test

`v1.2.2`_ (1, Jul. 2021)
========================

Added
-----
* Create qtenv2.bat file on windows(#279)

Fixed
-----
* Fix list subcommand to retrieve information from web(#280)
* Fix crash when installing Qt6.2.0 on mac(#288,#289)


`v1.2.1`_ (22, Jun. 2021)
=========================

Fixed
-----
* Fix crash when tool subcommand used.(#275,#276)

`v1.2.0`_ (21, Jun. 2021)
=========================

Added
-----
* Add -c/--config option to specify custom settings.ini(#246)
* Document for settings.ini configuration parameters(#246)
* Patching libtool file(.la) on mac(#267)
* CI: Add more blacklist mirrors
* Add --kde option for src subcommand(#274)

Changed
-------
* Use spawn multiprocessing on Linux platform.(#273)
* Check MD5 checksum when download(#238)
* Config settings.ini parser and URL list format(#246)
* Refactoring network connection code, consolidated to helper.py(#244)
* Refactoring exceptions, introduce exceptions.py(#244)
* Update known Qt versions combinations.(#243)
* CI: changes azure pipelines test scripts(#250)

Fixed
-----
* Fix logging during subprocess installation on macOS, and Windows(#273)
* Fix patching qmake(#259)
* Prettify help message format(#237)
* Update patching pkgconfig/lib on mac(#267)
* CI: fix check workflow(#248)
* CI: fix error on Azure/Windows(connection error)(#246)
* Fix typo in README(#326)


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
-----.. _v2.0.1: https://github.com/miurahr/aqtinstall/compare/v2.0.0...v2.0.1

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



.. _Unreleased: https://github.com/miurahr/aqtinstall/compare/v2.0.6...HEAD
.. _v2.0.6: https://github.com/miurahr/aqtinstall/compare/v2.0.5...v2.0.6
.. _v2.0.5: https://github.com/miurahr/aqtinstall/compare/v2.0.4...v2.0.5
.. _v2.0.4: https://github.com/miurahr/aqtinstall/compare/v2.0.3...v2.0.4
.. _v2.0.3: https://github.com/miurahr/aqtinstall/compare/v2.0.2...v2.0.3
.. _v2.0.2: https://github.com/miurahr/aqtinstall/compare/v2.0.1...v2.0.2
.. _v2.0.1: https://github.com/miurahr/aqtinstall/compare/v2.0.0...v2.0.1
.. _v2.0.0: https://github.com/miurahr/aqtinstall/compare/v1.2.5...v2.0.0
.. _v1.2.5: https://github.com/miurahr/aqtinstall/compare/v1.2.4...v1.2.5
.. _v1.2.4: https://github.com/miurahr/aqtinstall/compare/v1.2.3...v1.2.4
.. _v1.2.3: https://github.com/miurahr/aqtinstall/compare/v1.2.2...v1.2.3
.. _v1.2.2: https://github.com/miurahr/aqtinstall/compare/v1.2.1...v1.2.2
.. _v1.2.1: https://github.com/miurahr/aqtinstall/compare/v1.2.0...v1.2.1
.. _v1.2.0: https://github.com/miurahr/aqtinstall/compare/v1.1.6...v1.2.0
.. _v1.1.6: https://github.com/miurahr/aqtinstall/compare/v1.1.5...v1.1.6
.. _v1.1.5: https://github.com/miurahr/aqtinstall/compare/v1.1.4...v1.1.5
.. _v1.1.4: https://github.com/miurahr/aqtinstall/compare/v1.1.3...v1.1.4
.. _v1.1.3: https://github.com/miurahr/aqtinstall/compare/v1.1.2...v1.1.3
.. _v1.1.2: https://github.com/miurahr/aqtinstall/compare/v1.1.1...v1.1.2
.. _v1.1.1: https://github.com/miurahr/aqtinstall/compare/v1.1.0...v1.1.1
.. _v1.1.0: https://github.com/miurahr/aqtinstall/compare/v1.0.0...v1.1.0
.. _v1.0.0: https://github.com/miurahr/aqtinstall/compare/v0.11.1...v1.0.0

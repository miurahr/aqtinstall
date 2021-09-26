====================
aqtinstall changeLog
====================

All notable changes to this project will be documented in this file.

`Unreleased`_
=============

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



.. _Unreleased: https://github.com/miurahr/aqtinstall/compare/v1.2.5...HEAD
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

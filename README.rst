Another Qt installer(aqt)
=========================

- Release: |pypi|
- Documentation: |docs|
- Test status: |gha| and Coverage: |coveralls|

.. |pypi| image:: https://badge.fury.io/py/aqtinstall.svg
   :target: http://badge.fury.io/py/aqtinstall
.. |docs| image:: https://readthedocs.org/projects/aqtinstall/badge/?version=stable
   :target: https://aqtinstall.readthedocs.io/en/latest/?badge=stable
.. |gha| image:: https://github.com/miurahr/aqtinstall/workflows/Test%20on%20GH%20actions%20environment/badge.svg
   :target: https://github.com/miurahr/aqtinstall/actions?query=workflow%3A%22Test+on+GH+actions+environment%22
.. |coveralls| image:: https://coveralls.io/repos/github/miurahr/aqtinstall/badge.svg?branch=master
   :target: https://coveralls.io/github/miurahr/aqtinstall?branch=master

This is a utility alternative to the official graphical Qt installer, for using in CI environment where an interactive
UI is not usable such as Github Actions, Travis-CI, CircleCI, Azure-Pipelines, AppVeyor and others.

.. warning::
    This is NOT franchised with The Qt Company and The Qt Project.
    there is NO guarantee and support. Please don't ask them about aqtinstall.

    When you need official and/or commercial support about unattended install,
    please ask your Qt reseller, or help desk according to your contract.

    The official installer has a capability to scripting installation process,
    please ask a consult with `the official documents`_.


.. _`the official documents`: https://doc.qt.io/qtinstallerframework/ifw-use-cases-cli.html#unattended-usage


It can automatically download prebuilt Qt binaries for any target (you're not bound to
Linux binaries on Linux; you could also download iOS binaries).
It's working with Python >= 3.6 on Linux, macOS and Windows.

When installing QtBase package on proper platforms (eg. install linux package on linux),
aqt update Qt binaries(eg. qmake, and libQt5Core.so/Qt5Core.dll/Framework.QtCore for Qt<5.14),
and change configurations(eg. qt.conf, and qconfig.pri) to make it working well with installed directory(Qt prefix).

.. note::
    Because it is an installer utility, it can download from Qt distribution site and its mirror.
    The site is operated by The Qt Company who may remove versions you may want to use that become end of support.
    Please don't blame us. When you keep your old mirror archives and operate an archive site,
    you may be able to use aqtinstall with base URL option specified to your site.


License and copyright
---------------------

This program is distributed under MIT license.

Qt SDK and its related files are under its licenses. When using aqtinstall, you are considered
to agree upon Qt licenses. **aqtinstall installs Qt SDK as of a (L)GPL Free Software.**

For details see `Qt licensing`_ and `Licenses used in Qt5`_

.. _`Qt licensing`: https://www.qt.io/licensing/

.. _`Licenses used in Qt5`: https://doc.qt.io/qt-5/licenses-used-in-qt.html


Requirements
------------

- Minimum Python version:
    3.6
- Recommended Python version:
    3.9 (frequently tested on)

- Dependencies:
    requests
    semantic_version
    patch
    py7zr
    texttable
    bs4
    dataclasses

Documentation
-------------

There is precise documentation with many examples.
You are recommended to read the *Getting started* section.

- Getting started: https://aqtinstall.readthedocs.io/en/latest/getting_started.html
- Stable (v2.0.x): https://aqtinstall.readthedocs.io/en/stable
- Latest: https://aqtinstall.readthedocs.io/en/latest

- Old (v1.2.5) : https://aqtinstall.readthedocs.io/en/v1.2.5/index.html

Install
-------

Same as usual, it can be installed with `pip`

.. code-block:: console

    pip install -U pip
    pip install aqtinstall

You are recommended to update pip before installing aqtinstall.

.. note::
    aqtinstall depends several packages, that is required to download files from internet, and extract 7zip archives,
    some of which are precompiled in several platforms.
    Older pip does not handle it expectedly(see #230).


Example
--------

When installing Qt SDK 6.2.0 for Windows.

Check what options you can take by `list-qt` subcommand

.. code-block:: console

    aqt list-qt windows desktop --arch 6.2.0

Then you may get candidates: `win64_mingw81 win64_msvc2019_64 win64_msvc2019_arm64`.
When you decided to install Qt SDK version 6.2.0 for mingw v8.1 gcc.

.. code-block:: console

    aqt install-qt windows desktop 6.2.0 win64_mingw81

.. note::
   It is your own task to set some environment variables to fit your platform, such as PATH, QT_PLUGIN_PATH, QML_IMPORT_PATH, and QML2_IMPORT_PATH. aqtinstall will never do it for you, in order not to break the installation of multiple versions.

Testimonies
-----------

Some projects utilize aqtinstall, and there are several articles and discussions

* GitHub Actions: `install_qt`_

* Docker image: `docker aqtinstall`_

* Yet another comic reader: `YACReader`_  utilize on Azure-Pipelines

.. _`install_qt`: https://github.com/jurplel/install-qt-action
.. _`docker aqtinstall`: https://github.com/vslotman/docker-aqtinstall
.. _`pyqt5-tools`: https://github.com/altendky/pyqt5-tools
.. _`YACReader`: https://github.com/YACReader/yacreader



* Contributor Nelson's blog article: `Fast and lightweight headless Qt Installer from Qt Mirrors - aqtinstall`_

* Lostdomain.org blog: `Using Azure DevOps Pipelines with Qt`_

* Wincak's Weblog: `Using Azure CI for cross-platform Linux and Windows Qt application builds`_

* Qt Forum: `Automatic installation for Travis CI (or any other CI)`_

* Qt Forum: `Qt silent, unattended install`_

* Reddit: `Qt Maintenance tool now requires you to enter your company name`_

* Qt Study group presentation: `Another Qt CLI installer`_


.. _`Fast and lightweight headless Qt Installer from Qt Mirrors - aqtinstall`: https://mindflakes.com/posts/1/01/01/fast-and-lightweight-headless-qt-installer-from-qt-mirrors-aqtinstall/
.. _`Using Azure DevOps Pipelines with Qt`: https://lostdomain.org/2019/12/27/using-azure-devops-pipelines-with-qt/
.. _`Using Azure CI for cross-platform Linux and Windows Qt application builds`: https://www.wincak.name/programming/using-azure-ci-for-cross-platform-linux-and-windows-qt-application-builds/
.. _`Automatic installation for Travis CI (or any other CI)`: https://forum.qt.io/topic/114520/automatic-installation-for-travis-ci-or-any-other-ci/2
.. _`Qt silent, unattended install`: https://forum.qt.io/topic/122185/qt-silent-unattended-install
.. _`Qt Maintenance tool now requires you to enter your company name`: https://www.reddit.com/r/QtFramework/comments/grgrux/qt_maintenance_tool_now_requires_you_to_enter/
.. _`Another Qt CLI installer`: https://www.slideshare.net/miurahr-nttdata/aqt-install-for-qt-tokyo-r-2-20196


History
-------

This program is originally shown in Kaidan project as a name `qli-installer`_.
The `aqtinstall` project extend and improve it.

.. _`qli-installer`: https://lnj.gitlab.io/post/qli-installer

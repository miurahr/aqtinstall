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

This is a utility alternative to the official graphical Qt installer, for using in CI environment
where an interactive UI is not usable, or just on command line.

It can automatically download prebuilt Qt binaries, documents and sources for target specified,
when the versions are on Qt download mirror sites.

.. note::
    Because it is an installer utility, it can download from Qt distribution site and its mirror.
    The site is operated by The Qt Company who may remove versions you may want to use that become end of support.
    Please don't blame us.

.. warning::
    This is NOT franchised with The Qt Company and The Qt Project. Please don't ask them about aqtinstall.


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

- Operating Systems:
    Linux, macOS, MS Windows


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

Same as usual, it can be installed with ``pip``:

.. code-block:: console

    pip install -U pip
    pip install aqtinstall

You are recommended to update pip before installing aqtinstall.

.. note::

    aqtinstall depends several packages, that is required to download files from internet, and extract 7zip archives,
    some of which are precompiled in several platforms.
    Older pip does not handle it expectedly(see #230).

.. note::

    When you want to use it on MSYS2/Mingw64 environment, you need to set environmental variable
    ``export SETUPTOOLS_USE_DISTUTILS=stdlib``, because of setuptools package on mingw wrongly
    raise error ``VC6.0 is not supported``

.. warning::

    There is an unrelated package `aqt` in pypi. Please don't confuse with it.

It may be difficult to set up some Windows systems with the correct version of Python and all of ``aqt``'s dependencies.
To get around this problem, ``aqtinstall`` offers ``aqt.exe``, a Windows executable that contains Python and all required dependencies.
You may access ``aqt.exe`` from the `Releases section`_, under "assets", or via the persistent link to `the continuous build`_ of ``aqt.exe``.

.. _`Releases section`: https://github.com/miurahr/aqtinstall/releases
.. _`the continuous build`: https://github.com/miurahr/aqtinstall/releases/download/Continuous/aqt.exe


Example
--------

When installing Qt SDK 6.2.0 for Windows.

Check the options that can be used with the ``list-qt`` subcommand, and query available architectures:

.. code-block:: console

    aqt list-qt windows desktop --arch 6.2.0

Then you may get candidates: ``win64_mingw81 win64_msvc2019_64 win64_msvc2019_arm64``. You can also query the available modules:

.. code-block:: console

    aqt list-qt windows desktop --modules 6.2.0


When you decide to install Qt SDK version 6.2.0 for mingw v8.1:

.. code-block:: console

    aqt install-qt windows desktop 6.2.0 win64_mingw81 -m all
 
The optional `-m all` argument installs all the modules available for Qt 6.2.0; you can leave it off if you don't want those modules.

To install Qt 6.2.0 with the modules 'qtcharts' and 'qtnetworking', you can use this command (note that the module names are lowercase):

.. code-block:: console

    aqt install-qt windows desktop 6.2.0 win64_mingw81 -m qtcharts qtnetworking


When aqtinstall downloads and installs packages, it updates package configurations
such as prefix directory in ``bin/qt.conf``, and ``bin/qconfig.pri``
to make it working well with installed directory.

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
The ``aqtinstall`` project extend and improve it.

.. _`qli-installer`: https://lnj.gitlab.io/post/qli-installer

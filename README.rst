Another Qt installer(aqt)
=========================

- Release: |pypi|
- Documents: |docs|
- Test status: |gha|


.. |pypi| image:: https://badge.fury.io/py/aqtinstall.svg
   :target: http://badge.fury.io/py/aqtinstall
.. |docs| image:: https://readthedocs.org/projects/aqtinstall/badge/?version=latest
   :target: https://aqtinstall.readthedocs.io/en/latest/?badge=latest
.. |gha| image:: https://github.com/miurahr/aqtinstall/workflows/Test%20on%20GH%20actions%20environment/badge.svg
   :target: https://github.com/miurahr/aqtinstall/actions?query=workflow%3A%22Test+on+GH+actions+environment%22

This is a utility alternative to the official graphical Qt installer, for using in CI environment where an interactive
UI is not usable such as Github Actions, Travis-CI, CircleCI, Azure-Pipelines, AppVeyor and others.

.. warning::
    This is NOT franchised with The Qt Comapany and The Qt Project.
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
aqt update Qt binaries(eg. qmake, and libQt5Core.so/Qt5Core.dll/Freamework.QtCore for Qt<5.14),
and change configurations(eg. qt.conf, and qconfig.pri) to make it working well with installed directory(Qt prefix).

The aqtinstall does not update PATH environment variable.

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

- Minimum Python version:  3.6
- Recommended Python version: 3.8, 3.9 (frequently tested on)

- Dependent libraries: requests, py7zr


Install
-------

Same as usual, it can be installed with `pip`

.. code-block:: bash

    $ pip install -U pip
    $ pip install aqtinstall

You are recommended to update pip before installing aqtinstall.

.. note::
    aqtinstall depends several packages, that is required to download files from internet, and extract 7zip archives,
    some of which are precompiled in several platforms.
    Older pip does not handle it expectedly(see #230).


Usage
-----

General usage looks like this:

.. code-block:: bash

    aqt [-h][--help][-O | --outputdir <directory>][-b | --base <mirror url>][-E | --external <7zip command>] \
        install <qt-version> <host> <target> [<arch>] [-m all | -m [extra module] [extra module]...] [--internal]
        [--archives <archive>[ <archive>...]] [--timeout <timeout(sec)>]

You can also call with ``python -m aqt`` syntax as well as command script ``aqt``.

* The Qt version is formatted like this: `5.11.3`
* Host is one of: `linux`, `mac`, `windows`
* Target is one of: `desktop`, `android`, `ios` (iOS only works with mac host)
* For some platforms you also need to specify an arch:
    * For windows, choose one of:
        * `win64_msvc2019_64`, `win32_msvc2019`,
        * `win64_msvc2017_64`, `win32_msvc2017`,
        * `win64_msvc2015_64`, `win32_msvc2015`,
        * `win64_mingw81`, `win32_mingw81`,
        * `win64_mingw73`, `win32_mingw73`,
        * `win64_mingw53`, `win32_mingw53`,
        * `win64_msvc2019_winrt_x64`, `win64_msvc2019_winrt_x86`, `win64_msvc2019_winrt_armv7`
        * `win64_msvc2017_winrt_x64`, `win64_msvc2017_winrt_x86`, `win64_msvc2017_winrt_armv7`
    * For android and Qt 6 or Qt 5.13 and below, choose one of: `android_x86_64`, `android_arm64_v8a`, `android_x86`,
      `android_armv7`
* You can specify external 7zip command path instead of built-in extractor.
* When specifying `all` for extra modules option `-m` all extra modules are installed.


Installing tool and utility (Experimental)
------------------------------------------

You can install tools and utilities using following syntax;

.. code-block:: bash

    python -m aqt [-h][--help][-O | --outputdir <directory>][-b | --base <mirror url>][-E | --external <7zip command>] \
        tool <host> <tool_name> <tool-version> <arch> [--timeout <timeout>]

* tool_name is one of `tools_ifw`, `tools_vcredist`, and `tools_openssl`.
* arch is full qualified tool name such as `qt.tools.ifw.31` which values can be seen on Qt `archive_site`_
  This is a quite experimental feature, may not work and please use it with your understanding what you are doing.
* It does not recognize 'installscript.qs'.
  When using tools which depends on a qt script, you should do something by yourself.

.. _`archive_site`: https://download.qt.io/online/qtsdkrepository/linux_x64/desktop/tools_ifw/


Target directory
----------------

aqt can take option '--outputdir' or '-O' that specify a target directory.

The Qt packages are installed under current directory as such `Qt/<ver>/gcc_64/`
If you want to install it in `C:\Qt` as same as standard gui installer default,
run such as follows:

.. code-block:: bash

    C:\> mkdir Qt
    C:\> aqt install --outputdir c:\Qt 5.11.3 windows desktop win64_msvc2019_64

Command examples
----------------

Example: Installing Qt SDK 5.12.0 for Linux with QtCharts and QtNetworkAuth:

.. code-block:: bash

    pip install aqtinstall
    aqt install --outputdir /opt/Qt 5.12.0 linux desktop -m qtcharts qtnetworkauth


Example: Installing Android (armv7) Qt 5.10.2:

.. code-block:: bash

    aqt install 5.10.2 linux android android_armv7


Example: Installing Android Qt 5.15.2:

.. code-block:: bash

    aqt install 5.15.2 linux android android


Example: Install examples, doc and source:

.. code-block:: bash

    C:\ aqt examples 5.15.0 windows desktop -m qtcharts qtnetworkauth
    C:\ aqt doc 5.15.0 windows desktop -m qtcharts qtnetworkauth
    C:\ aqt src 5.15.0 windows desktop


Example: Install Web Assembly for Qt5

.. code-block:: bash

    aqt install 5.15.0 linux desktop wasm_32


Example: Install an Install FrameWork (IFW):

.. code-block:: bash

    aqt tool linux tools_ifw 4.0 qt.tools.ifw.40


Example: Install vcredist:

.. code-block:: bash

    C:\ aqt tool windows tools_vcredist 2019-02-13-1 qt.tools.vcredist_msvc2019_x64
    C:\ .\Qt\Tools\vcredist\vcredist_msvc2019_x64.exe /norestart /q


Example: Install MinGW on Windows

.. code-block:: bash

    C:\ aqt tool -O c:\Qt windows tools_mingw 8.1.0-1-202004170606 qt.tools.win64_mingw810w
    c:\ set PATH=C:\Qt\Tools\mingw810_64\bin


Example: Install Qt6 for android

.. code-block:: bash

    aqt install -O qt 6.1.0 linux desktop
    aqt install -O qt 6.1.0 linux android android_armv7
    qt/6.1.0/android_armv7/bin/qmake -query


Example: Install Qt6 for ios/mac

.. code-block:: bash

    aqt install -O qt 6.1.0 mac desktop
    aqt install -O qt 6.1.0 mac ios ios
    qt/6.1.0/ios/bin/qmake -query


Example: Show help message

.. code-block:: bash

    aqt help


Environment Variables
---------------------

It is users task to set some environment variables to fit your platform such as


.. code-block:: bash

   export PATH=/path/to/qt/x.x.x/clang_64/bin/:$PATH
   export QT_PLUGIN_PATH=/path/to/qt/x.x.x/clang_64/plugins/
   export QML_IMPORT_PATH=/path/to/qt/x.x.x/clang_64/qml/
   export QML2_IMPORT_PATH=/path/to/qt/x.x.x/clang_64/qml/

aqtinstall never do it for you because not to break multiple installation versions.



Supported CI platforms
----------------------

There are no limitation for CI platform but currently it is tested on Azure Pipelines and Github actions.
If you want to use it with Github actions, `install_qt`_ action will help you.
If you want to use it with Azure Pipelines, blog article `Using Azure DevOps Pipelines with Qt`_ may be informative.


(Advanced) Force dependency
---------------------------

(Here is a note for advanced user who knows python/pip well.)

When you have a trouble on your (minor) platform to install aqtinstall's dependency,
you can force dependencies and its versions (not recommended for ordinary use).
You can run `pip` to install individual dependencies in manual and install aqtinstall with `--no-deps`.

Example:
^^^^^^^^

Avoid installation of py7zr, python 7zip library, and force using external 7z command to extract archives.

.. code-block:: bash

    $ pip install -U pip
    $ pip install requests==2.25.1 packaging texttable
    $ pip install --no-deps aqtinstall
    $ python -m aqt --external /usr/local/bin/7z install 5.15.2 linux desktop


Testimonies
-----------

Some projects utilize aqtinstall.

* GitHub Actions: `install_qt`_

* Docker image: `docker aqtinstall`_

* PyQt5 Tools: `pyqt5-tools`_

* Yet another comic reader: `YACReader`_  utilize on Azure-Pipelines

.. _`install_qt`: https://github.com/jurplel/install-qt-action
.. _`docker aqtinstall`: https://github.com/vslotman/docker-aqtinstall
.. _`pyqt5-tools`: https://github.com/altendky/pyqt5-tools
.. _`YACReader`: https://github.com/YACReader/yacreader


Media, slide, articles and discussions
--------------------------------------

* Contributor Nelson's blog article: `Fast and lightweight headless Qt Installer from Qt Mirrors - aqtinstall`_

* Lostdomain.org blog: `Using Azure DevOps Pipelines with Qt`_

* Wincak's Weblog: `Using Azure CI for cross-platform Linux and Windows Qt application builds`_

* Qt Forum: `Automatic installation for Travis CI (or any other CI)`_

* Qt Form: `Qt silent, unattended install`_

* Qt Study group presentation: `Another Qt CLI installer`_


.. _`Fast and lightweight headless Qt Installer from Qt Mirrors - aqtinstall`: https://mindflakes.com/posts/1/01/01/fast-and-lightweight-headless-qt-installer-from-qt-mirrors-aqtinstall/
.. _`Using Azure DevOps Pipelines with Qt`: https://lostdomain.org/2019/12/27/using-azure-devops-pipelines-with-qt/
.. _`Using Azure CI for cross-platform Linux and Windows Qt application builds`: https://www.wincak.name/programming/using-azure-ci-for-cross-platform-linux-and-windows-qt-application-builds/
.. _`Automatic installation for Travis CI (or any other CI)`: https://forum.qt.io/topic/114520/automatic-installation-for-travis-ci-or-any-other-ci/2
.. _`Qt silent, unattended install`: https://forum.qt.io/topic/122185/qt-silent-unattended-install
.. _`Another Qt CLI installer`: https://www.slideshare.net/miurahr-nttdata/aqt-install-for-qt-tokyo-r-2-20196


History
-------

This program is originally shown in Kaidan project as a name `qli-installer`_.
A project `aqtinstall` extend the original to run with standard python features with Linux, Mac and Windows,
to be tested on CI platform, and to improve performance with a concurrent downloading.

.. _`qli-installer`: https://lnj.gitlab.io/post/qli-installer

Another Qt installer(aqt)
=========================


.. |pypi| image:: https://badge.fury.io/py/aqtinstall.svg
   :target: http://badge.fury.io/py/aqtinstall
.. |docs| image:: https://readthedocs.org/projects/aqtinstall/badge/?version=latest
   :target: https://aqtinstall.readthedocs.io/en/latest/?badge=latest
.. |pep8| image:: https://travis-ci.org/miurahr/aqtinstall.svg?branch=master
   :target: https://travis-ci.org/miurahr/aqtinstall
.. |macos| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.aqtinstall?branchName=master&jobName=Mac
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master
.. |ubuntu| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.aqtinstall?branchName=master&jobName=Linux
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master
.. |windows| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.aqtinstall?branchName=master&jobName=Windows
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master
.. |ext| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.aqtinstall?branchName=master&jobName=Linux%20(Specific%20Mirror)
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master
.. |gha| image:: https://github.com/miurahr/aqtinstall/workflows/Test%20on%20GH%20actions%20environment/badge.svg
   :target: https://github.com/miurahr/aqtinstall/actions?query=workflow%3A%22Test+on+GH+actions+environment%22

+--------+-----------+---------+
| Jobs   | Mac       | Release |
|        | Linux     | Status  |
|        | Windows   |         |
|        | Mirror    |         |
+--------+-----------+---------+
| Status | |macos|   | |pypi|  |
|        | |ubuntu|  | |pep8|  |
|        | |windows| | |docs|  |
|        | |ext|     |         |
|        | |gha|     |         |
+--------+-----------+---------+

This is a utility alternative to the official graphical Qt installer, for using in CI environment where an interactive UI is not usable such as Github Actions, Travis-CI, CircleCI, Azure-Pipelines, AppVeyor and others.

It can automatically download prebuilt Qt binaries for any target (you're not bound to
Linux binaries on Linux; you could also download iOS binaries).
It's working with Python > 3.5 on Linux, OS X and Windows.

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
- Recommended Python version: 3.7.5 or later

- Dependent libraries: requests, py7zr


Install
-------

Same as usual, it can be installed with `pip`

.. code-block:: bash

    $ pip install aqtinstall

Usage
-----

General usage looks like this:

.. code-block:: bash

    aqt [-h][--help][-O | --outputdir <directory>][-b | --base <mirror url>][-E | --external <7zip command>] \
        install <qt-version> <host> <target> [<arch>] [-m all | -m [extra module] [extra module]...] [--internal]
        [--archives archive]

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
    * For android and Qt 5.13 or below, choose one of: `android_x86_64`, `android_arm64_v8a`, `android_x86`,
      `android_armv7`
* You can specify external 7zip command path instead of built-in extractor.
* When specifying `all` for extra modules option `-m` all extra modules are installed.


Installing tool and utility (Experimental)
------------------------------------------

You can install tools and utilities using following syntax;

.. code-block:: bash

    python -m aqt [-h][--help][-O | --outputdir <directory>][-b | --base <mirror url>][-E | --external <7zip command>] \
        tool <host> <tool_name> <tool-version> <arch>

* tool_name is one of `tools_ifw`, `tools_vcredist`, and `tools_openssl`.
* arch is full qualified tool name such as `qt.tools.ifw.31` which values can be seen on Qt `archive_site`_
  This is a quite experimental feature, may not work and please use it with your understanding of what you are doing.
* It does not recognize 'installscript.qs'. When using tools which depends on a qt script, you should do something by yourself.

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
    sudo aqt install --outputdir /opt 5.12.0 linux desktop -m qtcharts qtnetworkauth


Example: Installing Android (armv7) Qt 5.10.2:

.. code-block:: bash

    aqt install 5.10.2 linux android android_armv7


Example: Install examples, doc and source:

.. code-block:: bash

    C:\ aqt examples 5.15.0 windows desktop -m qtcharts qtnetworkauth
    C:\ aqt doc 5.15.0 windows desktop -m qtcharts qtnetworkauth
    C:\ aqt src 5.15.0 windows desktop


Example: Install Web Assembly

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


Use cases
---------

* GitHub Actions: `install_qt`_

* Docker image: `docker aqtinstall`_

* PyQt5 Tools: `pyqt5-tools`_

* Yet another comic reader: `YACReader`_  utilize on Azure-Pipelines

.. _`install_qt`: https://github.com/jurplel/install-qt-action

.. _`docker aqtinstall`: https://github.com/vslotman/docker-aqtinstall

.. _`pyqt5-tools`: https://github.com/altendky/pyqt5-tools

.. _`YACReader`: https://github.com/YACReader/yacreader


Media and articles
------------------

* Contributor Nelson's blog article: `Fast and lightweight headless Qt Installer from Qt Mirrors: aqtinstall`_

* Lostdomain.org blog: `Using Azure DevOps Pipelines with Qt`_

* Qt Forum: `Automatic installation for Travis CI (or any other CI)`_


.. _`Fast and lightweight headless Qt Installer from Qt Mirrors: aqtinstall`: https://mindflakes.com/posts/1/01/01/fast-and-lightweight-headless-qt-installer-from-qt-mirrors-aqtinstall/

.. _`Using Azure DevOps Pipelines with Qt`: https://lostdomain.org/2019/12/27/using-azure-devops-pipelines-with-qt/

.. _`Automatic installation for Travis CI (or any other CI)`: https://forum.qt.io/topic/114520/automatic-installation-for-travis-ci-or-any-other-ci/2


History
-------

This program is originally shown in Kaidan project as a name `qli-installer`_.
A project `aqtinstall` extend the original to run with standard python features with Linux, Mac and Windows,
to be tested on CI platform, and to improve performance with a concurrent downloading.

.. _`qli-installer`: https://lnj.gitlab.io/post/qli-installer

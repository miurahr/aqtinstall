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
+--------+-----------+---------+

This is an utility replacing the official graphical Qt installer. It can
automatically download prebuilt Qt binaries for any target (you're not bound to
Linux binaries on Linux; you could also download iOS binaries).
It's working with Python > 3.5 on Linux, OS X and Windows.
It is required to install 7zip utility in your platform.

License and copyright
---------------------

This program is distributed under MIT license.

Qt SDK and its related files are under its licenses. When using aqtinstall, you are considered
to agree upon Qt licenses. **aqtinstall installs Qt SDK as of a (L)GPL Free Software.**

For details see `Qt licensing`_ and `Licenses used in Qt5`_

.. _`Qt licensing`: https://www.qt.io/licensing/

.. _`Licenses used in Qt5`: https://doc.qt.io/qt-5/licenses-used-in-qt.html

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
        install <qt-version> <host> <target> [<arch>] [-m all | -m [extra module] [extra module]...]

.. code-block:: bash

    python -m aqt [-h][--help][-O | --outputdir <directory>][-b | --base <mirror url>][-E | --external <7zip command>] \
        install <qt-version> <host> <target> [<arch>] [-m all | -m [extra module] [extra module]...]

* The Qt version is formatted like this: `5.11.3`
* Host is one of: `linux`, `mac`, `windows`
* Target is one of: `desktop`, `android`, `ios` (iOS only works with mac host)
* For some platforms you also need to specify an arch:
    * For windows, choose one of: `win64_msvc2017_64`, `win32_msvc2017`, `win64_msvc2015_64`, `win32_msvc2015`, 
      `win64_mingw73`, `win32_mingw73`, `win64_mingw53`, `win32_mingw53`, `win64_msvc2017_winrt_x64`, 
      `win64_msvc2017_winrt_x86`, `win64_msvc2017_winrt_armv7`
    * For android and Qt 5.13 or below, choose one of: `android_x86_64`, `android_arm64_v8a`, `android_x86`, 
      `android_armv7`
* You can specify external 7zip command path instead of built-in extractor.
* When specify all for extra modules option '-m' all extra modules are installed.


Installing tool and utility(Experimental)
-----------------------------------------

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
    C:\> aqt install --outputdir c:\Qt 5.11.3 windows desktop win64_msvc2017_64


Example: Installing Qt SDK 5.12.0 for Linux with QtCharts and QtNetworkAuth:

.. code-block:: bash

    pip install aqtinstall
    sudo aqt install --outputdir /opt 5.12.0 linux desktop -m qcharts qtnetworkauth


Example: Installing Android (armv7) Qt 5.10.2:

.. code-block:: bash

    aqt install 5.10.2 linux android android_armv7


Example: Install Install FrameWork(IFW):

.. code-block:: bash

    aqt tool linux tools_ifw 3.1.1 qt.tools.ifw.31


Example: Install vcredist:

.. code-block:: bash

    C:\ aqt tool windows tools_vcredist 2019-02-13-1 qt.tools.vcredist_msvc2017_x64
    C:\ .\Qt\Tools\vcredist\vcredist_msvc2017_x64.exe /norestart /q


Example: Install OpenSSL:

.. code-block:: bash

    C:\ aqt tool windows tools_openssl 1.1.1-1 qt.tools.openssl.win_x64


Example: Show help message

.. code-block:: bash

    aqt help


Supported CI platform
---------------------

There are no limitation for CI platform but currently it is tested on Azure Pipelines.
If you want to use it with Github actions, please see `install_qt`_ action.


Use cases
---------

* GitHub Actions: `install_qt`_

.. _`install_qt`: https://github.com/jurplel/install-qt-action


History
-------

This program is originally shown in `Kaidan`_ project as a name `qli-installer`.
A project `aqtinstall` extend the original to run with standard python features with Linux, Mac and Windows,
to be tested on CI platform, and to improve performance with a concurrent downloading.

.. _`kaidan`: https://git.kaidan.im/lnj/qli-installer

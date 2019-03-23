Another Qt installer(aqt)
=========================


.. image:: https://badge.fury.io/py/aqtinstall.png
   :target: http://badge.fury.io/py/aqtinstall
      :alt: PyPI version


.. |macos| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.aqtinstall?branchName=master&jobName=macOS
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master
.. |ubuntu3| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.aqtinstall?branchName=master&jobName=Ubuntu_1604_py3
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master
.. |ubuntu2| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.aqtinstall?branchName=master&jobName=Ubuntu_1604_py2
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master
.. |windows| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.aqtinstall?branchName=master&jobName=Windows
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master

+-------------+-----------+
|  OS         | Status    |
+-------------+-----------+
| MacOS       | |macos|   |
+-------------+-----------+
| Ubuntu      | |ubuntu3| |
+-------------+-----------+
| Python2     | |ubuntu2| |
+-------------+-----------+
| Windows     | |windows| |
+-------------+-----------+

This is an utility replacing the official graphical Qt installer. It can
automatically download prebuilt Qt binaries for any target (you're not bound to
Linux binaries on Linux; you could also download iOS binaries).
It's working on Linux, OS X and Windows.

Prerequisite
------------

**Dependencies**: python, 7z

It is required `p7zip` for windows, `7zip` for mac or `p7zip-full` for Ubuntu.

Install
-------

Same as usual, it can be installed with `pip`

.. code-block:: bash

    $ pip install aqtinstall

Usage
-----

General usage looks like this:

.. code-block:: bash

    aqt [-h][--help] install <qt-version> <host> <target> [<arch>]
    python -m aqt [-h][--help] install <qt-version> <host> <target> [<arch>]

* The Qt version is formatted like this: `5.11.3`
* Host is one of: `linux`, `mac`, `windows`
* Target is one of: `desktop`, `android`, `ios` (iOS only works with mac host)
* For android and windows you also need to specify an arch: `win64_msvc2017_64`,
  `win64_msvc2015_64`, `win32_msvc2015`, `win32_mingw53`, `android_x86`, `android_armv7`


The Qt packages are installed under current directory as such `Qt<ver>/<ver>/gcc_64/`
If you want to install it in `C:\Qt` as same as standard gui installer default,
run such as follows:

.. code-block:: bash

    C:\> mkdir Qt
    C:\> cd Qt
    C:\Qt\> aqt install 5.11.3 windows desktop win64_msvc2017_64


Example: Installing Qt 5.12.0 for Linux:

.. code-block:: bash

    pip install aqtinstall
    cd /opt
    sudo aqt install 5.12.0 linux desktop


Example: Installing Android (armv7) Qt 5.10.2:

.. code-block:: bash

    aqt install 5.10.2 linux android android_armv7


Example: Show help message

.. code-block:: bash

    aqt -h



Supported CI platform
---------------------

There are no limitation for CI platform but currently it is tested on Azure Pipelines.


License and copyright
---------------------

This program is distributed under MIT license.

Qt SDK and its related files are under its licenses. When using the utility, you are considered
to agree upon Qt licenses.
For details see `Qt licensing`_ and `Licenses used in Qt5`_

.. _`Qt licensing`: https://www.qt.io/licensing/

.. _`Licenses used in Qt5`: https://doc.qt.io/qt-5/licenses-used-in-qt.html

History
-------

This program is originally shown in `Kaidan`_ project
A project `aqtinstall` extend the original to run with standard python features with Linux, Mac and Windows,
to be tested on CI platform, and to improve performance with a concurrent downloading.

.. _`kaidan`: https://git.kaidan.im/lnj/qli-installer

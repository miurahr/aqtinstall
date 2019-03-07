Another Qt installer(aqt)
=========================

.. |macos| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.qli-installer?branchName=master&jobName=macOS
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master
.. |ubuntu3| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.qli-installer?branchName=master&jobName=Ubuntu_1604_py3
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master
.. |ubuntu2| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.qli-installer?branchName=master&jobName=Ubuntu_1604_py2
   :target: https://dev.azure.com/miurahr/github/_build/latest?definitionId=6&branchName=master
.. |windows| image:: https://dev.azure.com/miurahr/github/_apis/build/status/miurahr.qli-installer?branchName=master&jobName=Windows
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

**Dependencies**: python3, 7z

It is required `p7zip` for windows, `7zip` for mac or `p7zip-full` for Ubuntu.

Usage
-----

General usage looks like this:

.. code-block:: bash

    aqtinst [-h][--help] <qt-version> <host> <target> [<arch>]

The Qt version is formatted like this: `5.11.3`
Host is one of: `linux`, `mac`, `windows`  
Target is one of: `desktop`, `android`, `ios` (iOS only works with mac host)  
For android and windows you also need to specify an arch: `win64_msvc2017_64`,
`win64_msvc2015_64`, `win32_msvc2015`, `win32_mingw53`, `android_x86`,
`android_armv7`

The Qt packages are installed under current directory as such `Qt<ver>/<ver>/gcc_64/`
If you want to install it in `C:\Qt` as same as standard gui installer defuult,
run such as follows;


.. code-block:: bash

    C:\> mkdir Qt
    C:\> cd Qt
    C:\Qt\> C:\python3.7\bin\python aqtinst 5.11.3 windows win64_msvc2017_64


Example: Installing Qt 5.12.0 for Linux:

.. code-block:: bash

    aqtinst 5.12.0 linux desktop


Example: Installing Android (armv7) Qt 5.10.2:

.. code-block:: bash

    aqtinst 5.10.2 linux android android_armv7

Example: Show help message

.. code-block:: bash

    aqtinst -h

Supported CI platform
---------------------

There are no limitation for CI platform but currently we are tested on Azure Pipelines.


License and copyright
---------------------

This program is distributed under MIT license.

Qt SDK and its related files are under its licenses. When using the qli-installer.py
you are considered to agree upon these licenses.
For details see [Qt licensing](https://www.qt.io/licensing/) and [Licenses used in Qt5](https://doc.qt.io/qt-5/licenses-used-in-qt.html)

History
-------

This program is originally shown in [Kaidan project](https://git.kaidan.im/lnj/qli-installer)
The project extend the original to run with standard python3 features with Linux, Mac and Windows,
test on CI platform, and improve performance with concurrent downloading.

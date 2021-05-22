.. _string-options-ref:

Command Line Options
====================

The CLI uses argparse to parse the command line options so the short or long versions may be used and the
long options may be truncated to the shortest unambiguous abbreviation.

Generic commands
----------------

.. program::  aqt

.. option:: help

    show generic help


List command
------------------

.. program::  aqt

.. option:: list [-h | --help] [--extension <extension>] [--filter-minor <Qt minor version>]
                [--modules <Qt version> | --extensions <Qt version> | --arch <Qt version> |
                 --latest-version | --latest-modules]
                <category> <target OS> [<target variant>]

    list available tools, versions of Qt, targets, extensions, modules, and architectures.

.. describe:: category

    tools, qt5 or qt6

.. describe:: target OS (aka host in code/help text)

    linux, windows or mac

.. describe:: target variant (aka target in code/help text)

    desktop, winrt, ios or android. When omitted, the command prints all the targets available for a host OS.

.. option:: --help, -h

    Display help text

.. option:: --extension {wasm,src_doc_examples,preview,wasm_preview,x86_64,x86,armv7,arm64_v8a}

    Extension of packages to list.
    Use the `--extensions` flag to list all relevant options for a host/target.
    Incompatible with the `--extensions` flag, but may be combined with any other flag.

.. option:: --extensions <Qt version>

    Qt version in the format of "5.X.Y". When set, this prints all valid
    arguments for the `--extension` flag for Qt 5.X.Y with a host/target.
    Incompatible with all other flags.

.. option:: --filter-minor <Qt minor version>

    Print versions of Qt that have a particular minor version.
    For example, `aqt list qt5 windows desktop --filter-minor 12` would print
    all versions of Qt for Windows Desktop beginning with 5.12.
    May be combined with the `--extension` flag and either the
    `--latest-version` or `--latest-modules` flags.

.. option:: --modules <Qt version>

    Qt version in the format of "5.X.Y". When set, this lists all the modules
    available for Qt 5.X.Y with a host/target/extension.
    May be combined with the `--extension` flag.

.. option:: --arch <Qt version>

    Qt version in the format of "5.X.Y". When set, this prints all architectures
    available for Qt 5.X.Y with a host/target/extension.
    May be combined with the `--extension` flag.

.. option:: --latest-version

    Print only the newest version available
    May be combined with the `--extension` and/or `--filter-minor` flags.

.. option:: --latest-modules

    List all the modules available for the latest version of Qt, or a minor
    version if the `--filter-minor` flag is set.
    May be combined with the `--extension` and/or `--filter-minor` flags.


Installation command
--------------------

.. program::  aqt

.. option:: install <Qt version> <target OS> <target variant> <target architecture>

    install Qt library specified version and target.
    There are various combinations to accept according to Qt version.

.. describe:: Qt version

    This is a Qt version such as 5.9,7, 5.12.1 etc

.. describe:: target OS

    linux, windows or mac

.. describe:: target variant

    desktop, ios or android

.. describe:: target architecture

   * gcc_64 for linux desktop

   * clang_64 for mac desktop

   * win64_msvc2019_64, win64_msvc2017_64, win64_msvc2015_64, win32_msvc2015, win32_mingw53 for windows desktop

   * android_armv7, android_arm64_v8a, android_x86, android_x86_64 for android

.. option:: --version, -v

    Display version

.. option:: --help, -h

    Display help text

.. option:: --outputdir, -O <Output Directory>

    specify output directory.

.. option:: --base, -b <base url>

    specify mirror site base url such as  -b 'https://mirrors.ocf.berkeley.edu/qt/'
    where 'online' folder exist.

.. option:: --modules, -m <list of modules>

    specify extra modules to install as a list.

.. code-block::

    -m qtcharts qtdatavis3d qtlottie qtnetworkauth qtpurchasing qtquicktimeline qtscript qtvirtualkeyboard qtwebglplugin


.. option:: --archives <list of archives>

    [Advanced] Specify subset of archives to **limit** installed archives.
    This is advanced option and not recommended to use for general usage.
    Main purpose is speed up CI/CD process by limiting installed modules.
    It can cause broken installation of Qt SDK.

.. option:: --noarchives

    [Advanced] Specify not to install all base packages.
    This is advanced option and you should use with --modules option.
    This allow you to add modules to existent Qt installation.

Tool installation commands
--------------------------

.. program::  aqt

.. option:: src <Qt version> <target OS> <target variant>

    install Qt sources specified version and target.


.. option:: doc <Qt version> <target OS> <target variant>

    install Qt documents specified version and target.


.. option:: examples <Qt version> <target OS> <target variant>

    install Qt examples specified version and target.


.. option:: tool <target OS> <target tool name> <target tool version> <tool variant name>

    install tools specified. tool name may be 'tools_openssl_x64', 'tools_ninja', 'tools_ifw', 'tools_cmake'
    and tool variants name may be 'qt.tools.openssl.gcc_64', 'qt.tools.ninja',  'qt.tools.ifw.32', 'qt.tools.cmake'.
    You may need to looking for version number at  https://download.qt.io/online/qtsdkrepository/


Experimental commands
---------------------

.. program::  aqt

.. option:: offline_installer <Qt version> <target OS> <target architecture> --archives [<package>, ...]

    [Experimental, Advanced] install Qt library specified version and target using offline installer.
    When specify old versions that has already become end-of-life, aqt download
    the installer from a proper server repository. A command intend to support version from 5.2 to 5.11.
    User may need to set environment variable QTLOGIN and QTPASSWORD properly or
    place qtaccount.ini file at proper place.

    User should specify proper package names. Otherwise it may install default
    packages.

    A feature is considered as very experimental.

.. option:: --archives <list of archives>

    archive packages to install. Expected values will be shown on log message.


Command examples
================


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

Example: install old version

.. code-block:: bash

    aqt offline_installer 5.11.2 linux gcc_64
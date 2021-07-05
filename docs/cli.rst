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
                [--modules (<Qt version> | latest) | --extensions (<Qt version> | latest) |
                 --arch (<Qt version> | latest) | --latest-version | --tool <tool name>]
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

.. option:: --extensions (<Qt version> | latest)

    Qt version in the format of "5.X.Y", or the keyword `latest`.
    When set, this prints all valid arguments for the `--extension` flag for
    Qt 5.X.Y, or the latest version of Qt if `latest` is specified.
    Incompatible with the `--extension` flag.

.. option:: --filter-minor <Qt minor version>

    Print versions of Qt that have a particular minor version.
    For example, `aqt list qt5 windows desktop --filter-minor 12` would print
    all versions of Qt for Windows Desktop beginning with 5.12.
    May be combined with any other flag to filter the output of that flag.

.. option:: --modules (<Qt version> | latest)

    Qt version in the format of "5.X.Y". When set, this lists all the modules
    available for Qt 5.X.Y with a host/target/extension, or the latest version
    of Qt if `latest` is specified.

.. option:: --arch (<Qt version> | latest)

    Qt version in the format of "5.X.Y". When set, this prints all architectures
    available for Qt 5.X.Y with a host/target/extension, or the latest version
    of Qt if `latest` is specified.

.. option:: --latest-version

    Print only the newest version available
    May be combined with the `--extension` and/or `--filter-minor` flags.

.. option:: --tool <tool name>

    The name of a tool. Use `aqt list tools <host> <target>` to see accepted values.
    This flag only works with the 'tools' category, and may noy be combined with
    any other flags.
    When set, this prints all 'tool variant names' available.

    The output of this command is meant to be used with the `aqt tool` command:
    See the :ref:`Tool installation commands` below.

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

.. option:: src <Qt version> <target OS> <target variant> [--kde] [--archives <archive>]

    install Qt sources specified version and target. by adding --kde option,
    KDE patch collection is applied for qtbase tree. It is only applied to
    Qt 5.15.2. When specified version is other than it, command will abort
    with error when using --kde.
    You can specify --archives option to install only a specified source
    such as qtbase.


.. option:: doc <Qt version> <target OS> <target variant>

    install Qt documents specified version and target.


.. option:: examples <Qt version> <target OS> <target variant>

    install Qt examples specified version and target.


.. option:: tool <target OS> <target tool name> <target tool version> <tool variant name>

    install tools specified. tool name may be 'tools_openssl_x64', 'tools_ninja', 'tools_ifw', 'tools_cmake'
    and tool variants name may be 'qt.tools.openssl.gcc_64', 'qt.tools.ninja',  'qt.tools.ifw.32', 'qt.tools.cmake'.
    You may use the :ref:`List command` with the `--tool` flag to display what tool variant names are available.
    You may need to looking for version number at  https://download.qt.io/online/qtsdkrepository/


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

    C:\ aqt examples 5.15.2 windows desktop -m qtcharts qtnetworkauth
    C:\ aqt doc 5.15.2 windows desktop -m qtcharts qtnetworkauth
    C:\ aqt src 5.15.2 windows desktop --archives qtbase --kde


Example: Install Web Assembly

.. code-block:: bash

    aqt install 5.15.0 linux desktop wasm_32


Example: List available versions for Qt5 on Linux

.. code-block:: bash

    aqt list qt5 linux desktop


Example: List available versions for Qt6 on macOS

.. code-block:: bash

    aqt list qt6 mac desktop


Example: List available modules for latest version of Qt6 on macOS

.. code-block:: bash

    aqt list qt6 mac desktop --modules latest    # prints 'qtquick3d qtshadertools', etc


Example: List available architectures for Qt 6.1.2 on windows

.. code-block:: bash

    aqt list qt6 windows desktop --arch 6.1.2    # prints 'win64_mingw81 win64_msvc2019_64', etc


Example: List available tools on windows

.. code-block:: bash

    aqt list tools windows desktop    # prints 'tools_ifw tools_qtcreator', etc


Example: List the variants of IFW available:

.. code-block:: bash

    aqt list tools linux desktop --tool tools_ifw   # prints 'qt.tools.ifw.41'


Example: Install an Install FrameWork (IFW):

.. code-block:: bash

    aqt tool linux tools_ifw 4.1 qt.tools.ifw.41


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

.. _string-options-ref:

Command Line Options
====================

The CLI uses argparse to parse the command line options so the short or long versions may be used and the
long options may be truncated to the shortest unambiguous abbreviation.

Generic commands
----------------

.. program::  aqt help

.. code-block:: bash

    aqt help

show generic help


List Qt command
------------------

.. program::  aqt list-qt

.. code-block:: bash

    aqt list-qt [-h | --help]
                [--extension <extension>]
                [--spec <specification>]
                [--modules    (<Qt version> | latest) |
                 --extensions (<Qt version> | latest) |
                 --arch       (<Qt version> | latest) |
                 --latest-version]
                <target OS> [<target variant>]

List available versions of Qt, targets, extensions, modules, and architectures.

.. describe:: target OS (aka host in code/help text)

    linux, windows or mac

.. describe:: target variant (aka target in code/help text)

    desktop, winrt, ios or android.
    When omitted, the command prints all the targets available for a host OS.
    Note that winrt is only available on Windows, and ios is only available on Mac OS.

.. option:: --help, -h

    Display help text

.. option:: --extension <Extension>

    Extension of packages to list
    {wasm,src_doc_examples,preview,wasm_preview,x86_64,x86,armv7,arm64_v8a}

    Use the `--extensions` flag to list all relevant options for a host/target.
    Incompatible with the `--extensions` flag, but may be combined with any other flag.

.. option:: --spec <Specification>

    Print versions of Qt within a version specification, as explained here:
    https://python-semanticversion.readthedocs.io/en/latest/reference.html#semantic_version.SimpleSpec
    You can specify partial versions, inequalities, etc.
    `"*"` would match all versions of Qt; `">6.0.2,<6.2.0"` would match all
    versions of Qt between 6.0.2 and 6.2.0, etc.
    For example, `aqt list-qt windows desktop --spec "5.12"` would print
    all versions of Qt for Windows Desktop beginning with 5.12.
    May be combined with any other flag to filter the output of that flag.

.. option:: --extensions (<Qt version> | latest)

    Qt version in the format of "5.X.Y", or the keyword `latest`.
    When set, this prints all valid arguments for the `--extension` flag for
    Qt 5.X.Y, or the latest version of Qt if `latest` is specified.
    Incompatible with the `--extension` flag.

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
    May be combined with the `--extension` and/or `--spec` flags.


List Tool command
-----------------

.. program::  aqt list-tool

.. code-block:: bash

    aqt list-tool [-h | --help] [-l | --long] <target OS> [<target variant>] [<tool name>]

List available tools

.. describe:: target OS (aka host in code/help text)

    linux, windows or mac

.. describe:: target variant (aka target in code/help text)

    desktop, winrt, ios or android.
    When omitted, the command prints all the targets available for a host OS.
    Note that winrt is only available on Windows, and ios is only available on Mac OS.

.. describe:: tool name

    The name of a tool. Use `aqt list-tool <target OS> <target variant>` to see accepted values.
    When set, this prints all 'tool variant names' available.

    The output of this command is meant to be used with the `aqt tool` command:
    See the :ref:`Tools installation command` below.

.. option:: --help, -h

    Display help text


.. option:: --long, -l

    Long display: shows extra metadata associated with each tool variant.
    This metadata is displayed in a table, and includes versions and release dates
    for each tool. If your terminal is wider than 95 characters, `aqt list-tool`
    will also display the names and descriptions for each tool. An example of this
    output is displayed below.

.. code-block:: bash
    $ python -m aqt list-tool windows desktop tools_conan

     Tool Variant Name           Version         Release Date     Display Name              Description
    ============================================================================================================
    qt.tools.conan         1.33-202102101246     2021-02-10     Conan 1.33          Conan command line tool 1.33
    qt.tools.conan.cmake   0.16.0-202102101246   2021-02-10     Conan conan.cmake   Conan conan.cmake (0.16.0)



Installation command
--------------------

.. program::  aqt install

.. code-block:: bash

    aqt install <Qt version> <target OS> <target variant> <target architecture>

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


Source installation command
---------------------------

.. program::  aqt src

.. code-block:: bash

    aqt src <Qt version> <target OS> <target variant> [--kde] [--archives <archive>]

install Qt sources specified version and target.


.. describe:: Qt version

    This is a Qt version such as 5.9,7, 5.12.1 etc

.. describe:: target OS

    linux, windows or mac

.. describe:: target variant

    desktop, ios or android

.. option:: --kde

    by adding --kde option,
    KDE patch collection is applied for qtbase tree. It is only applied to
    Qt 5.15.2. When specified version is other than it, command will abort
    with error when using --kde.

.. option:: --archives

    You can specify --archives option to install only a specified source
    such as qtbase.

Document installation command
-----------------------------

.. program:: aqt doc

.. code-block:: bash

    aqt doc <Qt version> <target OS> <target variant>

install Qt documents specified version and target.

.. describe:: Qt version

    This is a Qt version such as 5.9,7, 5.12.1 etc

.. describe:: target OS

    linux, windows or mac

.. describe:: target variant

    desktop, ios or android


Example installation command
----------------------------

.. program:: aqt examples

.. code-block:: bash

    aqt examples <Qt version> <target OS> <target variant>

install Qt examples specified version and target.


.. describe:: Qt version

    This is a Qt version such as 5.9,7, 5.12.1 etc

.. describe:: target OS

    linux, windows or mac

.. describe:: target variant

    desktop, ios or android


Tools installation command
---------------------------

.. program::  aqt tool

.. code-block:: bash

    aqt tool <target OS> <target variant> <tool name> [<tool variant name>]

.. describe:: target OS

    linux, windows or mac

.. describe:: tool name

    install tools specified. tool name may be 'tools_openssl_x64', 'tools_vcredist', 'tools_ninja',
    'tools_ifw', 'tools_cmake'

.. describe:: tool variant name

    tool variant names may be 'qt.tools.openssl.gcc_64', 'qt.tools.vcredist_msvc2013_x64'.

You should use the :ref:`List Tool command` to display what tools and tool variant names are available.
    

Command examples
================

.. program:: None

Example: Installing Qt SDK 5.12.0 for Linux with QtCharts and QtNetworkAuth:

.. code-block:: console

    pip install aqtinstall
    sudo aqt install --outputdir /opt 5.12.0 linux desktop -m qtcharts qtnetworkauth


Example: Installing Android (armv7) Qt 5.10.2:

.. code-block:: console

    aqt install 5.10.2 linux android android_armv7


Example: Install examples, doc and source:

.. code-block:: console

    aqt examples 5.15.2 windows desktop -m qtcharts qtnetworkauth
    aqt doc 5.15.2 windows desktop -m qtcharts qtnetworkauth
    aqt src 5.15.2 windows desktop --archives qtbase --kde


Example: Install Web Assembly

.. code-block:: console

    aqt install 5.15.0 linux desktop wasm_32


Example: List available versions of Qt on Linux

.. code-block:: console

    aqt list-qt linux desktop


Example: List available versions of Qt6 on macOS

.. code-block:: console

    aqt list-qt mac desktop --spec "6"


Example: List available modules for latest version of Qt on macOS

.. code-block:: console

    aqt list-qt mac desktop --modules latest    # prints 'qtquick3d qtshadertools', etc


Example: List available architectures for Qt 6.1.2 on windows

.. code-block:: console

    aqt list-qt windows desktop --arch 6.1.2    # prints 'win64_mingw81 win64_msvc2019_64', etc


Example: List available tools on windows

.. code-block:: console

    aqt list-tool windows desktop    # prints 'tools_ifw tools_qtcreator', etc


Example: List the variants of IFW available:

.. code-block:: console

    aqt list-tool linux desktop tools_ifw       # prints 'qt.tools.ifw.41'
    # Alternate: `tools_` prefix is optional
    aqt list-tool linux desktop ifw             # prints 'qt.tools.ifw.41'


Example: List the variants of IFW, including version, release date, description, etc.:

    aqt list-tool linux desktop tools_ifw -l    # prints a table of metadata


Example: Install an Install FrameWork (IFW):

.. code-block:: console

    aqt tool linux desktop tools_ifw


Example: Install vcredist on Windows:

.. code-block:: doscon


    aqt tool windows tools_vcredist
    .\Qt\Tools\vcredist\vcredist_msvc2019_x64.exe /norestart /q


Example: Install MinGW on Windows

.. code-block:: doscon

    aqt tool -O c:\Qt windows tools_mingw qt.tools.win64_mingw810
    set PATH=C:\Qt\Tools\mingw810_64\bin


Example: Show help message

.. code-block:: console

    aqt help

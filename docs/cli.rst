.. _string-options-ref:

Command Line Options
====================

The CLI uses argparse to parse the command line options so the short or long versions may be used and the
long options may be truncated to the shortest unambiguous abbreviation.

Generic commands
----------------

.. program::  help

.. code-block:: bash

    aqt help

show generic help

.. program::  version

.. code-block:: bash

    aqt version

display version


.. _list qt command:

List Qt command
------------------

.. program::  list-qt

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

    Use the ``--extensions`` flag to list all relevant options for a host/target.
    Incompatible with the ``--extensions`` flag, but may be combined with any other flag.

.. option:: --spec <Specification>

    Print versions of Qt within a version specification, as explained here:
    https://python-semanticversion.readthedocs.io/en/latest/reference.html#semantic_version.SimpleSpec
    You can specify partial versions, inequalities, etc.
    ``"*"`` would match all versions of Qt; ``">6.0.2,<6.2.0"`` would match all
    versions of Qt between 6.0.2 and 6.2.0, etc.
    For example, ``aqt list-qt windows desktop --spec "5.12"`` would print
    all versions of Qt for Windows Desktop beginning with 5.12.
    May be combined with any other flag to filter the output of that flag.

.. option:: --extensions (<Qt version> | latest)

    Qt version in the format of "5.X.Y", or the keyword ``latest``.
    When set, this prints all valid arguments for the ``--extension`` flag for
    Qt 5.X.Y, or the latest version of Qt if ``latest`` is specified.
    Incompatible with the ``--extension`` flag.

.. option:: --modules (<Qt version> | latest)

    Qt version in the format of "5.X.Y". When set, this lists all the modules
    available for Qt 5.X.Y with a host/target/extension, or the latest version
    of Qt if ``latest`` is specified.

.. option:: --arch (<Qt version> | latest)

    Qt version in the format of "5.X.Y". When set, this prints all architectures
    available for Qt 5.X.Y with a host/target/extension, or the latest version
    of Qt if ``latest`` is specified.

.. option:: --latest-version

    Print only the newest version available
    May be combined with the ``--extension`` and/or ``--spec`` flags.


.. _list tool command:

List Tool command
-----------------

.. program::  list-tool

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
    for each tool. If your terminal is wider than 95 characters, ``aqt list-tool``
    will also display the names and descriptions for each tool. An example of this
    output is displayed below.

.. code-block:: bash

    $ python -m aqt list-tool windows desktop tools_conan

     Tool Variant Name           Version         Release Date     Display Name              Description
    ============================================================================================================
    qt.tools.conan         1.33-202102101246     2021-02-10     Conan 1.33          Conan command line tool 1.33
    qt.tools.conan.cmake   0.16.0-202102101246   2021-02-10     Conan conan.cmake   Conan conan.cmake (0.16.0)


.. _qt installation command:

Qt Installation command
-----------------------

.. program:: install-qt

.. code-block:: bash

    aqt install-qt
        [-h | --help]
        [-O | --outputdir <directory>]
        [-b | --base <mirror url>]
        [--timeout <timeout(sec)>]
        [-E | --external <7zip command>]
        [--internal]
        [-k | --keep]
        [-m | --modules (all | <module> [<module>...])]
        [--archives <archive> [<archive>...]]
        [--noarchives]
        <host> <target> <Qt version> [<arch>]

install Qt library specified version and target.
There are various combinations to accept according to Qt version.

.. describe:: target OS

    linux, windows or mac

.. describe:: target variant

    desktop, ios or android

.. describe:: Qt version

    This is a Qt version such as 5.9.7, 5.12.1 etc.
    Use the :ref:`List Qt Command` to list available versions.

.. describe:: target architecture

   * gcc_64 for linux desktop

   * clang_64 for mac desktop

   * win64_msvc2019_64, win64_msvc2017_64, win64_msvc2015_64, win32_msvc2015, win32_mingw53 for windows desktop

   * android_armv7, android_arm64_v8a, android_x86, android_x86_64 for android

    Use the :ref:`List Qt Command` to list available architectures.

.. option:: --help, -h

    Display help text

.. option:: --outputdir, -O <Output Directory>

    specify output directory.
    By default, aqt installs to the current working directory.

.. option:: --base, -b <base url>

    specify mirror site base url such as  -b 'https://mirrors.ocf.berkeley.edu/qt/'
    where 'online' folder exist.

.. option:: --timeout <timeout(sec)>

    the connection timeout, in seconds, for the download site. (default: 5 sec)

.. option:: --external, -E <7zip command>

    Specify external 7zip command path. By default, aqt uses py7zr_ for this task.

.. _py7zr: https://pypi.org/project/py7zr/

.. option:: --internal

    Use the internal extractor, py7zr_

.. option:: --keep, -k

    Keep downloaded archive when specified, otherwise remove after install

.. option:: --modules, -m (<list of modules> | all)

    specify extra modules to install as a list.
    Use the :ref:`List Qt Command` to list available modules.

.. code-block::

    -m qtcharts qtdatavis3d qtlottie qtnetworkauth qtpurchasing qtquicktimeline qtscript qtvirtualkeyboard qtwebglplugin


If you wish to install every module available, you may use the ``all`` keyword
instead of a list of modules, like this:

.. code-block:: bash

    aqt install-qt <host> <target> <Qt version> <arch> -m all


.. option:: --archives <list of archives>

    [Advanced] Specify subset of archives to **limit** installed archives.
    This is advanced option and not recommended to use for general usage.
    Main purpose is speed up CI/CD process by limiting installed modules.
    It can cause broken installation of Qt SDK.

.. option:: --noarchives

    [Advanced] Specify not to install all base packages.
    This is advanced option and you should use it with ``--modules`` option.
    This allow you to add modules to existent Qt installation.


Source installation command
---------------------------

.. program::  install-src

.. code-block:: bash

    aqt install-src <target OS> <target variant> <Qt version> [--kde] [--archives <archive>]

install Qt sources specified version and target.


.. describe:: target OS

    linux, windows or mac

.. describe:: target variant

    desktop, ios or android

.. describe:: Qt version

    This is a Qt version such as 5.9,7, 5.12.1 etc

.. option:: --kde

    by adding ``--kde`` option,
    KDE patch collection is applied for qtbase tree. It is only applied to
    Qt 5.15.2. When specified version is other than it, command will abort
    with error when using ``--kde``.

.. option:: --archives

    You can specify ``--archives`` option to install only a specified source
    such as qtbase.

Document installation command
-----------------------------

.. program:: install-doc

.. code-block:: bash

    aqt install-doc <target OS> <target variant> <Qt version>

install Qt documents specified version and target.

.. describe:: target OS

    linux, windows or mac

.. describe:: target variant

    desktop, ios or android

.. describe:: Qt version

    This is a Qt version such as 5.9,7, 5.12.1 etc


Example installation command
----------------------------

.. program:: install-example

.. code-block:: bash

    aqt install-example <target OS> <target variant> <Qt version>

install Qt examples specified version and target.


.. describe:: target OS

    linux, windows or mac

.. describe:: target variant

    desktop, ios or android

.. describe:: Qt version

    This is a Qt version such as 5.9,7, 5.12.1 etc


.. _tools installation command:

Tools installation command
---------------------------

.. program::  install-tool

.. code-block:: bash

    aqt install-tool <target OS> <target variant> <tool name> [<tool variant name>]

.. describe:: target OS

    linux, windows or mac

.. describe:: target variant

    desktop, ios or android

.. describe:: tool name

    install tools specified. tool name may be 'tools_openssl_x64', 'tools_vcredist', 'tools_ninja',
    'tools_ifw', 'tools_cmake'

.. option:: tool variant name

    Optional field to specify tool variant. It may be required for vcredist and mingw installation.
    tool variant names may be 'qt.tools.win64_mingw810', 'qt.tools.vcredist_msvc2013_x64'.

You should use the :ref:`List Tool command` to display what tools and tool variant names are available.
    

Command examples
================

.. program:: None

Example: Installing Qt SDK 5.12.0 for Linux with QtCharts and QtNetworkAuth:

.. code-block:: console

    pip install aqtinstall
    sudo aqt install-qt --outputdir /opt linux desktop 5.12.0 -m qtcharts qtnetworkauth


Example: Installing Android (armv7) Qt 5.10.2:

.. code-block:: console

    aqt install-qt linux android 5.10.2 android_armv7


Example: Install examples, doc and source:

.. code-block:: console

    aqt install-example windows desktop 5.15.2 -m qtcharts qtnetworkauth
    aqt install-doc windows desktop 5.15.2 -m qtcharts qtnetworkauth
    aqt install-src windows desktop 5.15.2 --archives qtbase --kde


Example: Install Web Assembly

.. code-block:: console

    aqt install-qt linux desktop 5.15.0 wasm_32


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

    aqt install-tool linux desktop tools_ifw


Example: Install vcredist on Windows:

.. code-block:: doscon


    aqt install-tool windows tools_vcredist
    .\Qt\Tools\vcredist\vcredist_msvc2019_x64.exe /norestart /q


Example: Install MinGW on Windows

.. code-block:: doscon

    aqt install-tool -O c:\Qt windows tools_mingw qt.tools.win64_mingw810
    set PATH=C:\Qt\Tools\mingw810_64\bin


Example: Show help message

.. code-block:: console

    aqt help

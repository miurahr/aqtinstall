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


List-* Commands
---------------

These commands are used to list the packages available for installation with ``aqt``.

.. _list-qt command:

list-qt command
~~~~~~~~~~~~~~~

.. program::  list-qt

.. code-block:: bash

    aqt list-qt [-h | --help]
                [-c | --config]
                [--spec <specification>]
                [--modules      (<Qt version> | latest) <architecture> |
                 --long-modules (<Qt version> | latest) <architecture> |
                 --arch         (<Qt version> | latest) |
                 --archives     (<Qt version> | latest) architecture [modules...]
                 --latest-version]
                [--use-official-installer [<email> <password>]]
                <host> [<target>]

List available versions of Qt, targets, modules, and architectures.

.. describe:: host

    linux, linux_arm64, windows, mac or all_os for Qt 6.7+

.. describe:: target

    desktop, winrt, ios, android or wasm for Qt 6.7+
    When omitted, the command prints all the targets available for a host OS.
    Note that winrt is only available on Windows, and ios is only available on Mac OS.

.. option:: --help, -h

    Display help text

.. option:: --spec <Specification>

    Print versions of Qt within a `SimpleSpec`_ that specifies a range of versions.
    You can specify partial versions, inequalities, etc.
    ``"*"`` would match all versions of Qt; ``">6.0.2,<6.2.0"`` would match all
    versions of Qt between 6.0.2 and 6.2.0, etc.
    For example, ``aqt list-qt windows desktop --spec "5.12"`` would print
    all versions of Qt for Windows Desktop beginning with 5.12.
    May be combined with any other flag to filter the output of that flag.

.. _SimpleSpec: https://python-semanticversion.readthedocs.io/en/latest/reference.html#semantic_version.SimpleSpec


.. option:: --modules (<Qt version> | latest) <architecture>

    This flag lists all the modules available for Qt 5.X.Y with a host/target/architecture
    combination, or the latest version of Qt if ``latest`` is specified.
    You can list available architectures by using ``aqt list-qt`` with the
    ``--arch`` flag described below. As of Qt 6.7 this also lists extensions.

.. option:: --long-modules (<Qt version> | latest) <architecture>

    Long display for modules: Similar to ``--modules``, but shows extra metadata associated with each module.
    This metadata is displayed in a table that includes long display names for each module.
    If your terminal is wider than 95 characters, ``aqt list-qt`` will also display
    release dates and sizes for each module. An example of this output is displayed below.

.. code-block:: console

    $ python -m aqt list-qt windows desktop --long-modules latest win64_mingw
       Module Name                          Display Name                       Release Date   Download Size   Installed Size
    ========================================================================================================================
    debug_info           Desktop MinGW 13.1.0 64-bit debug information files   2024-12-12     912.6M          5.7G          
    qt3d                 Qt 3D for MinGW 13.1.0 64-bit                         2024-12-12     3.4M            26.5M         
    qt5compat            Qt 5 Compatibility Module for MinGW 13.1.0 64-bit     2024-12-12     768.6K          3.2M          
    qtactiveqt           Active Qt for MinGW 13.1.0 64-bit                     2024-12-12     6.4M            35.1M         
    qtcharts             Qt Charts for MinGW 13.1.0 64-bit                     2024-12-12     836.5K          8.7M          
    qtconnectivity       Qt Connectivity for MinGW 13.1.0 64-bit               2024-12-12     259.2K          1.8M          
    qtdatavis3d          Qt Data Visualization for MinGW 13.1.0 64-bit         2024-12-12     636.4K          5.0M          
    qtgraphs             Qt Graphs for MinGW 13.1.0 64-bit                     2024-12-12     843.2K          6.9M          
    qtgrpc               Qt Protobuf and Qt GRPC for MinGW 13.1.0 64-bit       2024-12-12     4.1M            34.7M         
    qthttpserver         Qt HTTP Server for MinGW 13.1.0 64-bit                2024-12-12     106.0K          563.2K        
    qtimageformats       Qt Image Formats for MinGW 13.1.0 64-bit              2024-12-12     427.2K          1.5M          
    qtlanguageserver     Qt language Server for MinGW 13.1.0 64-bit            2024-12-12     7.7M            56.1M         
    qtlocation           Qt Location for MinGW 13.1.0 64-bit                   2024-12-12     718.1K          5.9M          
    qtlottie             Qt Lottie Animation for MinGW 13.1.0 64-bit           2024-12-12     161.2K          951.5K        
    qtmultimedia         Qt Multimedia for MinGW 13.1.0 64-bit                 2024-12-12     18.0M           107.6M        
    qtnetworkauth        Qt Network Authorization for MinGW 13.1.0 64-bit      2024-12-12     128.4K          811.7K        
    qtpdf                MinGW 13.1.0 x64                                      2024-12-12     4.0M            11.1M         
    qtpositioning        Qt Positioning for MinGW 13.1.0 64-bit                2024-12-12     414.3K          2.8M          
    qtquick3d            Qt Quick 3D for MinGW 13.1.0 64-bit                   2024-12-12     18.0M           102.1M        
    qtquick3dphysics     Qt Quick 3D Physics for MinGW 13.1.0 64-bit           2024-12-12     35.0M           198.8M        
    qtquickeffectmaker   Qt Quick Effect Maker for MinGW 13.1.0 64-bit         2024-12-12     3.8M            5.0M          
    qtquicktimeline      Qt Quick Timeline for MinGW 13.1.0 64-bit             2024-12-12     91.7K           646.7K        
    qtremoteobjects      Qt Remote Objects for MinGW 13.1.0 64-bit             2024-12-12     486.9K          2.3M          
    qtscxml              Qt State Machine for MinGW 13.1.0 64-bit              2024-12-12     539.5K          3.6M          
    qtsensors            Qt Sensors for MinGW 13.1.0 64-bit                    2024-12-12     206.8K          2.3M          
    qtserialbus          Qt SerialBus for MinGW 13.1.0 64-bit                  2024-12-12     300.7K          1.8M          
    qtserialport         Qt SerialPort for MinGW 13.1.0 64-bit                 2024-12-12     76.3K           377.8K        
    qtshadertools        Qt Shader Tools for MinGW 13.1.0 64-bit               2024-12-12     1.5M            5.4M          
    qtspeech             Qt Speech for MinGW 13.1.0 64-bit                     2024-12-12     124.7K          686.3K        
    qtvirtualkeyboard    Qt Virtual Keyboard for MinGW 13.1.0 64-bit           2024-12-12     2.2M            7.1M          
    qtwebchannel         Qt WebChannel for MinGW 13.1.0 64-bit                 2024-12-12     139.8K          722.6K        
    qtwebsockets         Qt WebSockets for MinGW 13.1.0 64-bit                 2024-12-12     117.9K          679.9K        
    qtwebview            Qt WebView for MinGW 13.1.0 64-bit                    2024-12-12     84.8K           687.8K 


.. option:: --arch (<Qt version> | latest)

    Qt version in the format of "5.X.Y". When set, this prints all architectures
    available for Qt 5.X.Y with a host/target, or the latest version
    of Qt if ``latest`` is specified.

.. _`list archives flag`:
.. option:: --archives (<Qt version> | latest) architecture [modules...]

    This flag requires a list of at least two arguments: 'Qt version' and 'architecture'.
    The 'Qt version' argument can be in the format "5.X.Y" or the "latest" keyword.
    You can use the ``--arch`` flag to see a list of acceptable values for the 'architecture' argument.
    Any following arguments must be the names of modules available for the preceding version and architecture.
    You can use the ``--modules`` flag to see a list of acceptable values.

    If you do not add a list of modules to this flag, this command will print a
    list of all the archives that make up the base Qt installation.

    If you add a list of modules to this flag, this command will print a list
    of all the archives that make up the specified modules.

    The purpose of this command is to show you what arguments you can pass to the
    :ref:`archives flag <install archives flag>` when using the ``install-*`` commands.
    This flag allows you to avoid installing parts of Qt that you do not need.

.. option:: --latest-version

    Print only the newest version available
    May be combined with the ``--spec`` flag.

.. option:: --use-official-installer [email password]

    Use the official Qt installer instead of the AQT approach. This option simply 
    forwards your search terms to the official Qt installer. 
    Will use current OS as ``host`` (but the ``host`` value passed must still be provided and valid). 
    Will use target as research term, along with eventual arch, using the following regex: 
    ``^.*{re.escape(version_str)}\.{re.escape(target_str)}.*$``. 
    It will list all the arguments ignored. 

    If you are already signed in and have a valid ``qtaccount.ini`` for the current 
    user, you can use this option without parameters. Otherwise, you must provide 
    an email and password to authenticate.

    See :ref:`the official installer section<official>` for more details.


.. _list-src command:

list-src command
~~~~~~~~~~~~~~~~

.. program::  list-src

.. code-block:: bash

    aqt list-src [-h | --help]
                 [-c | --config]
                 <host> (<Qt version> | <spec>)

List source archives available for installation using the `install-src command`_.

.. describe:: host

    linux, linux_arm64, windows or mac

.. describe:: Qt version

    This is a Qt version such as 5.9.7, 5.12.1 etc.
    Use the :ref:`List-Qt Command` to list available versions.

.. describe:: spec

    This is a `SimpleSpec`_ that specifies a range of versions.
    If you type something in the ``<Qt version>`` positional argument that
    cannot be interpreted as a version, it will be interpreted as a `SimpleSpec`_,
    and ``aqt`` will select the highest available version within that `SimpleSpec`_.

    For example, ``aqt list-src mac 5.12`` would print archives for the
    latest version of Qt 5.12 available (5.12.11 at the time of this writing).


.. _list-doc command:

list-doc command
~~~~~~~~~~~~~~~~

.. program::  list-doc

.. code-block:: bash

    aqt list-doc [-h | --help]
                 [-c | --config]
                 [-m | --modules]
                 <host> (<Qt version> | <spec>)

List documentation archives and modules available for installation using the
`install-doc command`_.

By default, ``list-doc`` will print a list of archives available for
installation using the `install-doc command`_, with the ``--archives`` option.

.. describe:: host

    linux, linux_arm64, windows or mac

.. describe:: Qt version

    This is a Qt version such as 5.9.7, 5.12.1 etc.
    Use the :ref:`List-Qt Command` to list available versions.

.. describe:: spec

    This is a `SimpleSpec`_ that specifies a range of versions.
    If you type something in the ``<Qt version>`` positional argument that
    cannot be interpreted as a version, it will be interpreted as a `SimpleSpec`_,
    and ``aqt`` will select the highest available version within that `SimpleSpec`_.

    For example, ``aqt list-doc mac 5.12`` would print archives for the
    latest version of Qt 5.12 available (5.12.11 at the time of this writing).

.. option:: --modules

    This flag causes ``list-doc`` to print a list of modules available for
    installation using the `install-doc command`_, with the ``--modules`` option.


.. _list-example command:

list-example command
~~~~~~~~~~~~~~~~~~~~

.. program::  list-example

.. code-block:: bash

    aqt list-example [-h | --help]
                     [-c | --config]
                     [-m | --modules]
                     <host> (<Qt version> | <spec>)

List example archives and modules available for installation using the
`install-example command`_.

By default, ``list-example`` will print a list of archives available for
installation using the `install-example command`_, with the ``--archives`` option.

.. describe:: host

    linux, linux_arm64, windows or mac

.. describe:: Qt version

    This is a Qt version such as 5.9.7, 5.12.1 etc.
    Use the :ref:`List-Qt Command` to list available versions.

.. describe:: spec

    This is a `SimpleSpec`_ that specifies a range of versions.
    If you type something in the ``<Qt version>`` positional argument that
    cannot be interpreted as a version, it will be interpreted as a `SimpleSpec`_,
    and ``aqt`` will select the highest available version within that `SimpleSpec`_.

    For example, ``aqt list-example mac 5.12`` would print archives for the
    latest version of Qt 5.12 available (5.12.11 at the time of this writing).

.. option:: --modules

    This flag causes ``list-example`` to print a list of modules available for
    installation using the `install-example command`_, with the ``--modules`` option.


.. _list-tool command:

list-tool command
~~~~~~~~~~~~~~~~~

.. program::  list-tool

.. code-block:: bash

    aqt list-tool [-h | --help] [-c | --config] [-l | --long] <host> [<target>] [<tool name>]

List available tools

.. describe:: host

    linux, linux_arm64, windows or mac

.. describe:: target

    desktop, winrt, ios or android.
    When omitted, the command prints all the targets available for a host OS.
    Note that winrt is only available on Windows, and ios is only available on Mac OS.

.. describe:: tool name

    The name of a tool. Use ``aqt list-tool <host> <target>`` to see accepted values.
    When set, this prints all 'tool variant names' available.

    The output of this command is meant to be used with the
    :ref:`aqt install-tool <Tools installation command>` below.

.. option:: --help, -h

    Display help text


.. option:: --long, -l

    Long display: shows extra metadata associated with each tool variant.
    This metadata is displayed in a table, and includes versions and release dates
    for each tool. If your terminal is wider than 95 characters, ``aqt list-tool``
    will also display the names and descriptions for each tool. An example of this
    output is displayed below.

.. code-block:: console

    $ python -m aqt list-tool windows desktop tools_conan -l

     Tool Variant Name           Version         Release Date     Display Name              Description
    ============================================================================================================
    qt.tools.conan         1.33-202102101246     2021-02-10     Conan 1.33          Conan command line tool 1.33
    qt.tools.conan.cmake   0.16.0-202102101246   2021-02-10     Conan conan.cmake   Conan conan.cmake (0.16.0)


Install-* Commands
------------------

These commands are used to install Qt, tools, source, docs, and examples.


.. _common options:

Common Options
~~~~~~~~~~~~~~

Most of these commands share the same command line options, and these options
are described here:


.. option:: --help, -h

    Display help text

.. option:: --outputdir, -O <Output Directory>

    Specify output directory.
    By default, aqt installs to the current working directory.

.. option:: --base, -b <base url>

    Specify mirror site base url such as  -b ``https://mirrors.dotsrc.org/qtproject``
    where 'online' folder exist.
    
.. option:: --config, -c <settings_file_path>

    Specify the path to your own ``settings.ini`` file. See :ref:`the Configuration section<configuration-ref>`.

.. option:: --timeout <timeout(sec)>

    The connection timeout, in seconds, for the download site. (default: 5 sec)

.. option:: --external, -E <7zip command>

    Specify external 7zip command path. By default, aqt uses py7zr_ for this task.

    In the past, our users have had success using 7-zip_ on Windows, Linux and Mac.
    You can install 7-zip on Windows with Choco_.
    The Linux/Mac port of 7-zip is called ``p7zip``, and you can install it with brew_ on Mac,
    or on Linux with your package manager.

.. _py7zr: https://pypi.org/project/py7zr/
.. _7-zip: https://www.7-zip.org/
.. _Choco: https://community.chocolatey.org/packages/7zip/
.. _brew: https://formulae.brew.sh/formula/p7zip

.. option:: --internal

    Use the internal extractor, py7zr_

.. option:: --keep, -k

    Keep downloaded archive when specified, otherwise remove after install.
    Use ``--archive-dest <path>`` to choose where aqt will place these files.
    If you do not specify a download destination, aqt will place these files in
    the current working directory.

.. option:: --archive-dest <path>

    Set the destination path for downloaded archives (temp directory by default).
    All downloaded archives will be automatically deleted unless you have
    specified the ``--keep`` option above, or ``aqt`` crashes.

    Note that this option refers to the intermediate ``.7z`` archives that ``aqt``
    downloads and then extracts to ``--outputdir``.
    Most users will not need to keep these files.

.. option:: --modules, -m (<list of modules> | all)

    Specify extra modules to install as a list.
    Use the appropriate ``aqt list-*`` command to list available modules:

+------------------+-------------------------+--------------------------------------------------------+
| Install command  | List command            | Usage of list command                                  |
+==================+=========================+========================================================+
| install-qt       | `list-qt command`_      | ``list-qt <host> <target> --modules <version> <arch>`` |
+------------------+-------------------------+--------------------------------------------------------+
| install-example  | `list-example command`_ | ``list-example <host> <version> --modules``            |
+------------------+-------------------------+--------------------------------------------------------+
| install-doc      | `list-doc command`_     | ``list-doc <host> <version> --modules``                |
+------------------+-------------------------+--------------------------------------------------------+


    This option only applicable to ``install-qt``, ``install-example``, and ``install-doc``.

    You can install multiple modules like this:

    .. code-block:: console

        $ aqt install-* <host> <target> <Qt version> -m qtcharts qtdatavis3d qtlottie qtnetworkauth \
            qtpurchasing qtquicktimeline qtscript qtvirtualkeyboard qtwebglplugin


    If you wish to install every module available, you may use the ``all`` keyword
    instead of a list of modules, like this:

    .. code-block:: bash

        aqt install-* <host> <target> <Qt version> <arch> -m all

.. option:: --UNSAFE-ignore-hash

    UNSAFE, use at your own risk.
    This disables the hash check of downloaded files from your mirror against the official hashes.
    Equivalent to setting ``INSECURE_NOT_FOR_PRODUCTION_ignore_hash: True`` in ``aqt/settings.ini``.
    It does not edit the configuration file and only affects the current session. It will print warnings.
    Useful if the Qt official mirror is down and you trust a third-party mirror.


.. _install archives flag:
.. option:: --archives <list of archives>

    [Advanced] Specify subset of archives to **limit** installed archives.
    It will only affect the base Qt installation and the ``debug_info`` module.
    This is advanced option and not recommended to use for general usage.
    Main purpose is speed up CI/CD process by limiting installed modules.
    It can cause broken installation of Qt SDK.

    This option is applicable to all the ``install-*`` commands except for ``install-tool``.

    You can print a list of all acceptable values to use with this command by
    using the appropriate ``aqt list-*`` command:

+------------------+-------------------------+--------------------------------------------------+
| Install command  | List command            | Usage of list command                            |
+==================+=========================+==================================================+
| install-qt       | `list-qt command`_      | ``list-qt <host> <target> --archives <version>`` |
+------------------+-------------------------+--------------------------------------------------+
| install-example  | `list-example command`_ | ``list-example <host> <version>``                |
+------------------+-------------------------+--------------------------------------------------+
| install-src      | `list-src command`_     | ``list-src <host> <version>``                    |
+------------------+-------------------------+--------------------------------------------------+
| install-doc      | `list-doc command`_     | ``list-doc <host> <version>``                    |
+------------------+-------------------------+--------------------------------------------------+


.. _qt installation command:

install-qt command
~~~~~~~~~~~~~~~~~~

.. program:: install-qt

.. code-block:: bash

    aqt install-qt
        [-h | --help]
        [-c | --config]
        [-O | --outputdir <directory>]
        [-b | --base <mirror url>]
        [--timeout <timeout(sec)>]
        [-E | --external <7zip command>]
        [--internal]
        [-k | --keep]
        [-d | --archive-dest] <path>
        [-m | --modules (all | <module> [<module>...])]
        [--archives <archive> [<archive>...]]
        [--autodesktop]
        [--noarchives]
        [--dry-run]
        [--use-official-installer [<email> <password>]]
        <host> <target> (<Qt version> | <spec>) [<arch>]

Install Qt library, with specified version and target.
There are various combinations to accept according to Qt version.

.. describe:: host

    linux, linux_arm64, windows, windows_arm64, all_os, or mac. The operating system on which the Qt development tools will run.

.. describe:: target

    desktop, ios, winrt, android, or wasm. The type of device for which you are developing Qt programs.
    If your target is ios, please be aware that versions of Qt older than 6.2.4 are expected to be
    non-functional with current versions of XCode (applies to any XCode greater than or equal to 13).

.. describe:: Qt version

    This is a Qt version such as 5.9.7, 5.12.1 etc.
    Use the :ref:`List-Qt Command` to list available versions.

.. describe:: spec

    This is a `SimpleSpec`_ that specifies a range of versions.
    If you type something in the ``<Qt version>`` positional argument that
    cannot be interpreted as a version, it will be interpreted as a `SimpleSpec`_,
    and ``aqt`` will select the highest available version within that `SimpleSpec`_.

    For example, ``aqt install-qt mac desktop 5.12`` would install the newest
    version of Qt 5.12 available, and ``aqt install-qt mac desktop "*"`` would
    install the highest version of Qt available.

    When using this option, ``aqt`` will print the version that it has installed
    in the logs so that you can verify it easily.

.. describe:: arch

   The compiler architecture for which you are developing. Options:

   * gcc_64 or linux_gcc_64 for linux desktop

   * linux_gcc_arm64 for linux_arm64 desktop

   * clang_64 for mac desktop

   * win64_msvc2022_64, win64_mingw, win64_llvm_mingw, win64_msvc2019_64, win64_msvc2019_arm64, win64_msvc2017_64, win64_msvc2015_64, win32_msvc2015, win32_mingw53 for windows desktop

   * win64_msvc2022_arm64 for windows_arm64 desktop

   * android_armv7, android_arm64_v8a, android_x86, android_x86_64 for android

   * wasm_singlethread or wasm_multithread for wasm

    Use the :ref:`List-Qt Command` to list available architectures.

.. option:: --autodesktop

    If you are installing an ios, android, WASM, or msvc_arm64 version of Qt6,
    the corresponding desktop version of Qt must be installed alongside of it.
    Turn this option on to install it automatically.
    This option will have no effect if the desktop version of Qt is not required.

.. option:: --noarchives

    [Advanced] Specify not to install all base packages.
    This is advanced option and you should use it with ``--modules`` option.
    This allow you to add modules to existent Qt installation.

.. option:: --dry-run

    Perform a simulation of the installation process without making any changes. 

.. option:: --use-official-installer [email password]

    Use the official Qt installer instead of the AQT approach. This option ignores 
    the ``--host`` parameter and forces installation for the current OS due to Qt 
    restrictions. 

    If you are already signed in and have a valid ``qtaccount.ini`` for the current 
    user, you can use this option without parameters. Otherwise, you must provide 
    an email and password to authenticate.

    See :ref:`the official installer section<official>` for more details.

See `common options`_.


.. _install-src command:

install-src command
~~~~~~~~~~~~~~~~~~~

.. program::  install-src

.. code-block:: bash

    aqt install-src
        [-h | --help]
        [-c | --config]
        [-O | --outputdir <directory>]
        [-b | --base <mirror url>]
        [--timeout <timeout(sec)>]
        [-E | --external <7zip command>]
        [--internal]
        [-k | --keep]
        [-d | --archive-dest] <path>
        [--archives <archive> [<archive>...]]
        [--kde]
        <host> [<target>] (<Qt version> | <spec>)

Install Qt source code for the specified version and target.


.. describe:: host

    linux, linux_arm64, windows or mac

.. describe:: target

    Deprecated and marked for removal in a future version of aqt.
    This parameter exists for backwards compatibility reasons, and its value is ignored.

.. describe:: Qt version

    This is a Qt version such as 5.9.7, 5.12.1 etc.
    Use the :ref:`List-Qt Command` to list available versions.

.. describe:: spec

    This is a `SimpleSpec`_ that specifies a range of versions.
    If you type something in the ``<Qt version>`` positional argument that
    cannot be interpreted as a version, it will be interpreted as a `SimpleSpec`_,
    and ``aqt`` will select the highest available version within that `SimpleSpec`_.

    For example, ``aqt install-src mac 5.12`` would install sources for the newest
    version of Qt 5.12 available, and ``aqt install-src mac "*"`` would
    install sources for the highest version of Qt available.

.. option:: --kde

    by adding ``--kde`` option,
    KDE patch collection is applied for qtbase tree. It is only applied to
    Qt 5.15.2. When specified version is other than it, command will abort
    with error when using ``--kde``.

See `common options`_.


.. _install-doc command:

install-doc command
~~~~~~~~~~~~~~~~~~~

.. program:: install-doc

.. code-block:: bash

    aqt install-doc
        [-h | --help]
        [-c | --config]
        [-O | --outputdir <directory>]
        [-b | --base <mirror url>]
        [--timeout <timeout(sec)>]
        [-E | --external <7zip command>]
        [--internal]
        [-k | --keep]
        [-d | --archive-dest] <path>
        [-m | --modules (all | <module> [<module>...])]
        [--archives <archive> [<archive>...]]
        <host> [<target>] (<Qt version> | <spec>)

Install Qt documentation for the specified version and target.

.. describe:: host

    linux, linux_arm64, windows or mac

.. describe:: target

    Deprecated and marked for removal in a future version of aqt.
    This parameter exists for backwards compatibility reasons, and its value is ignored.

.. describe:: Qt version

    This is a Qt version such as 5.9.7, 5.12.1 etc.
    Use the :ref:`List-Qt Command` to list available versions.

.. describe:: spec

    This is a `SimpleSpec`_ that specifies a range of versions.
    If you type something in the ``<Qt version>`` positional argument that
    cannot be interpreted as a version, it will be interpreted as a `SimpleSpec`_,
    and ``aqt`` will select the highest available version within that `SimpleSpec`_.

    For example, ``aqt install-doc mac 5.12`` would install documentation for the newest
    version of Qt 5.12 available, and ``aqt install-doc mac "*"`` would
    install documentation for the highest version of Qt available.

See `common options`_.


.. _install-example command:

install-example command
~~~~~~~~~~~~~~~~~~~~~~~

.. program:: install-example

.. code-block:: bash

    aqt install-example
        [-h | --help]
        [-c | --config]
        [-O | --outputdir <directory>]
        [-b | --base <mirror url>]
        [--timeout <timeout(sec)>]
        [-E | --external <7zip command>]
        [--internal]
        [-k | --keep]
        [-d | --archive-dest] <path>
        [-m | --modules (all | <module> [<module>...])]
        [--archives <archive> [<archive>...]]
        <host> [<target>] (<Qt version> | <spec>)

Install Qt examples for the specified version and target.


.. describe:: host

    linux, linux_arm64, windows or mac

.. describe:: target

    Deprecated and marked for removal in a future version of aqt.
    This parameter exists for backwards compatibility reasons, and its value is ignored.

.. describe:: Qt version

    This is a Qt version such as 5.9.7, 5.12.1 etc.
    Use the :ref:`List-Qt Command` to list available versions.

.. describe:: spec

    This is a `SimpleSpec`_ that specifies a range of versions.
    If you type something in the ``<Qt version>`` positional argument that
    cannot be interpreted as a version, it will be interpreted as a `SimpleSpec`_,
    and ``aqt`` will select the highest available version within that `SimpleSpec`_.

    For example, ``aqt install-example mac 5.12`` would install examples for the newest
    version of Qt 5.12 available, and ``aqt install-example mac "*"`` would
    install examples for the highest version of Qt available.


See `common options`_.


.. _tools installation command:

install-tool command
~~~~~~~~~~~~~~~~~~~~

.. program::  install-tool

.. code-block:: bash

    aqt install-tool
        [-h | --help]
        [-c | --config]
        [-O | --outputdir <directory>]
        [-b | --base <mirror url>]
        [--timeout <timeout(sec)>]
        [-E | --external <7zip command>]
        [--internal]
        [-k | --keep]
        [-d | --archive-dest] <path>
        <host> <target> <tool name> [<tool variant name>]

Install tools like QtIFW, mingw, Cmake, Conan, and vcredist.

.. describe:: host

    linux, linux_arm64, windows or mac

.. describe:: target

    desktop, ios or android

.. describe:: tool name

    install tools specified. tool name may be 'tools_openssl_x64', 'tools_vcredist', 'tools_ninja',
    'tools_ifw', 'tools_cmake'

.. option:: tool variant name

    Optional field to specify tool variant. It may be required for vcredist and mingw installation.
    tool variant names may be 'qt.tools.win64_mingw810', 'qt.tools.vcredist_msvc2013_x64'.

You should use the :ref:`List-Tool command` to display what tools and tool variant names are available.
    

See `common options`_.

Command examples
================

.. program:: None

Example: Installing Qt SDK 5.12.12 for Linux with QtCharts and QtNetworkAuth:

.. code-block:: console

    pip install aqtinstall
    sudo aqt install-qt --outputdir /opt linux desktop 5.12.12 -m qtcharts qtnetworkauth


Example: Installing the newest LTS version of Qt 5.12:

.. code-block:: console

    pip install aqtinstall
    sudo aqt install-qt linux desktop 5.12 gcc_64

Example: Installing the newest LTS version of Qt 6.7 for linux arm64:

.. code-block:: console

    pip install aqtinstall
    sudo aqt install-qt linux_arm64 desktop 6.7

Example: Installing Android (armv7) Qt 5.13.2:

.. code-block:: console

    aqt install-qt linux android 5.13.2 android_armv7


Example: Installing Android (armv7) Qt 6.4.2:

.. code-block:: console

    aqt install-qt linux android 6.4.2 android_armv7 --autodesktop


Example: Install examples, doc and source:

.. code-block:: console

    aqt install-example windows 5.15.2 -m qtcharts qtnetworkauth
    aqt install-doc windows 5.15.2 -m qtcharts qtnetworkauth
    aqt install-src windows 5.15.2 --archives qtbase --kde

Example: Print archives available for installation with ``install-example/doc/src``:

.. code-block:: console

    aqt list-example windows 5.15.2
    aqt list-doc windows 5.15.2
    aqt list-src windows 5.15.2

Example: Print modules available for installation with ``install-example/doc``:

.. code-block:: console

    aqt list-example windows 5.15.2 --modules
    aqt list-doc windows 5.15.2 --modules

Example: Install Web Assembly for Qt5

.. code-block:: console

    aqt install-qt linux desktop 5.15.0 wasm_32


Example: Install different versions of Qt6 for Web Assembly (WASM)

.. code-block:: console

    aqt install-qt linux desktop 6.2.4 wasm_32 --autodesktop
    aqt install-qt linux desktop 6.5.0 wasm_singlethread --autodesktop
    aqt install-qt all_os wasm 6.8.0 wasm_multithread --autodesktop


Example: Install commercial version 6.5.5 of Qt6 on Windows

.. code-block:: console

    aqt install-qt windows desktop 6.5.5 win64_msvc2019_64 --use-official-installer 'email@gmail.com' 'password'


Example: List commercial packages of Android for version 6.8.3 of Qt6 on current OS

.. code-block:: console

    aqt list-qt linux android --arch 6.8.3 --use-official-installer 'email@gmail.com' 'password'


Example: List available versions of Qt on Linux

.. code-block:: console

    aqt list-qt linux desktop


Example: List available versions of Qt6 on macOS

.. code-block:: console

    aqt list-qt mac desktop --spec "6"


Example: List available modules for latest version of Qt on macOS

.. code-block:: console

    aqt list-qt mac desktop --modules latest clang_64   # prints 'qtquick3d qtshadertools', etc


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

.. code-block:: console

    aqt list-tool linux desktop tools_ifw -l    # prints a table of metadata


Example: Install an Install FrameWork (IFW):

.. code-block:: console

    aqt install-tool linux desktop tools_ifw


Example: Install vcredist on Windows:

.. code-block:: doscon


    aqt install-tool windows desktop tools_vcredist
    .\Qt\Tools\vcredist\vcredist_msvc2019_x64.exe /norestart /q


Example: Install MinGW 8.1.0 on Windows:

.. code-block:: doscon

    aqt install-tool -O c:\Qt windows desktop tools_mingw qt.tools.win64_mingw810
    set PATH=C:\Qt\Tools\mingw810_64\bin


Example: Install MinGW 11.2.0 on Windows:

.. code-block:: doscon

    aqt install-tool -O c:\Qt windows desktop tools_mingw90
    set PATH=C:\Qt\Tools\mingw1120_64\bin

.. note::

    This is not a typo; it is a mislabelled tool name!
    ``tools_mingw90`` and the tool variant ``qt.tools.win64_mingw900``
    do not contain MinGW 9.0.0; they actually contain MinGW 11.2.0!
    Verify with ``aqt list-tool --long windows desktop tools_mingw90``
    in a wide terminal.


Example: Show help message

.. code-block:: console

    aqt help

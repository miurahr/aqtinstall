.. _getting_started:

Getting Started
===============

``aqt`` is a tool that can be used to install Qt, modules, tools related to Qt,
source, docs, and examples, available at https://download.qt.io/.
Before running ``aqt``, you will need to tell ``aqt`` exactly what you want it
to install. This section of the documentation is meant to walk you through the
process of finding out what packages are available to ``aqt``, so you can tell
``aqt`` what you want to install.

Please note that every ``aqt`` subcommand has a ``--help`` option; please use
it if you are having trouble!


Installing Qt
-------------

General usage of ``aqt`` looks like this:

.. code-block:: bash

    aqt install-qt <host> <target> (<Qt version> | <spec>) [<arch>]

If you have installed ``aqt`` with pip, you can run it with the command script ``aqt``,
but in some cases you may need to run it as ``python -m aqt``.
Some older operating systems may require you to specify Python version 3, like this: ``python3 -m aqt``.

To use ``aqt`` to install Qt, you will need to tell ``aqt`` four things:

1. The host operating system (windows, mac, or linux)
2. The target SDK (desktop, android, ios, or winrt)
3. The version of Qt you would like to install
4. The target architecture

Keep in mind that Qt for IOS is only available on Mac OS, and Qt for WinRT is
only available on Windows.

To find out what versions of Qt are available, you can use the :ref:`aqt list-qt command <list-qt command>`.
This command will print all versions of Qt available for Windows Desktop:

.. code-block:: console

    $ aqt list-qt windows desktop
    5.9.0 5.9.1 5.9.2 5.9.3 5.9.4 5.9.5 5.9.6 5.9.7 5.9.8 5.9.9
    5.10.0 5.10.1
    5.11.0 5.11.1 5.11.2 5.11.3
    5.12.0 5.12.1 5.12.2 5.12.3 5.12.4 5.12.5 5.12.6 5.12.7 5.12.8 5.12.9 5.12.10 5.12.11
    5.13.0 5.13.1 5.13.2
    5.14.0 5.14.1 5.14.2
    5.15.0 5.15.1 5.15.2
    6.0.0 6.0.1 6.0.2 6.0.3 6.0.4
    6.1.0 6.1.1 6.1.2
    6.2.0

Notice that the version numbers are sorted, grouped by minor version number,
and separated by a single space-character. The output of all of the 
:ref:`aqt list-qt <list-qt command>` commands is intended to make it easier for you to write programs
that consume the output of :ref:`aqt list-qt <list-qt command>`.

Because the :ref:`aqt list-qt <list-qt command>` command directly queries the Qt downloads repository
at https://download.qt.io/, the results of this command will always be accurate.
The `Available Qt versions`_ wiki page was last modified at some point in the past,
so it may or may not be up to date.

.. _Available Qt versions: https://github.com/miurahr/aqtinstall/wiki/Available-Qt-versions

Now that we know what versions of Qt are available, let's choose version 6.2.0.

The next thing we need to do is find out what architectures are available for
Qt 6.2.0 for Windows Desktop. To do this, we can use :ref:`aqt list-qt <list-qt command>` with the
``--arch`` flag:

.. code-block:: console

    $ aqt list-qt windows desktop --arch 6.2.0
    win64_mingw81 win64_msvc2019_64 win64_msvc2019_arm64 wasm_32

Notice that this is a very small subset of the architectures listed in the 
`Available Qt versions`_ wiki page. If we need to use some architecture that
is not on this list, we can use the `Available Qt versions`_ wiki page to get
a rough idea of what versions support the architecture we want, and then use
:ref:`aqt list-qt <list-qt command>` to confirm that the architecture is available.

Let's say that we want to install Qt 6.2.0 with architecture `win64_mingw81`.
The installation command we need is:

.. code-block:: console

    $ aqt install-qt windows desktop 6.2.0 win64_mingw81

Let's say that we want to install the next version of Qt 6.2 as soon as it is available.
We can do this by using a
`SimpleSpec <https://python-semanticversion.readthedocs.io/en/latest/reference.html#semantic_version.SimpleSpec>`_
instead of an explicit version:

.. code-block:: console

    $ aqt install-qt windows desktop 6.2 win64_mingw81


External 7-zip extractor
------------------------

By default, ``aqt`` extracts the 7zip archives stored in the Qt repository using
py7zr_, which is installed alongside ``aqt``. You can specify an alternate 7zip
command path instead by using the ``-E`` or ``--external`` flag. For example,
you could use 7-zip_ on a Windows desktop, using this command:

.. code-block:: doscon

    C:\> aqt install-qt windows desktop 6.2.0 gcc_64 --external 7za.exe

On Linux, you can specify p7zip_, a Linux port of 7-zip_, which is often
installed by default, using this command:

.. code-block:: console

    $ aqt install-qt linux desktop 6.2.0 gcc_64 --external 7z

.. _py7zr: https://pypi.org/project/py7zr/
.. _p7zip: http://p7zip.sourceforge.net/
.. _7-zip: https://www.7-zip.org/

Changing the output directory
-----------------------------

By default, ``aqt`` will install all of the Qt packages into the current
working directory, in the subdirectory ``./<Qt version>/<arch>/``.
For example, if we install Qt 6.2.0 for Windows desktop with arch `win64_mingw81`,
it would end up in ``./6.2.0/win64_mingw81``.

If you would prefer to install it to another location, you
will need to use the ``-O`` or ``--outputdir`` flag.
This option also works for all of the other subcommands that begin with
``aqt install-``.

To install to ``C:\Qt``, the default directory used by the standard gui installer,
you may use this command:

.. code-block:: doscon

    C:\> mkdir Qt
    C:\> aqt install-qt --outputdir c:\Qt windows desktop 6.2.0 win64_mingw81


Installing Modules
------------------

Let's say we need to install some modules for Qt 5.15.2 on Windows Desktop.
First we need to find out what the modules are called, and we can do that 
with :ref:`aqt list-qt <list-qt command>` with the ``--modules`` flag.
Each version of Qt has a different list of modules for each host OS/ target SDK/ architecture
combination, so we will need to supply :ref:`aqt list-qt <list-qt command>` with that information:

.. code-block:: console

    $ aqt list-qt windows desktop --modules 5.15.2 win64_mingw81
    qtcharts qtdatavis3d qtlottie qtnetworkauth qtpurchasing qtquick3d
    qtquicktimeline qtscript qtvirtualkeyboard qtwebengine qtwebglplugin

Let's say that we want to know more about these modules before we install them.
We can use the ``--long-modules`` flag for that:

.. code-block:: console

    $ aqt list-qt windows desktop --long-modules 5.15.2 win64_mingw81
       Module Name                         Display Name
    ======================================================================
    debug_info          Desktop MinGW 8.1.0 64-bit Debug Information Files
    qtcharts            Qt Charts for MinGW 8.1.0 64-bit
    qtdatavis3d         Qt Data Visualization for MinGW 8.1.0 64-bit
    qtlottie            Qt Lottie Animation for MinGW 8.1.0 64-bit
    qtnetworkauth       Qt Network Authorization for MinGW 8.1.0 64-bit
    qtpurchasing        Qt Purchasing for MinGW 8.1.0 64-bit
    qtquick3d           Qt Quick 3D for MinGW 8.1.0 64-bit
    qtquicktimeline     Qt Quick Timeline for MinGW 8.1.0 64-bit
    qtscript            Qt Script for MinGW 8.1.0 64-bit
    qtvirtualkeyboard   Qt Virtual Keyboard for MinGW 8.1.0 64-bit
    qtwebglplugin       Qt WebGL Streaming Plugin for MinGW 8.1.0 64-bit

Note that if your terminal is wider than 95 characters, this command will show
release dates and sizes in extra columns to the right.
If you try this, you will notice that `debug_info` is 5.9 gigabytes installed.

Let's say that we want to install `qtcharts` and `qtnetworkauth`. 
We can do that by using the `-m` flag with the :ref:`aqt install-qt <qt installation command>` command.
This flag receives the name of at least one module as an argument:

.. code-block:: console

    $ aqt install-qt windows desktop 5.15.2 win64_mingw81 -m qtcharts qtnetworkauth

If we wish to install all the modules that are available, we can do that with the ``all`` keyword:

.. code-block:: console

    $ aqt install-qt windows desktop 5.15.2 win64_mingw81 -m all

Remember that the :ref:`aqt list-qt <list-qt command>` command is meant to be scriptable?
One way to install all modules available for Qt 5.15.2 is to send the output of
:ref:`aqt list-qt <list-qt command>` into :ref:`aqt install-qt <qt installation command>`, like this:

.. code-block:: console

    $ aqt install-qt windows desktop 5.15.2 win64_mingw81 \
          -m $(aqt list-qt windows desktop --modules 5.15.2 win64_mingw81)

You will need a Unix-style shell to run this command, or at least git-bash on Windows.
The ``xargs`` equivalent to this command is an exercise left to the reader.

If you want to install all available modules, you are probably better off using
the ``all`` keyword, as discussed above. This scripting example is presented to
give you a sense of how to accomplish something more complicated.
Perhaps you want to install all modules except `qtnetworkauth`; you could write a script
that removes `qtnetworkauth` from the output of :ref:`aqt list-qt <list-qt command>`,
and pipe that into :ref:`aqt install-qt <qt installation command>`.
This exercise is left to the reader.


Installing Qt for Android
-------------------------

Let's install Qt for Android. This will be similar to installing Qt for Desktop on Windows.

.. note::

    Versions of aqtinstall older than 3.1.0 required the use of the ``--extensions`` and
    ``--extension`` flag to list any architectures, modules, or archives for Qt 6 and above.
    These flags are no longer necessary, so please do not use them.

.. code-block:: console

    $ aqt list-qt windows android                           # Print Qt versions available
    5.9.0 5.9.1 ...
    ...
    6.4.0

    $ aqt list-qt windows android --arch 6.2.4              # Print architectures available
    android_x86_64 android_armv7 android_x86 android_arm64_v8a

    $ aqt list-qt windows android --modules 6.2.4 android_armv7   # Print modules available
    qt3d qt5compat qtcharts qtconnectivity qtdatavis3d ...

    $ aqt install-qt windows android 6.2.4 android_armv7 -m qtcharts qtnetworkauth   # Install

Please note that when you install Qt for android or ios, the installation will not
be functional unless you install the corresponding desktop version of Qt alongside it.
You can do this automatically with the ``--autodesktop`` flag:

.. code-block:: console

    $ aqt install-qt linux android 6.2.4 android_armv7 -m qtcharts qtnetworkauth --autodesktop

Installing Qt for WASM
----------------------

To find out how to install Qt for WASM, we will need to use the ``wasm_32`` architecture.
We can find out whether or not that architecture is available for our version of Qt with the
``--arch`` flag.

.. code-block:: console

    $ python -m aqt list-qt windows desktop --arch 6.1.3
    win64_mingw81 win64_msvc2019_64
    $ python -m aqt list-qt windows desktop --arch 6.2.0
    win64_mingw81 win64_msvc2019_64 win64_msvc2019_arm64 wasm_32

Not every version of Qt supports WASM. This command shows us that we cannot use WASM with Qt 6.1.3.

Please note that the WASM architecture for Qt 6.5.0+ changed from ``wasm_32`` to ``wasm_singlethread`` and
``wasm_multithread``. Always use ``aqt list-qt`` to check what architectures are available for the desired version of Qt.

We can check the modules available as before:

.. code-block:: console

    $ aqt list-qt windows desktop --modules 5.15.2 wasm_32   # available modules
    qtcharts qtdatavis3d qtlottie qtnetworkauth qtpurchasing qtquicktimeline qtscript
    qtvirtualkeyboard qtwebglplugin

We can install Qt for WASM as before:

.. code-block:: console

    $ aqt install-qt windows desktop 5.15.2 wasm_32 -m qtcharts qtnetworkauth

Please note that when you install Qt for WASM version 6 and above, the installation will not
be functional unless you install a non-WASM desktop version of Qt alongside it.
You can do this automatically with the ``--autodesktop`` flag:

.. code-block:: console

    $ aqt install-qt linux desktop 6.2.0 wasm_32 -m qtcharts qtnetworkauth --autodesktop


Installing Tools
----------------

Let's find out what tools are available for Windows Desktop by using the
:ref:`aqt list-tool <list-tool command>` command:

.. code-block:: console

    $ aqt list-tool windows desktop
    tools_vcredist
    ...
    tools_qtcreator
    tools_qt3dstudio
    tools_openssl_x86
    tools_openssl_x64
    tools_openssl_src
    tools_ninja
    tools_mingw
    tools_ifw
    tools_conan
    tools_cmake

Let's see what tool variants are available in `tools_mingw`:

.. code-block:: console

    $ aqt list-tool windows desktop tools_mingw
    qt.tools.mingw47
    qt.tools.win32_mingw48
    qt.tools.win32_mingw482
    qt.tools.win32_mingw491
    qt.tools.win32_mingw492
    qt.tools.win32_mingw530
    qt.tools.win32_mingw730
    qt.tools.win32_mingw810
    qt.tools.win64_mingw730
    qt.tools.win64_mingw810

This gives us a list of things that we could install using
:ref:`aqt install-tool <tools installation command>`.
Let's see some more details, using the ``-l`` or ``--long`` flag:

.. code-block:: console

    $ aqt list-tool windows desktop tools_mingw -l

       Tool Variant Name            Version          Release Date
    =============================================================
    qt.tools.mingw47          4.7.2-1-1              2013-07-01
    qt.tools.win32_mingw48    4.8.0-1-1              2013-07-01
    qt.tools.win32_mingw482   4.8.2                  2014-05-08
    qt.tools.win32_mingw491   4.9.1-3                2016-05-31
    qt.tools.win32_mingw492   4.9.2-1                2016-05-31
    qt.tools.win32_mingw530   5.3.0-2                2017-04-27
    qt.tools.win32_mingw730   7.3.0-1-202004170606   2020-04-17
    qt.tools.win32_mingw810   8.1.0-1-202004170606   2020-04-17
    qt.tools.win64_mingw730   7.3.0-1-202004170606   2020-04-17
    qt.tools.win64_mingw810   8.1.0-1-202004170606   2020-04-17

The ``-l`` flag causes :ref:`aqt list-tool <list-tool command>` to print a table
that shows plenty of data pertinent to each tool variant available in `tools_mingw`.
:ref:`aqt list-tool <list-tool command>` additionally prints the 'Display Name'
and 'Description' for each tool if your terminal is wider than 95 characters;
terminals that are narrower than this cannot display this table in a readable way.

Now let's install `mingw`, using the :ref:`aqt install-tool <tools installation command>` command.
This command receives four parameters:

1. The host operating system (windows, mac, or linux)
2. The target SDK (desktop, android, ios, or winrt)
3. The name of the tool (this is `tools_mingw` in our case)
4. (Optional) The tool variant name. We saw a list of these when we ran
   :ref:`aqt list-tool <list-tool command>` with the `tool name` argument filled in.

To install `mingw`, you could use this command (please don't):

.. code-block:: console

    $ aqt install-tool windows desktop tools_mingw    # please don't run this!

Using this command will install every tool variant available in `tools_mingw`;
in this case, you would install 10 different versions of the same tool.
For some tools, like `qtcreator` or `ifw`, this is an appropriate thing to do,
since each tool variant is a different program.
However, for tools like `mingw` and `vcredist`, it would make more sense to use
:ref:`aqt list-tool <list-tool command>` to see what tool variants are available,
and then install just the tool variant you are interested in, like this:

.. code-block:: console

    $ aqt install-tool windows desktop tools_mingw qt.tools.win64_mingw730


Please note that ``aqt install-tool`` does not recognize the ``installscript.qs``
related to each tool. When you install these tools with the standard gui installer,
the installer may use the ``installscript.qs`` script to make additional changes
to your system. If you need those changes to occur, it will be your responsibility
to make those changes happen, because ``aqt`` is not capable of running this script.


Installing a subset of Qt archives [Advanced]
---------------------------------------------

Introduction
````````````

You may have noticed that by default, ``aqt install-qt`` installs a lot of
archives that you may or may not need, and a typical installation can take up
more disk space than necessary. If you installed the module ``debug_info``, it
may have installed more than 1 gigabyte of data. This section will help you to
reduce the footprint of your Qt installation.

.. note::

    Be careful about using the ``--archives`` flag; it is marked `Advanced` for a reason!
    It is very easy to misuse this command and end up with a Qt installation that
    is missing the components that you need.
    Don't use it unless you know what you are doing!


Minimum Qt Installation
```````````````````````

Normally, when you run ``aqt install-qt``, the program will print a long list
of archives that it is downloading, extracting, and installing,
including ``qtbase``, ``qtmultimedia``, ``qt3d``, and ~25 more items.
We can use the ``--archives`` flag to choose which of these archives we will
actually install.
The ``--archives`` flag can only affect two modules: the base Qt installation and the ``debug_info`` module.

.. note::
    In this documentation, **"modules"**, **"archives"**, and **"the base Qt installation"**
    refer to different things, and are defined here:

    - **Archives**: In this context, an **archive** is a bundle of files compressed
      with the 7zip algorithm.
      It exists on a disk drive as a file with the extension ``.7z``.

    - **Modules**: The Qt repository organizes groups of archives into modules.
      A **module** contains one or more **archives**.

    - **the base Qt installation**:
      By definition, this is just another **module** that contains 20-30 **archives**.
      This documentation refers to it as **the base Qt installation** instead of
      a **module** for several reasons:

        - The ``aqt install-qt`` installs this module by default.
        - You cannot specify this module with ``aqt install-qt --modules``.
        - The ``aqt list-qt --modules`` command is incapable of printing this module.
        - ``aqt`` transforms the names of modules as they exist in the Qt repository
          so that they are easier to read and write.
          If the name of **the base Qt installation** were transformed using the
          same rules, the name would be empty.

          The fully-qualified name of the **base Qt installation** module is
          usually something like ``qt.qt6.620.gcc_64``.
          The fully-qualified name of the ``qtcharts`` module could be
          something like ``qt.qt6.620.qtcharts.gcc_64``.
          It would be difficult to read and write a list of 20 modules with the prefix
          ``qt.qt6.620.`` and the suffix ``.gcc_64``, because these parts are
          repetitive and not meaningful. Only the ``qtcharts`` part is useful.

Let's say that we want to install Qt 5.15.2 for Linux desktop, using the gcc_64 architecture.
The ``qtbase`` archive includes the bare minimum for a working Qt installation,
and we can install it alone with the ``--archives`` flag:

.. code-block:: console

    $ aqt install-qt linux desktop 5.15.2 --archives qtbase

This time, ``aqt install-qt`` will only install one archive, ``qtbase``, instead
of the ~27 archives it installs by default.

Installing More Than The Bare Minimum
`````````````````````````````````````

Let's say that the ``qtbase`` archive is missing some features that you need.
Using the ``--archives qtbase`` flag causes ``aqt install-qt`` to omit roughly 27 archives.
We can print a list of these archives with the ``aqt list-qt --archives`` command:

.. code-block:: console

    $ aqt list-qt linux desktop --archives 5.15.2 gcc_64
    icu qt3d qtbase qtconnectivity qtdeclarative qtgamepad qtgraphicaleffects qtimageformats
    qtlocation qtmultimedia qtquickcontrols qtquickcontrols2 qtremoteobjects qtscxml
    qtsensors qtserialbus qtserialport qtspeech qtsvg qttools qttranslations qtwayland
    qtwebchannel qtwebsockets qtwebview qtx11extras qtxmlpatterns

Here, we have used the ``--archives`` flag with two arguments:
the version of Qt we are interested in, and the architecture we are using.
As a result, the command printed a list of archives that are part of the base
(non-minimal) Qt installation.

Let's say we need to use ``qtmultimedia``, ``qtdeclarative``, ``qtsvg``, and
nothing else. Remember that the ``qtbase`` archive is required for a minimal
working Qt installation. We can install these archives using this command:

.. code-block:: console

    $ aqt install-qt linux desktop 5.15.2 --archives qtbase qtmultimedia qtdeclarative qtsvg

Installing Modules With Archives Specified
``````````````````````````````````````````

As of aqt v2.1.0, the ``--archives`` flag will only apply to
the base Qt installation and to the ``debug_info`` module.
Previous versions of aqt required that when installing modules with the ``--archives`` flag,
the user must specify archives for each module, otherwise they would not be installed.
This behavior has been changed to prevent such mistakes.

Let's say that we need to install the bare minimum Qt 5.15.2, with the modules ``qtcharts`` and ``qtlottie``:

.. code-block:: console

    $ aqt install-qt linux desktop 5.15.2 --modules qtcharts qtlottie --archives qtbase

This command will successfully install 3 archives: 1 for ``qtbase``, and one each for the two modules.
If we had tried to use this command with previous versions of aqt, we would not have
installed the two modules because we did not specify them in the ``--archives`` list.

.. note::

    You can still misuse the ``--archives`` flag by omitting the ``qtbase`` archive,
    or by omitting archives that another archive or module is dependent on.
    You may not notice that there is a problem until you try to compile a program,
    and compilation fails.

Installing the ``debug_info`` module
````````````````````````````````````

Now let's say we need to install the ``debug_info`` module, which is particularly large: around one gigabyte.
We do not want to install all of it, so we can use ``aqt install-qt --archives``
to choose which archives we want to install. Remember that the ``--archives`` flag


``aqt list-qt --archives``
to print which archives are part of the ``debug_info`` module:

.. code-block:: console

    $ aqt list-qt linux desktop --archives 5.15.2 gcc_64 debug_info
    qt3d qtbase qtcharts qtconnectivity qtdatavis3d qtdeclarative qtgamepad qtgraphicaleffects
    qtimageformats qtlocation qtlottie qtmultimedia qtnetworkauth qtpurchasing qtquick3d
    qtquickcontrols qtquickcontrols2 qtquicktimeline qtremoteobjects qtscript qtscxml qtsensors
    qtserialbus qtserialport qtspeech qtsvg qttools qtvirtualkeyboard qtwayland qtwebchannel
    qtwebengine qtwebglplugin qtwebsockets qtwebview qtx11extras qtxmlpatterns

This is a lot of archives.
Note that there's a name collision between the ``debug_info`` archives and the
archives in every other module/Qt base install:
this is because there's a ``debug_info`` archive that corresponds to almost
every other archive available.

Let's install Qt with ``qtcharts`` and ``debug_info`` with some archives specified:

.. code-block:: console

    $ aqt install-qt linux desktop --modules qtcharts debug_info \
                                   --archives qtcharts qtbase qtdeclarative

Notice what we did here: We specified the ``qtcharts`` and ``debug_info`` modules,
and we specified the ``qtbase``, ``qtcharts``, and ``qtdeclarative`` archives.
This will install a total of 6 archives:

- the 3 archives named ``qtbase``, ``qtcharts``, and ``qtdeclarative`` from the ``debug_info`` module,
- the 1 archive ``qtcharts`` from the ``qtcharts`` module, and
- the 2 archives ``qtbase`` and ``qtdeclarative`` from the base Qt installation.

.. note::
    At present, ``aqt install-qt`` is incapable of installing any archive from
    the ``debug_info`` module without also installing the corresponding module
    from the base Qt installation.
    For instance, you cannot install the ``debug_info`` archive for ``qtbase``
    without also installing the usual ``qtbase`` archive.

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

To find out what versions of Qt are available, you can use the :ref:`aqt list-qt command <list qt command>`.
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
:ref:`aqt list-qt <list qt command>` commands is intended to make it easier for you to write programs
that consume the output of :ref:`aqt list-qt <list qt command>`.

Because the :ref:`aqt list-qt <list qt command>` command directly queries the Qt downloads repository
at https://download.qt.io/, the results of this command will always be accurate.
The `Available Qt versions`_ wiki page was last modified at some point in the past,
so it may or may not be up to date.

.. _Available Qt versions: https://github.com/miurahr/aqtinstall/wiki/Available-Qt-versions

Now that we know what versions of Qt are available, let's choose version 6.2.0.

The next thing we need to do is find out what architectures are available for
Qt 6.2.0 for Windows Desktop. To do this, we can use :ref:`aqt list-qt <list qt command>` with the
``--arch`` flag:

.. code-block:: console

    $ aqt list-qt windows desktop --arch 6.2.0
    win64_mingw81 win64_msvc2019_64 win64_msvc2019_arm64

Notice that this is a very small subset of the architectures listed in the 
`Available Qt versions`_ wiki page. If we need to use some architecture that
is not on this list, we can use the `Available Qt versions`_ wiki page to get
a rough idea of what versions support the architecture we want, and then use
:ref:`aqt list-qt <list qt command>` to confirm that the architecture is available.

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
with :ref:`aqt list-qt <list qt command>` with the ``--modules`` flag.
Each version of Qt has a different list of modules for each host OS/ target SDK
combination, so we will need to supply :ref:`aqt list-qt <list qt command>` with that information:

.. code-block:: console

    $ aqt list-qt windows desktop --modules 5.15.2
    debug_info qtcharts qtdatavis3d qtlottie qtnetworkauth qtpurchasing qtquick3d
    qtquicktimeline qtscript qtvirtualkeyboard qtwebengine qtwebglplugin

Let's say that we want to install `qtcharts` and `qtnetworkauth`. 
We can do that by using the `-m` flag with the :ref:`aqt install-qt <qt installation command>` command.
This flag receives the name of at least one module as an argument:

.. code-block:: console

    $ aqt install-qt windows desktop 5.15.2 win64_mingw81 -m qtcharts qtnetworkauth

If we wish to install all the modules that are available, we can do that with the ``all`` keyword:

.. code-block:: console

    $ aqt install-qt windows desktop 5.15.2 win64_mingw81 -m all

Remember that the :ref:`aqt list-qt <list qt command>` command is meant to be scriptable?
One way to install all modules available for Qt 5.15.2 is to send the output of
:ref:`aqt list-qt <list qt command>` into :ref:`aqt install-qt <qt installation command>`, like this:

.. code-block:: console

    $ aqt install-qt windows desktop 5.15.2 win64_mingw81 \
          -m $(aqt list-qt windows desktop --modules 5.15.2)

You will need a Unix-style shell to run this command, or at least git-bash on Windows.
The ``xargs`` equivalent to this command is an exercise left to the reader.

If you want to install all available modules, you are probably better off using
the ``all`` keyword, as discussed above. This scripting example is presented to
give you a sense of how to accomplish something more complicated.
Perhaps you want to install all modules except `qtnetworkauth`; you could write a script
that removes `qtnetworkauth` from the output of :ref:`aqt list-qt <list qt command>`,
and pipe that into :ref:`aqt install-qt <qt installation command>`.
This exercise is left to the reader.


Installing Qt for Android
-------------------------

Let's install Qt for Android. Installing Qt 5 will be similar to installing Qt
for Desktop on Windows, but there will be differences when we get to Qt 6.

.. code-block:: console

    $ aqt list-qt windows android                     # Print Qt versions available
    5.9.0 5.9.1 ...
    ...
    6.2.0

    $ aqt list-qt windows android --arch 5.15.2       # Print architectures available
    android

    $ aqt list-qt windows android --modules 5.15.2    # Print modules available
    qtcharts qtdatavis3d qtlottie qtnetworkauth qtpurchasing qtquick3d qtquicktimeline qtscript

    $ aqt install-qt windows android 5.15.2 android -m qtcharts qtnetworkauth   # Install

Let's see what happens when we try to list architectures and modules for Qt 6:

.. code-block:: console

    $ aqt list-qt windows android --arch 6.2.0       # Print architectures available
    Command line input error: Qt 6 for Android requires one of the following extensions:
    ('x86_64', 'x86', 'armv7', 'arm64_v8a').
    Please add your extension using the `--extension` flag.

    $ aqt list-qt windows android --modules 6.2.0    # Print modules available
    Command line input error: Qt 6 for Android requires one of the following extensions:
    ('x86_64', 'x86', 'armv7', 'arm64_v8a').
    Please add your extension using the `--extension` flag.

The Qt 6 for Android repositories are a little different than the Qt 5 repositories,
and the :ref:`aqt list-qt <list qt command>` tool doesn't know where to look for modules and architectures
if you don't tell it what architecture you need. I know, it sounds a little
backwards, but that's how the Qt repo was put together.

There are four architectures available, and the error message from :ref:`aqt list-qt <list qt command>`
just told us what they are: `x86_64`, `x86`, `armv7`, and `arm64_v8a`.
If we want to install Qt 6.2.0 for armv7, we use this command to print available modules:

.. code-block:: console

    $ aqt list-qt windows android --extension armv7 --modules 6.2.0
    qt3d qt5compat qtcharts qtconnectivity qtdatavis3d qtimageformats qtlottie
    qtmultimedia qtnetworkauth qtpositioning qtquick3d qtquicktimeline
    qtremoteobjects qtscxml qtsensors qtserialbus qtserialport qtshadertools
    qtvirtualkeyboard qtwebchannel qtwebsockets qtwebview

We know we want to use `armv7` for the architecture, but we don't know exactly
what value for 'architecture' we need to pass to :ref:`aqt install-qt <qt installation command>` yet, so we
will use :ref:`aqt list-qt <list qt command>` again:

.. code-block:: console

    $ aqt list-qt windows android --extension armv7 --arch 6.2.0
    android_armv7

You should be thinking, "Well, that was silly. All it did was add `android_` to
the beginning of the architecture I gave it. Why do I need to use
``aqt list-qt --arch`` for that?" The answer is, ``aqt list-qt --arch`` is
checking to see what actually exists in the Qt repository. If it prints an error
message, instead of the obvious `android_armv7`, we would know that Qt 6.2.0
for that architecture doesn't exist for some reason, and any attempt to install
it with :ref:`aqt install-qt <qt installation command>` will fail.

Finally, let's install Qt 6.2.0 for Android armv7 with some modules:

.. code-block:: console

    $ aqt install-qt linux android 6.2.0 android_armv7 -m qtcharts qtnetworkauth


Installing Qt for WASM
----------------------

To find out how to install Qt for WASM, we need to tell :ref:`aqt list-qt <list qt command>` that we are
using the `wasm` architecture. We can do that by using the ``--extension wasm`` flag.

.. code-block:: console

    $ aqt list-qt windows desktop --extension wasm
    5.13.1 5.13.2
    5.14.0 5.14.1 5.14.2
    5.15.0 5.15.1 5.15.2

There are only a few versions of Qt that support WASM, and they are only available
for desktop targets. If we tried this command with `android`, `winrt`, or `ios`
targets, we would have seen an error message.

We can check the architecture and modules available as before:

.. code-block:: console

    $ aqt list-qt windows desktop --extension wasm --arch 5.15.2     # Print architectures available
    wasm_32

    $ aqt list-qt windows desktop --extension wasm --modules 5.15.2  # Print modules available
    qtcharts qtdatavis3d qtlottie qtnetworkauth qtpurchasing qtquicktimeline qtscript
    qtvirtualkeyboard qtwebglplugin

We can install Qt for WASM as before:

.. code-block:: console

    $ aqt install-qt windows desktop 5.15.2 wasm_32 -m qtcharts qtnetworkauth


Installing Tools
----------------

Let's find out what tools are available for Windows Desktop by using the
:ref:`aqt list-tool <list tool command>` command:

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

The ``-l`` flag causes :ref:`aqt list-tool <list tool command>` to print a table
that shows plenty of data pertinent to each tool variant available in `tools_mingw`.
:ref:`aqt list-tool <list tool command>` additionally prints the 'Display Name'
and 'Description' for each tool if your terminal is wider than 95 characters;
terminals that are narrower than this cannot display this table in a readable way.

Now let's install `mingw`, using the :ref:`aqt install-tool <tools installation command>` command.
This command receives four parameters:

1. The host operating system (windows, mac, or linux)
2. The target SDK (desktop, android, ios, or winrt)
3. The name of the tool (this is `tools_mingw` in our case)
4. (Optional) The tool variant name. We saw a list of these when we ran
   :ref:`aqt list-tool <list tool command>` with the `tool name` argument filled in.

To install `mingw`, you could use this command (please don't):

.. code-block:: console

    $ aqt install-tool windows desktop tools_mingw    # please don't run this!

Using this command will install every tool variant available in `tools_mingw`;
in this case, you would install 10 different versions of the same tool.
For some tools, like `qtcreator` or `ifw`, this is an appropriate thing to do,
since each tool variant is a different program.
However, for tools like `mingw` and `vcredist`, it would make more sense to use
:ref:`aqt list-tool <list tool command>` to see what tool variants are available,
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

You may have noticed that by default, ``aqt install-qt`` installs a lot of
archives that you may or may not need, and a typical installation can take up
more disk space than necessary. If you installed the module ``debug_info``, it
may have installed more than 1 gigabyte of data. This section will help you to
reduce the footprint of your Qt installation.

Usually, when you run ``aqt install-qt``, the program will print a long list
of archives that it is downloading, extracting, and installing,
including ``qtbase``, ``qtmultimedia``, ``qt3d``, and around 20 more items.
We can use the ``--archives`` flag to choose which of these archives we will
actually install.

Let's say that we want to install Qt 5.15.2 for Linux desktop, using the gcc_64 architecture.
Many package managers will allow you to install something called ``qtbase``, which
is a version of the Qt SDK that is stripped down to the absolute bare minimum.
If you don't need any more the bare essentials, you can install this version of
Qt using the ``--archives`` flag:

.. code-block:: console

    $ aqt install-qt linux desktop 5.15.2 --archives qtbase

This time, ``aqt install-qt`` will only install one archive instead of the 27
archives it installs by default.

Let's say that ``qtbase`` is missing a few features that you need.
To print a list of all the archives that are part of the base Qt installation,
we can use the ``aqt list-qt --archives`` command:

.. code-block:: console

    $ aqt list-qt linux desktop --archives 5.15.2 gcc_64
    icu qt3d qtbase qtconnectivity qtdeclarative qtgamepad qtgraphicaleffects qtimageformats
    qtlocation qtmultimedia qtquickcontrols qtquickcontrols2 qtremoteobjects qtscxml
    qtsensors qtserialbus qtserialport qtspeech qtsvg qttools qttranslations qtwayland
    qtwebchannel qtwebsockets qtwebview qtx11extras qtxmlpatterns

Notice what happened here: We used the ``--archives`` flag with two arguments:
the version of Qt we are interested in, and the architecture we are using.
As a result, the command printed a list of archives that are part of the base
(non-minimal) Qt installation.

Let's say we need to use ``qtmultimedia``, ``qtdeclarative``, ``qtsvg``, and
nothing else. Remember that the ``qtbase`` archive is required for a minimal
working Qt installation. We can install these archives using this command:

.. code-block:: console

    $ aqt install-qt linux desktop 5.15.2 --archives qtbase qtmultimedia qtdeclarative qtsvg

Now let's say we need to install the ``qtcharts`` and ``qtlottie`` modules.
Let's see what archives are part of these modules:

.. code-block:: console

    $ aqt list-qt linux desktop --archives 5.15.2 gcc_64 qtcharts qtlottie
    qtcharts qtlottie

This time, the command only printed two archives.
The ``qtcharts`` and ``qtlottie`` modules are comprised of a single archive per module.
Notice that the command printed all archives associated with the modules we provided it,
and it did not print any of the archives associated with the base Qt installation.
The ``--archives`` flag with a Qt version and architecture alone will print
archives for the base Qt installation and none of the modules.
When you add a list of modules to the command, it will print a list of all archives
associated with those modules.

Now let's say we need to install the ``debug_info`` module, which is particularly large.
We do not want to install all of it, so we can use the ``--archives`` flag again
to print which archives are part of the ``debug_info`` module:

.. code-block:: console

    $ aqt list-qt linux desktop --archives 5.15.2 gcc_64 debug_info
    qt3d qtbase qtcharts qtconnectivity qtdatavis3d qtdeclarative qtgamepad qtgraphicaleffects
    qtimageformats qtlocation qtlottie qtmultimedia qtnetworkauth qtpurchasing qtquick3d
    qtquickcontrols qtquickcontrols2 qtquicktimeline qtremoteobjects qtscript qtscxml qtsensors
    qtserialbus qtserialport qtspeech qtsvg qttools qtvirtualkeyboard qtwayland qtwebchannel
    qtwebengine qtwebglplugin qtwebsockets qtwebview qtx11extras qtxmlpatterns

This is a lot of archives. Notice that the names in this list are a superset of
all the archive names associated with the base Qt installation. These names do
not refer to the same archives; the full names of the archives have been abridged
to make them easier to read and type.
The ``qtcharts`` archive from the ``qtcharts`` module is not the same as the
``qtcharts`` archive from the ``debug_info`` module, but their abridged names
are the same.

Also notice that this list overlaps with most of the list of modules available
for this version of Qt. This is because the ``debug_info`` module is intended to
provide debug info for most of the modules as well as the base Qt installation.

Let's install Qt with ``qtcharts``, ``qtlottie``, and ``debug_info`` with some
archives specified:

.. code-block:: console

    $ aqt install-qt linux desktop --modules qtcharts qtlottie debug_info \
                                   --archives qtcharts qtbase qtdeclarative

Notice what we did here: We specified the ``qtlottie`` module, but we did not
add ``qtlottie`` to the ``--archives`` flag. The ``--archives`` flag is used to
filter out any archives not in that list, which means ``qtlottie`` will not be installed.
This command is presented as a warning to you that in order to install a module
when you are using the ``--archives`` flag, you need to add the archive name
to the list of archives.

This command would successfully install the ``qtcharts`` and ``qtlottie`` modules:

.. code-block:: console

    $ aqt install-qt linux desktop --modules qtcharts qtlottie debug_info \
                                   --archives qtcharts qtlottie qtbase qtdeclarative

Also notice that we are installing part of the ``debug_info`` module.
Remember that this module includes archives called ``qtcharts``, ``qtlottie``,
``qtbase``, and ``qtdeclarative``. The base Qt installation and the modules
``qtcharts`` and ``qtlottie`` also contain archives by these names.
This command will install 8 archives: 4 as part of ``debug_info``, 2 from the
base Qt installation, and 2 from the modules.

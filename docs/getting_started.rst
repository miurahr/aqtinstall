:tocdepth: 2

.. _getting_started_ref:

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

To install Qt, you will need to tell ``aqt`` four things:

1. The host operating system (windows, mac, or linux)
2. The target SDK (desktop, android, ios, or winrt)
3. The version of Qt you would like to install
4. The target architecture

Keep in mind that Qt for ios is only available on Mac OS, and Qt for WinRT is 
only available on Windows.

To find out what versions of Qt are available, you can use the :ref:`List Qt command`.
This command will print all versions of Qt available for Windows desktop:

.. code-block:: console

    aqt list-qt windows desktop

Output:

.. code-block::

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
``aqt list-qt`` commands is intended to make it easier for you to write programs
that consume the output of ``aqt list-qt``.

Because the ``aqt list-qt`` command directly queries the Qt downloads repository
at https://download.qt.io/, the results of this command will always be accurate.
The :ref:`Available Qt versions` page of this documentation was written at some
point in the past, so it may or may not be up to date.

Now that we know what versions of Qt are available, let's choose version 6.2.0.

The next thing we need to do is find out what architectures are available for
Qt 6.2.0 for Windows desktop. To do this, we can use ``aqt list-qt`` with the
`--arch` flag:

.. code-block:: console

    aqt list-qt windows desktop --arch 6.2.0

Output:

.. code-block::

  win64_mingw81 win64_msvc2019_64 win64_msvc2019_arm64

Notice that this is a very small subset of the architectures listed in the 
:ref:`Available Qt versions` page. If we need to use some architecture that
is not on this list, we can use the :ref:`Available Qt versions` page to get
a rough idea of what versions support the architecture we want, and then use
``aqt list-qt`` to confirm that the architecture is available.

Let's say that we want to install Qt 6.2.0 with architecture `win64_mingw81`.
The installation command we need is:

.. code-block:: console

    aqt install-qt windows desktop 6.2.0 win64_mingw81


Installing Modules
------------------

Let's say we need to install some modules for Qt 5.15.2 on Windows desktop. 
First we need to find out what the modules are called, and we can do that 
with ``aqt list-qt`` with the `--modules` flag.
Each version of Qt has a different list of modules for each host OS/ target SDK
combination, so we will need to supply ``aqt list-qt`` with that information:

.. code-block:: console

    aqt list-qt windows desktop --modules 5.15.2

Output:

.. code-block::

    debug_info qtcharts qtdatavis3d qtlottie qtnetworkauth qtpurchasing qtquick3d 
    qtquicktimeline qtscript qtvirtualkeyboard qtwebengine qtwebglplugin

Let's say that we want to install `qtcharts` and `qtnetworkauth`. 
We can do that by using the `-m` flag with the ``aqt install-qt`` command.
This flag receives the name of at least one module as an argument:

.. code-block:: console

    aqt install-qt windows desktop 5.15.2 win64_mingw81 -m qtcharts qtnetworkauth

Remember that the ``aqt list-qt`` command is meant to be scriptable? If you want
to install all modules available for Qt 5.15.2, we can do so by sending the
output of ``aqt list-qt`` into ``aqt install-qt``, like this:

.. code-block:: console

    aqt install-qt windows desktop 5.15.2 win64_mingw81 -m $(aqt list-qt windows desktop --modules 5.15.2)

You will need a Unix-style shell to run this command, or at least git-bash on Windows.
The ``xargs`` equivalent to this command is an exercise left to the reader.

Let's try to install `qtcharts` and `qtnetworkauth` for Qt 6.1.2 as well. 
Before we do this, let's run ``aqt list-qt``:

.. code-block:: console

    aqt list-qt windows desktop --modules 6.1.2

Output:

.. code-block::

    addons.qt3d addons.qtactiveqt addons.qtcharts addons.qtdatavis3d addons.qtimageformats 
    addons.qtlottie addons.qtnetworkauth addons.qtscxml addons.qtvirtualkeyboard 
    debug_info qt5compat qtquick3d qtquicktimeline qtshadertools

What's this? There's no `qtcharts` or `qtnetworkauth`, but there are 
`addons.qtcharts` and `addons.qtnetworkauth`. Sometime after Qt 6, the module
naming conventions changed, so we will have to refer to these modules by their
new names to install them successfully:

.. code-block:: console

    aqt install-qt windows desktop 6.1.2 win64_mingw81 -m addons.qtcharts addons.qtnetworkauth


Installing Tools
----------------

Let's find out what tools are available for Windows desktop by using the
``aqt list-tool`` command:

.. code-block:: console

    aqt list-tool windows desktop

Output:

.. code-block::

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

Let's see what's in `tools_mingw`, using the `-l` or `--long` flag:

.. code-block:: console

    aqt list-tool windows desktop tools_mingw -l

Output:

.. code-block::

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

The `-l` flag causes ``aqt list-tool`` to print a table that shows plenty of
data pertinent to each tool variant available in `tools_mingw`.
``aqt list-tool`` additionally prints the 'Display Name' and 'Description' for
each tool if your terminal is wider than 95 characters; terminals that are
narrower than this cannot display this table in a readable way.

Now let's install `mingw`, using the ``aqt tool`` command.
This command receives four parameters:

1. The host operating system (windows, mac, or linux)
2. The target SDK (desktop, android, ios, or winrt)
3. The name of the tool (this is `tools_mingw` in our case)
4. (Optional) The tool variant name.
   We saw a list of these when we ran ``aqt list-tool`` with the ``-l`` flag

To install `mingw`, you could use this command (please don't):

.. code-block:: console

    aqt tool windows desktop tools_mingw    # please don't run this!

Using this command will install every tool variant available in `tools_mingw`;
in this case, you would install 10 different versions of the same tool.
For some tools, like `qtcreator` or `ifw`, this is an appropriate thing to do,
since each tool variant is a different program.
However, for tools like `mingw` and `vcredist`, it would make more sense to use
``aqt list-tool`` to see what tool variants are available, and then install just
the tool variant you are interested in, like this:

.. code-block:: console

    aqt tool windows desktop tools_mingw qt.tools.win64_mingw730


Installing Qt for WASM
----------------------
Planned: discuss using the ``--extensions`` flags and ``--extension wasm``


Installing Qt for Android
-------------------------
Planned: discuss specifying the target architecture with the ``--extension`` flag





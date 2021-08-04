:tocdepth: 2

.. _installation:

Installation
============

Requirements
------------

- Minimum Python version:  3.6
- Recommended Python version: 3.7.5 or later

- Dependent libraries: requests, py7zr


Install by pip command
----------------------

Same as usual, it can be installed with `pip`

.. code-block:: bash

    $ pip install aqtinstall



Command changes
===============

From version 2.0.0, sub commands are changed.
The previous versions of these sub commands have been retained for backwards
compatibility, but are no longer recommended.

+------------------+---------------------+----------------------------+
| New sub commands | Legacy sub commands |  Note                      |
+==================+=====================+============================+
| install-qt       | install             | Version moved after target |
+------------------+---------------------+----------------------------+
| install-tool     | tool                | Arguments are changed      |
|                  |                     |                            |
|                  |                     | New syntax doesn't take    |
|                  |                     | version                    |
+------------------+---------------------+----------------------------+
| install-example  | examples            | Version moved after target |
|                  |                     |                            |
|                  |                     | Caution with last (s)      |
+------------------+---------------------+----------------------------+
| install-src      | src                 | Version moved after target |
|                  |                     |                            |
|                  |                     | New command only can       |
|                  |                     | take --kde option          |
+------------------+---------------------+----------------------------+
| install-doc      | doc                 | Version moved after target |
+------------------+---------------------+----------------------------+
|                  | list                | Legacy list commands are   |
|                  |                     | removed.                   |
+------------------+---------------------+----------------------------+
| list-qt          |                     |                            |
+------------------+---------------------+----------------------------+
| list-tool        |                     |                            |
+------------------+---------------------+----------------------------+


Usage
=====

General usage looks like this:

.. code-block:: bash

    aqt install-qt
        [-h | --help]
        [-O | --outputdir <directory>]
        [-E | --external <7zip command>]
        [-m | --modules (all | <module> [<module>...])]
        <host> <target> <Qt version> [<arch>]

You can also call with ``python -m aqt`` syntax as well as command script ``aqt``.
Some older operating systems may require you to specify Python version 3, like this: ``python3 -m aqt``.

* Host is one of: `linux`, `mac`, `windows`
* Target is one of: `desktop`, `android`, `winrt`, `ios`
  (iOS only works with mac host, and winrt only works with windows host)
* The Qt version is formatted like this: `5.11.3`
* For some host/target combinations, you also need to specify an arch:
    * For windows desktop, choose one of:
        * `win64_msvc2019_64`, `win32_msvc2019`,
        * `win64_msvc2017_64`, `win32_msvc2017`,
        * `win64_msvc2015_64`, `win32_msvc2015`,
        * `win64_mingw81`, `win32_mingw81`,
        * `win64_mingw73`, `win32_mingw73`,
        * `win64_mingw53`, `win32_mingw53`,
        * `win64_msvc2019_winrt_x64`, `win64_msvc2019_winrt_x86`, `win64_msvc2019_winrt_armv7`
        * `win64_msvc2017_winrt_x64`, `win64_msvc2017_winrt_x86`, `win64_msvc2017_winrt_armv7`
    * For android and Qt 5.11 or below, choose one of: `android_x86`, `android_armv7`
    * For android and Qt 5.12 or Qt 5.13 or Qt 6, choose one of:
      `android_x86_64`, `android_arm64_v8a`, `android_x86`, `android_armv7`
* You can specify external 7zip command path instead of built-in extractor by using the ``-E`` or ``--external`` flag.
* You can specify an alternate output directory by using the ``-O`` or ``--outputdir`` flag.
* To install all available modules, you can use the option ``-m all``.

A full description of the options for ``aqt install-qt`` is available in the documentation
for the :ref:`Qt installation command`.

Installing tool and utility
---------------------------

You can install tools and utilities using the :ref:`tools installation command`:

.. code-block:: bash

    aqt install-tool [-h | --help] <host> <target> <tool_name> [<arch>]

* tool_name is one of `tools_ifw`, `tools_vcredist`, and `tools_openssl`.
  Use the :ref:`aqt list-tool <list tool command>` to show what tools are available.
* arch is full qualified tool name such as `qt.tools.ifw.31`.
  Please use :ref:`aqt list-tool <list tool command>` to list acceptable values for this parameter.
* It does not recognize 'installscript.qs'. When using tools which depends on a qt script, you should do something by yourself.


Target directory
----------------

You can change the installation directory by using the option ``--outputdir`` or ``-O``.
This option works for ``aqt install-qt``, ``aqt install-tool``, and any other subcommand
that begins with ``install-``.

By default, the Qt packages are installed in the current working directory, in
the subdirectory ``./<Qt version>/<arch>/``.
For example, if you install Qt 5.11.3 for Windows desktop with arch `win64_msvc2019_64`,
it would end up in ``./5.11.3/win64_msvc2019_64``.

To install to ``C:\Qt``, the default directory used by the standard gui installer,
you may use this command:

.. code-block:: doscon

    C:\> mkdir Qt
    C:\> aqt install-qt --outputdir c:\Qt windows desktop 5.11.3 win64_msvc2019_64

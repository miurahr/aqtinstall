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

+----------------- -+---------------------+----------------------------+
| New sub commands  | Legacy sub commands |  Note                      |
+===================+=====================+============================+
| install-qt        | install             | version moved after target |
+----------------- -+---------------------+----------------------------+
| install-tool      | tool                | Arguments are changed      |
|                   |                     | new syntax doesn't take    |
|                   |                     | version                    |
+----------------- -+---------------------+----------------------------+
| install-example   | examples            | version moved after target |
|                   |                     | caution with last (s)      |
+----------------- -+---------------------+----------------------------+
| install-src       | src                 | version moved after target |
|                   |                     | New command only can       |
|                   |                     | take --kde option          |
+----------------- -+---------------------+----------------------------+
| install-doc       | doc                 | version moved after target |
+----------------- -+---------------------+----------------------------+
|                   | list                | legacy list commands are   |
|                   |                     | removed.                   |
+----------------- -+---------------------+----------------------------+
| list-qt           |                     |                            |
+----------------- -+---------------------+----------------------------+
| list-tool         |                     |                            |
+----------------- -+---------------------+----------------------------+


Usage
=====

General usage looks like this:

.. code-block:: bash

    aqt [-h][--help][-O | --outputdir <directory>][-b | --base <mirror url>][-E | --external <7zip command>] \
        install-qt <host> <target> <qt-version> [<arch>] [-m all | -m [extra module] [extra module]...] [--internal]
        [--archives <archive>[ <archive>...]] [--timeout <timeout(sec)>]

You can also call with ``python -m aqt`` syntax as well as command script ``aqt``.
Some older operating systems may require you to specify Python version 3, like this: ``python3 -m aqt``.

* Host is one of: `linux`, `mac`, `windows`
* Target is one of: `desktop`, `android`, `ios` (iOS only works with mac host)
* The Qt version is formatted like this: `5.11.3`
* For some platforms you also need to specify an arch:
    * For windows, choose one of:
        * `win64_msvc2019_64`, `win32_msvc2019`,
        * `win64_msvc2017_64`, `win32_msvc2017`,
        * `win64_msvc2015_64`, `win32_msvc2015`,
        * `win64_mingw81`, `win32_mingw81`,
        * `win64_mingw73`, `win32_mingw73`,
        * `win64_mingw53`, `win32_mingw53`,
        * `win64_msvc2019_winrt_x64`, `win64_msvc2019_winrt_x86`, `win64_msvc2019_winrt_armv7`
        * `win64_msvc2017_winrt_x64`, `win64_msvc2017_winrt_x86`, `win64_msvc2017_winrt_armv7`
    * For android and Qt 5.13 or below, choose one of: `android_x86_64`, `android_arm64_v8a`, `android_x86`,
      `android_armv7`
* You can specify external 7zip command path instead of built-in extractor.
* When specifying `all` for extra modules option `-m` all extra modules are installed.


Installing tool and utility (Experimental)
------------------------------------------

You can install tools and utilities using the :ref:`tools installation command`:

.. code-block:: bash

    python -m aqt [-h][--help][-O | --outputdir <directory>][-b | --base <mirror url>][-E | --external <7zip command>] \
        install-tool <host> <target> <tool_name> [<arch>] [--timeout <timeout>]

* tool_name is one of `tools_ifw`, `tools_vcredist`, and `tools_openssl`.
* arch is full qualified tool name such as `qt.tools.ifw.31`.
  Please use :ref:`aqt list-tool <list tool command>` to list acceptable values for this parameter.
  This is a quite experimental feature, may not work and please use it with your understanding of what you are doing.
* It does not recognize 'installscript.qs'. When using tools which depends on a qt script, you should do something by yourself.


Target directory
----------------

aqt can take option '--outputdir' or '-O' that specify a target directory.

The Qt packages are installed under current directory as such `Qt/<ver>/gcc_64/`
If you want to install it in `C:\Qt` as same as standard gui installer default,
run such as follows:

.. code-block:: bash

    C:\> mkdir Qt
    C:\> aqt install-qt --outputdir c:\Qt windows desktop 5.11.3 win64_msvc2019_64

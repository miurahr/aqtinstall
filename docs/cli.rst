.. _string-options-ref:

*********************
Command Line Options
*********************

The CLI uses argparse to parse the command line options so the short or long versions may be used and the
long options may be truncated to the shortest unambiguous abbreviation.

.. program::  aqt

.. option:: list

    list available versions (not implemented yet)

.. option:: help

    show generic help

.. option:: install <Qt version> <target OS> <target variant> <target environment>

    install Qt library specified version and target.

.. describe:: Qt version

    This is a Qt version such as 5.9,7, 5.12.1 etc

.. describe:: target OS

    linux, windows or mac

.. describe:: target variant

    desktop or android

.. describe:: target environment

   * gcc_64 for linux desktop

   * clang_64 for mac desktip

   * win64_msvc2017_64, win64_msvc2015_64, in32_msvc2015, win32_mingw53 for windows desktop

   * android_x86, android_armv7 for android

.. option:: --version, -v

    Display version

.. option:: --help, -h

    Display help text

.. option:: --outputdir, -O <Output Directory>

    specify output directory.

.. option:: --base, -b <base url>

    specify mirror site base url such as  -b 'http://mirrors.ocf.berkeley.edu/qt/'
    where 'online' folder exist.

.. option:: --modules, -m <list of modules>

    specify extra modules to install as a list.

.. code-block::

    -m qtcharts qtdatavis3d qtlottie qtnetworkauth qtpurchasing qtquicktimeline qtscript qtvirtualkeyboard qtwebglplugin


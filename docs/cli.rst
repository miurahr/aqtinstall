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

.. option:: src <Qt version> <target OS> <target variant>

    install Qt sources specified version and target.


.. option:: doc <Qt version> <target OS> <target variant>

    install Qt documents specified version and target.


.. option:: examples <Qt version> <target OS> <target variant>

    install Qt examples specified version and target.


.. option:: tool <target OS> <target tool name> <target tool version> <tool variant name>

    install tools specified. tool name may be 'tools_openssl_x64', 'tools_ninja', 'tools_ifw', 'tools_cmake'
    and tool variants name may be 'qt.tools.openssl.gcc_64', 'qt.tools.ninja',  'qt.tools.ifw.32', 'qt.tools.cmake'.
    You may need to looking for version number at  https://download.qt.io/online/qtsdkrepository/



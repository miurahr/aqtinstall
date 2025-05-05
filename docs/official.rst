.. _official:

Official Qt Installer
=====================

.. important::
   * **You can use this for commercial and open-source Qt versions**
   * **You can only install for the OS running the CLI**
   * **All commands require authentication, even for open-source.** The authentication process:

     * It first looks into the folder of your OS where the file ``qtaccount.ini`` can be:

       * Windows: ``C:\Users\<username>\AppData\Roaming\Qt\qtaccount.ini``
       * Linux: ``/home/<username>/.local/share/Qt/qtaccount.ini``
       * MacOS: ``/Users/<username>/Library/Application Support/Qt/qtaccount.ini``

     This file is automatically created when you use the ``MaintenanceTool`` binary and log in using the GUI. It is also created the first time you use the CLI or any mean to authenticate. You can simply copy the file from your PC to the CI server, it will work across platforms. Just treat it as a password. Refer to `this page <https://doc.qt.io/qt-6/get-and-install-qt-cli.html#providing-login-information>`_ for more details.

     * It will also check the value of the environment variable ``QT_INSTALLER_JWT_TOKEN`` and use the token if provided.
     * If neither are present, you will need to provide ``--email <email> --pw <password>``.  
       The Qt official installer will generate a ``qtaccount.ini`` file in the relevant folder for your OS (see above for its location) if there is not one already present. That file contains your Qt JSON Web Token (JWT), and must be treated as a password.  
       Note that if ``--email`` and ``--pw`` are provided, they will supersede the ``qtaccount.ini`` and the JWT provided in the environment.  

``install-qt-official``
------------------------
Install Qt packages using the official Qt installer.

.. code-block:: bash

   aqt install-qt-official <target> <arch> <version> [options]

Arguments
~~~~~~~~~
- ``target`` - Target platform (desktop, android, ios)
- ``arch`` - Target architecture
- ``version`` - Qt version to install

Options
~~~~~~~
- ``--email <email>`` - Qt account email/username
- ``--pw <password>`` - Qt account password
- ``--modules <module1> <module2> ...`` - Additional Qt modules to install

  * Very broad meaning, aka ``packages`` or ``components`` (`see here <https://doc.qt.io/qt-6/get-and-install-qt-cli.html#component-names-for-installation>`_). Extensions, wasm, src... are 'modules'
  * If none are inputed, the package ``qtX.Y.Z-essentials`` is downloaded (default Qt install, includes ``qtcreator``...)
  * If ``all`` is inputed, the package ``qtX.Y.Z-full`` is downloaded (includes everything)

- ``--outputdir <path>`` - Installation directory (default: current directory)
- ``--override <args...>`` - Pass all remaining arguments directly to the Qt installer CLI

``list-qt-official``
---------------------
Search available Qt packages using the official Qt installer.

.. code-block:: bash

   aqt list-qt-official [search_terms] [options]

Options
~~~~~~~
- ``--email <email>`` - Qt account email/username
- ``--pw <password>`` - Qt account password
- ``search_terms`` - Terms to search for in package names (grabs all that is not other options)

Override Mode
----------------------
``install-qt-official`` supports an override mode that passes all arguments after ``--override`` directly to the Qt installer CLI, and will ignore all the other params except ``--email`` and ``--pw`` if given prior to it

.. code-block:: bash

   aqt install-qt-official --override [installer_args... --email email --pw password]
   aqt install-qt-official --email email --pw password --override [installer_args...]

When using override mode:

* All standard command options are ignored
* Arguments are passed directly to the Qt installer
* The ``--email``/``--pw`` flags are used for authentication
* `More info here <https://doc.qt.io/qt-6/get-and-install-qt-cli.html>`_

Examples
--------------
.. code-block:: bash

   # Standard installation
   aqt install-qt-official desktop linux_gcc_64 6.8.0 --email user@example.com --pw pass

   # Installation with modules
   aqt install-qt-official desktop linux_gcc_64 6.8.0 --email user@example.com --pw pass --modules qtcharts qtnetworkauth

   # List packages containing 'wasm'
   aqt list-qt-official wasm --email user@example.com --pw pass

   # Override mode
   aqt install-qt-official --override install qt.qt6.680.gcc_64 --email user@example.com --pw pass

Advanced configs
--------------------------
The file located in ``./aqt/settings.ini`` can be edited in the ``[qtofficial]`` part to fine tune the official installer (`more details here <https://doc.qt.io/qt-6/get-and-install-qt-cli.html#message-identifiers-for-auto-answer>`_):

.. code-block:: ini

   [qtofficial]
   unattended : True # Removes needs of user interaction, and simplifies the --override option as well by passing flags by default to remain unattended
   installer_timeout : 1800
   operation_does_not_exist_error : Ignore
   overwrite_target_directory : No
   stop_processes_for_updates : Ignore
   installation_error_with_cancel : Ignore
   installation_error_with_ignore : Ignore
   associate_common_filetypes : Yes
   telemetry : No
   cache_path : # When empty, will use ~/.local/share/aqt/cache or equivalent for your OS
   temp_dir : # When empty, will use ~/.local/share/aqt/tmp or equivalent for your OS

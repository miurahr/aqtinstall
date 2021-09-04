:tocdepth: 2

.. _installation:

Installation
============

Requirements
------------

- Minimum Python version:  3.6
- Recommended Python version: 3.7.5 or later

- Dependent libraries: requests, py7zr, semantic_version, patch, texttable, bs4


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


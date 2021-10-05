.. _configuration-ref:

Configuration
=============

``aqtinstall`` can be configured through a configuration file.
A default configuration is stored in ``aqt/settings.ini`` file.

You can specify custom configuration file through ``AQT_CONFIG``
environment variable or "-c" or "--config" command line option.

A file is like as follows:

.. code-block::

    [DEFAULTS]

    [aqt]
    concurrency: 4
    baseurl: https://download.qt.io
    7zcmd: 7z
    print_stacktrace_on_error: False

    [requests]
    connection_timeout: 3.5
    response_timeout: 30
    max_retries_on_connection_error: 5
    retry_backoff: 0.1
    max_retries_on_checksum_error: 5

    [mirrors]
    blacklist:
        http://mirrors.ustc.edu.cn
        http://mirrors.tuna.tsinghua.edu.cn
        http://mirrors.geekpie.club
    fallbacks:
        https://mirrors.ocf.berkeley.edu/qt
        https://ftp.jaist.ac.jp/pub/qtproject
        http://ftp1.nluug.nl/languages/qt
        https://mirrors.dotsrc.org/qtproject

    [kde_patches]
    patches:
        0001-toolchain.prf-Use-vswhere-to-obtain-VS-installation-.patch


Settings
--------

The ``[aqt]`` section configures basic behavior.

concurrency:
    ``concurrency`` is a setting how many download concurrently starts.
    It should be a integer value.

baseurl:
    ``baseurl`` is a URL of Qt download site.
    When you have your own Qt download site repository, you can set it here.
    It is as same as ``--base`` option.

7zcmd:
    It is a command name of 7-zip. When ``aqtinstall`` is installed **without**
    recommended library ``py7zr``, it is used to extract archive instead of
    ``py7zr`` library.
    When ``--external`` option specified, a value is override with option's one.

print_stacktrace_on_error:
    ``print_stacktrace_on_error`` is either ``True`` or ``False``.
    The ``True`` setting causes a stack trace to be printed to stderr any time
    an error occurs that will end the program.
    The ``False`` setting will hide the stack trace, unless an unhandled
    exception occurs.


The ``[requests]`` section controls the way that ``aqt`` makes network requests.

connection_timeout:
    ``connection_timeout`` is a timeout in second for connection.
    It is passed to ``requests`` library.

response_timeout:
    ``response_timeout`` is a timeout in second how much time waiting for response.
    It is passed to ``requests`` library.

max_retries:
    Deprecated; please do not use this setting. It has been replaced by the

max_retries_on_connection_error:
    ``max_retries_on_connection_error`` is an integer that controls how many times
    ``aqt`` will try to reconnect to the server in the case of a connection error.

retry_backoff:
    ``retry_backoff`` is a floating point number that controls how long ``aqt``
    will sleep between failed connection attempts.
    Setting this value too low will hammer the server, and may result
    in no successful connections at all.

max_retries_on_checksum_error:
    This setting controls how many times ``aqt`` will attempt to download a file,
    in the case of a checksum error.


The ``[mirrors]`` section is a configuration for mirror handling.

blacklist:
    It is a list of URL where is a problematic mirror site.
    Some mirror sites ignore a connection from IP addresses out of their preffered one.
    It will cause connection error or connection timeout.
    There are some known mirror sites in default.
    When you are happy with the default sites,
    you can override with your custom settings.

fallbacks:
    It is a list of URL where is a good for access.
    When mirror site cause an error, aqt use fallbacks when possible.

import os

import aqt


def test_cli_help(capsys):
    expected = "".join(["show help\n",
                        "usage: aqt [-h] [--logging-conf LOGGING_CONF] [--logger LOGGER]\n",
                        "           {install,tool,list,help} ...\n",
                        "\n",
                        "Installer for Qt SDK.\n",
                        "\n",
                        "optional arguments:\n",
                        "  -h, --help            show this help message and exit\n",
                        "  --logging-conf LOGGING_CONF\n",
                        "                        Logging configuration ini file.\n",
                        "  --logger LOGGER       Specify logger name\n",
                        "\n",
                        "subcommands:\n",
                        "  Valid subcommands\n",
                        "\n",
                        "  {install,tool,list,help}\n",
                        "                        subcommand for aqt Qt installer\n"])
    cli = aqt.cli.Cli()
    cli.run(["help"])
    out, err = capsys.readouterr()
    assert out == expected


def test_cli_check_module():
    cli = aqt.cli.Cli()
    assert cli._check_modules_arg('5.11.3', ['qtcharts', 'qtwebengine'])
    assert not cli._check_modules_arg('5.7', ['not_exist'])
    assert cli._check_modules_arg('5.14.0', None)
    assert not cli._check_modules_arg('5.15.0', ["Unknown"])


def test_cli_check_combination():
    cli = aqt.cli.Cli()
    assert cli._check_qt_arg_combination('5.11.3', 'linux', 'desktop', 'gcc_64')
    assert cli._check_qt_arg_combination('5.11.3', 'mac', 'desktop', 'clang_64')
    assert not cli._check_qt_arg_combination('5.14.0', 'android', 'desktop', 'clang_64')


def test_cli_check_mirror():
    cli = aqt.cli.Cli()
    assert cli._check_mirror(None)
    arg = ['install', '5.11.3', 'linux', 'desktop', '-b', "https://download.qt.io/"]
    args = cli.parser.parse_args(arg)
    assert args.base == 'https://download.qt.io/'
    assert cli._check_mirror(args.base)


def test_cli_make_config_file(tmp_path):
    cli = aqt.cli.Cli()
    os.makedirs(tmp_path.joinpath('5.11.3', 'clang_64', 'bin'))
    os.makedirs(tmp_path.joinpath('5.11.3', 'clang_64', 'mkspecs'))
    with tmp_path.joinpath('5.11.3', 'clang_64', 'mkspecs', 'qconfig.pri').open('w') as f:
        f.write("QT_ARCH = x86_64\n"
                "QT_BUILDABI = x86_64-little_endian-lp64\n"
                "QT.global.enabled_features = shared rpath c++11 c++14 future "
                "concurrent pkg-config separate_debug_info\n"
                "QT.global.disabled_features = cross_compile framework appstore-compliant debug_and_release "
                "simulator_and_device build_all c++1z force_asserts static\n"
                "QT_CONFIG += shared rpath release c++11 c++14 concurrent dbus "
                "reduce_exports reduce_relocations separate_debug_info stl\n"
                "CONFIG += shared release\n"
                "QT_VERSION = 5.11.3\n"
                "QT_MAJOR_VERSION = 5\n"
                "QT_MINOR_VERSION = 11\n"
                "QT_PATCH_VERSION = 3\n"
                "QT_GCC_MAJOR_VERSION = 5\n"
                "QT_GCC_MINOR_VERSION = 3\n"
                "QT_GCC_PATCH_VERSION = 1\n"
                "QT_EDITION = Enterprise\n"
                "QT_LICHECK = licheck64\n"
                "QT_RELEASE_DATE = 2018-11-29\n")
    cli.make_conf_files('5.11.3', 'clang_64', tmp_path)
    assert os.path.exists(tmp_path.joinpath('5.11.3', 'clang_64', 'bin', 'qt.conf'))

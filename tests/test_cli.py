import aqt


def test_cli_help(capsys):
    expected = "".join(["usage: aqt [-h] [--logging-conf LOGGING_CONF] [--logger LOGGER]\n",
                        "           {install,doc,examples,src,tool,list,help} ...\n",
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
                        "  {install,doc,examples,src,tool,list,help}\n",
                        "                        subcommand for aqt Qt installer\n"])
    cli = aqt.installer.Cli()
    cli.run(["help"])
    out, err = capsys.readouterr()
    assert out == expected


def test_cli_check_module():
    cli = aqt.installer.Cli()
    assert cli._check_modules_arg('5.11.3', ['qtcharts', 'qtwebengine'])
    assert not cli._check_modules_arg('5.7', ['not_exist'])
    assert cli._check_modules_arg('5.14.0', None)
    assert not cli._check_modules_arg('5.15.0', ["Unknown"])


def test_cli_check_combination():
    cli = aqt.installer.Cli()
    assert cli._check_qt_arg_combination('5.11.3', 'linux', 'desktop', 'gcc_64')
    assert cli._check_qt_arg_combination('5.11.3', 'mac', 'desktop', 'clang_64')
    assert not cli._check_qt_arg_combination('5.14.0', 'android', 'desktop', 'clang_64')


def test_cli_check_version():
    cli = aqt.installer.Cli()
    assert cli._check_qt_arg_versions('5.12.0')
    assert not cli._check_qt_arg_versions('5.12')


def test_cli_check_mirror():
    cli = aqt.installer.Cli()
    assert cli._check_mirror(None)
    arg = ['install', '5.11.3', 'linux', 'desktop', '-b', "https://download.qt.io/"]
    args = cli.parser.parse_args(arg)
    assert args.base == 'https://download.qt.io/'
    assert cli._check_mirror(args.base)


def test_cli_launch_with_no_argument(capsys):
    expected = "".join(["usage: aqt [-h] [--logging-conf LOGGING_CONF] [--logger LOGGER]\n",
                        "           {install,doc,examples,src,tool,list,help} ...\n",
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
                        "  {install,doc,examples,src,tool,list,help}\n",
                        "                        subcommand for aqt Qt installer\n"])
    cli = aqt.installer.Cli()
    cli.run([])
    out, err = capsys.readouterr()
    assert out == expected

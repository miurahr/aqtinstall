import aqt


def test_cli_help(capsys):
    expected = "".join(["show help\n",
                        "usage: aqt [-h] [--logging-conf LOGGING_CONF] [--logger LOGGER] [--dry-run]\n",
                        "           {install,tool,list,help} ...\n",
                        "\n",
                        "Installer for Qt SDK.\n",
                        "\n",
                        "optional arguments:\n",
                        "  -h, --help            show this help message and exit\n",
                        "  --logging-conf LOGGING_CONF\n",
                        "                        Specify logging configuration YAML file.\n",
                        "  --logger LOGGER       Specify logger name\n",
                        "  --dry-run             Dry run operations.\n",
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


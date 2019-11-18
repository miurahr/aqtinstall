import pytest

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


def test_cli_license_agreement(capsys, monkeypatch):

    def mockinput(prompt):
        print(prompt, end='')
        return "yes\n"

    monkeypatch.setattr('builtins.input', mockinput)

    expected = ['Please agree with Qt license: GPLv3 and LGPL\n',
                'The terms is in https://www.qt.io/download-open-source\n',
                'Do you agree upon the terms? (yes/no): ']
    expected_str = ''.join(expected)
    cli = aqt.cli.Cli()
    with pytest.raises(SystemExit) as e:
        cli.run(["--dry-run", "install", "5.14.0", "linux", "desktop"])
    assert e.type == SystemExit
    assert e.value.code == 0
    out, err = capsys.readouterr()
    assert out == expected_str

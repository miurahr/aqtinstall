import re
import sys

import pytest
from semantic_version import Version

import aqt


def test_cli_help(capsys):
    expected = "".join(
        [
            "usage: aqt [-h] [-c CONFIG]\n",
            "           {install,doc,examples,src,tool,list,help,version} ...\n",
            "\n",
            "Installer for Qt SDK.\n",
            "\n",
            "optional arguments:\n",
            "  -h, --help            show this help message and exit\n",
            "  -c CONFIG, --config CONFIG\n",
            "                        Configuration ini file.\n",
            "\n",
            "subcommands:\n",
            "  Valid subcommands\n",
            "\n",
            "  {install,doc,examples,src,tool,list,help,version}\n",
            "                        subcommand for aqt Qt installer\n",
        ]
    )
    cli = aqt.installer.Cli()
    cli.run(["help"])
    out, err = capsys.readouterr()
    assert out == expected


def test_cli_check_module():
    cli = aqt.installer.Cli()
    cli._setup_settings()
    assert cli._check_modules_arg("5.11.3", ["qtcharts", "qtwebengine"])
    assert not cli._check_modules_arg("5.7", ["not_exist"])
    assert cli._check_modules_arg("5.14.0", None)
    assert not cli._check_modules_arg("5.15.0", ["Unknown"])


def test_cli_check_combination():
    cli = aqt.installer.Cli()
    cli._setup_settings()
    assert cli._check_qt_arg_combination("5.11.3", "linux", "desktop", "gcc_64")
    assert cli._check_qt_arg_combination("5.11.3", "mac", "desktop", "clang_64")
    assert not cli._check_qt_arg_combination("5.14.0", "android", "desktop", "clang_64")


def test_cli_check_version():
    cli = aqt.installer.Cli()
    cli._setup_settings()
    assert cli._check_qt_arg_versions("5.12.0")
    assert not cli._check_qt_arg_versions("5.12")


@pytest.mark.parametrize(
    "invalid_version",
    ("5.15", "five-dot-fifteen", "5", "5.5.5.5"),
)
def test_cli_invalid_version(capsys, invalid_version):
    """Checks that invalid version strings are handled properly"""

    # Ensure that invalid_version cannot be a Version
    with pytest.raises(ValueError):
        Version(invalid_version)

    cli = aqt.installer.Cli()
    cli._setup_settings()

    matcher = re.compile(
        r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
        r".*Invalid version: '"
        + invalid_version
        + r"'! Please use the form '5\.X\.Y'\.\n.*"
    )

    for cmd in (
        ("install", invalid_version, "mac", "desktop"),
        ("doc", invalid_version, "mac", "desktop"),
        ("list", "qt5", "mac", "desktop", "--modules", invalid_version),
    ):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            cli = aqt.installer.Cli()
            cli.run(cmd)
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        sys.stdout.write(out)
        sys.stderr.write(err)
        assert matcher.match(err)


def test_cli_check_mirror():
    cli = aqt.installer.Cli()
    cli._setup_settings()
    assert cli._check_mirror(None)
    arg = ["install", "5.11.3", "linux", "desktop", "-b", "https://download.qt.io/"]
    args = cli.parser.parse_args(arg)
    assert args.base == "https://download.qt.io/"
    assert cli._check_mirror(args.base)


def test_cli_launch_with_no_argument(capsys):
    expected = "".join(
        [
            "usage: aqt [-h] [-c CONFIG]\n",
            "           {install,doc,examples,src,tool,list,help,version} ...\n",
            "\n",
            "Installer for Qt SDK.\n",
            "\n",
            "optional arguments:\n",
            "  -h, --help            show this help message and exit\n",
            "  -c CONFIG, --config CONFIG\n",
            "                        Configuration ini file.\n",
            "\n",
            "subcommands:\n",
            "  Valid subcommands\n",
            "\n",
            "  {install,doc,examples,src,tool,list,help,version}\n",
            "                        subcommand for aqt Qt installer\n",
        ]
    )
    cli = aqt.installer.Cli()
    cli.run([])
    out, err = capsys.readouterr()
    assert out == expected

import re
import sys
from pathlib import Path

import pytest

from aqt.exceptions import CliInputError
from aqt.installer import Cli
from aqt.metadata import MetadataFactory, SimpleSpec, Version


def test_cli_help(capsys):
    expected = "".join(
        [
            "usage: aqt [-h] [-c CONFIG]\n",
            "           {install-qt,install-tool,install-doc,install-example,install-src,list-qt,list-tool,",
            "install,tool,doc,example,src,help,version}\n",
            "           ...\n",
            "\n",
            "Another unofficial Qt Installer.\n",
            "aqt helps you install Qt SDK, tools, examples and others\n",
            "\n",
            "optional arguments:\n",
            "  -h, --help            show this help message and exit\n",
            "  -c CONFIG, --config CONFIG\n",
            "                        Configuration ini file.\n",
            "\n",
            "subcommands:\n",
            "  aqt accepts several subcommands:\n",
            "  install-* subcommands are commands that install components\n",
            "  list-* subcommands are commands that show available components\n",
            "  \n",
            "  commands {install|tool|src|examples|doc} are deprecated and marked for removal\n",
            "\n",
            "  {install-qt,install-tool,install-doc,install-example,install-src,list-qt,list-tool,",
            "install,tool,doc,example,src,help,version}\n",
            "                        Please refer to each help message by using '--help' with each subcommand\n",
        ]
    )
    cli = Cli()
    cli.run(["help"])
    out, err = capsys.readouterr()
    assert out == expected


def test_cli_check_module():
    cli = Cli()
    cli._setup_settings()
    assert cli._check_modules_arg("5.11.3", ["qtcharts", "qtwebengine"])
    assert not cli._check_modules_arg("5.7", ["not_exist"])
    assert cli._check_modules_arg("5.14.0", None)
    assert not cli._check_modules_arg("5.15.0", ["Unknown"])


def test_cli_check_combination():
    cli = Cli()
    cli._setup_settings()
    assert cli._check_qt_arg_combination("5.11.3", "linux", "desktop", "gcc_64")
    assert cli._check_qt_arg_combination("5.11.3", "mac", "desktop", "clang_64")
    assert not cli._check_qt_arg_combination("5.14.0", "android", "desktop", "clang_64")


def test_cli_check_version():
    cli = Cli()
    cli._setup_settings()
    assert cli._check_qt_arg_versions("5.12.0")
    assert not cli._check_qt_arg_versions("5.12")


@pytest.mark.parametrize(
    "host, target, arch, version_or_spec, expected_version, is_bad_spec",
    (
        ("windows", "desktop", "wasm_32", "6.1", None, False),
        ("windows", "desktop", "wasm_32", "5.12", None, False),
        ("windows", "desktop", "wasm_32", "5.13", Version("5.13.2"), False),
        ("windows", "desktop", "wasm_32", "5", Version("5.15.2"), False),
        ("windows", "desktop", "wasm_32", "<5.14.5", Version("5.14.2"), False),
        ("windows", "desktop", "mingw32", "6.0", Version("6.0.3"), False),
        ("windows", "winrt", "mingw32", "6", None, False),
        ("windows", "winrt", "mingw32", "bad spec", None, True),
        ("windows", "android", "android_x86", "6", Version("6.1.0"), False),
        ("windows", "desktop", "android_x86", "6", Version("6.1.0"), False),  # does not validate arch
        ("windows", "desktop", "android_fake", "6", Version("6.1.0"), False),  # does not validate arch
    ),
)
def test_cli_determine_qt_version(
    monkeypatch, host, target, arch, version_or_spec: str, expected_version: Version, is_bad_spec: bool
):
    _html = (Path(__file__).parent / "data" / f"{host}-{target}.html").read_text("utf-8")
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, _: _html)
    cli = Cli()
    cli._setup_settings()

    if is_bad_spec:
        with pytest.raises(CliInputError) as e:
            Cli._determine_qt_version(version_or_spec, host, target, arch)
        assert e.type == CliInputError
        assert format(e.value) == f"Invalid version or SimpleSpec: '{version_or_spec}'\n" + SimpleSpec.usage()
    elif not expected_version:
        with pytest.raises(CliInputError) as e:
            Cli._determine_qt_version(version_or_spec, host, target, arch)
        assert e.type == CliInputError
        expect_msg = f"No versions of Qt exist for spec={version_or_spec} with host={host}, target={target}, arch={arch}"
        actual_msg = format(e.value)
        assert actual_msg == expect_msg
    else:
        ver = Cli._determine_qt_version(version_or_spec, host, target, arch)
        assert ver == expected_version


@pytest.mark.parametrize(
    "invalid_version",
    ("5.15", "five-dot-fifteen", "5", "5.5.5.5"),
)
def test_cli_invalid_version(capsys, invalid_version):
    """Checks that invalid version strings are handled properly"""

    # Ensure that invalid_version cannot be a semantic_version.Version
    with pytest.raises(ValueError):
        Version(invalid_version)

    cli = Cli()
    cli._setup_settings()

    matcher = re.compile(
        r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
        r"(.*\n)*"
        r".*Invalid version: '" + invalid_version + r"'! Please use the form '5\.X\.Y'\.\n.*"
    )

    for cmd in (
        ("install", invalid_version, "mac", "desktop"),
        ("doc", invalid_version, "mac", "desktop"),
        ("list-qt", "mac", "desktop", "--modules", invalid_version),
    ):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            cli = Cli()
            cli.run(cmd)
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        sys.stdout.write(out)
        sys.stderr.write(err)
        assert matcher.match(err)


def test_cli_check_mirror():
    cli = Cli()
    cli._setup_settings()
    assert cli._check_mirror(None)
    arg = ["install-qt", "linux", "desktop", "5.11.3", "-b", "https://download.qt.io/"]
    args = cli.parser.parse_args(arg)
    assert args.base == "https://download.qt.io/"
    assert cli._check_mirror(args.base)

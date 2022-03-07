import re
import sys
from pathlib import Path
from typing import Optional

import pytest

from aqt.exceptions import CliInputError
from aqt.installer import Cli
from aqt.metadata import MetadataFactory, SimpleSpec, Version


def expected_help(actual, prefix=None):
    expected = (
        "usage: aqt [-h] [-c CONFIG]\n"
        "           {install-qt,install-tool,install-doc,install-example,install-src,"
        "list-qt,list-tool,list-doc,list-example,list-src,"
        "install,tool,doc,examples,src,help,version}\n"
        "           ...\n"
        "\n"
        "Another unofficial Qt Installer.\n"
        "aqt helps you install Qt SDK, tools, examples and others\n"
        "\n"
        "option",
        "  -h, --help            show this help message and exit\n"
        "  -c CONFIG, --config CONFIG\n"
        "                        Configuration ini file.\n"
        "\n"
        "subcommands:\n"
        "  aqt accepts several subcommands:\n"
        "  install-* subcommands are commands that install components\n"
        "  list-* subcommands are commands that show available components\n"
        "  \n"
        "  commands {install|tool|src|examples|doc} are deprecated and marked for "
        "removal\n"
        "\n"
        "  {install-qt,install-tool,install-doc,install-example,install-src,list-qt,"
        "list-tool,list-doc,list-example,list-src,"
        "install,tool,doc,examples,src,help,version}\n"
        "                        Please refer to each help message by using '--help' "
        "with each subcommand\n",
    )
    if prefix is not None:
        return actual.startswith(prefix + expected[0]) and actual.endswith(expected[1])
    return actual.startswith(expected[0]) and actual.endswith(expected[1])


def test_cli_help(capsys):
    cli = Cli()
    cli.run(["help"])
    out, err = capsys.readouterr()
    assert expected_help(out)


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
    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda *args, **kwargs: _html)
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
        ("list-qt", "mac", "desktop", "--arch", invalid_version),
    ):
        cli = Cli()
        assert cli.run(cmd) == 1
        out, err = capsys.readouterr()
        sys.stdout.write(out)
        sys.stderr.write(err)
        assert matcher.match(err)


@pytest.mark.parametrize(
    "version, allow_latest, allow_empty, allow_minus, expect_ok",
    (
        ("1.2.3", False, False, False, True),
        ("1.2.", False, False, False, False),
        ("latest", True, False, False, True),
        ("latest", False, False, False, False),
        ("", False, True, False, True),
        ("", False, False, False, False),
        ("1.2.3-0-123", False, False, True, True),
        ("1.2.3-0-123", False, False, False, False),
    ),
)
def test_cli_validate_version(version: str, allow_latest: bool, allow_empty: bool, allow_minus: bool, expect_ok: bool):
    if expect_ok:
        Cli._validate_version_str(version, allow_latest=allow_latest, allow_empty=allow_empty, allow_minus=allow_minus)
    else:
        with pytest.raises(CliInputError) as err:
            Cli._validate_version_str(version, allow_latest=allow_latest, allow_empty=allow_empty, allow_minus=allow_minus)
        assert err.type == CliInputError


def test_cli_check_mirror():
    cli = Cli()
    cli._setup_settings()
    assert cli._check_mirror(None)
    arg = ["install-qt", "linux", "desktop", "5.11.3", "-b", "https://download.qt.io/"]
    args = cli.parser.parse_args(arg)
    assert args.base == "https://download.qt.io/"
    assert cli._check_mirror(args.base)


@pytest.mark.parametrize(
    "arch, host, target, version, expect",
    (
        ("impossible_arch", "windows", "desktop", "6.2.0", "impossible_arch"),
        ("", "windows", "desktop", "6.2.0", None),
        (None, "windows", "desktop", "6.2.0", None),
        (None, "linux", "desktop", "6.2.0", "gcc_64"),
        (None, "mac", "desktop", "6.2.0", "clang_64"),
        (None, "mac", "ios", "6.2.0", "ios"),
        (None, "mac", "android", "6.2.0", "android"),
        (None, "mac", "android", "5.12.0", None),
        # SimpleSpec instead of Version
        ("impossible_arch", "windows", "desktop", "6.2", "impossible_arch"),
        ("", "windows", "desktop", "6.2", None),
        (None, "windows", "desktop", "6.2", None),
        (None, "linux", "desktop", "6.2", "gcc_64"),
        (None, "mac", "desktop", "6.2", "clang_64"),
        (None, "mac", "ios", "6.2", "ios"),
        (None, "mac", "android", "6.2", None),  # No way to determine arch for android target w/o version
    ),
)
def test_set_arch(arch: Optional[str], host: str, target: str, version: str, expect: Optional[str]):

    if not expect:
        with pytest.raises(CliInputError) as e:
            Cli._set_arch(arch, host, target, version)
        assert e.type == CliInputError
        assert format(e.value) == "Please supply a target architecture."
        assert e.value.should_show_help is True
    else:
        assert Cli._set_arch(arch, host, target, version) == expect


@pytest.mark.parametrize(
    "cmd, expect_msg, should_show_help",
    (
        (
            "install-qt mac ios 6.2.0 --base not_a_url",
            "The `--base` option requires a url where the path `online/qtsdkrepository` exists.",
            True,
        ),
        (
            "install-qt mac ios 6.2.0 --noarchives",
            "When `--noarchives` is set, the `--modules` option is mandatory.",
            False,
        ),
        (
            "install-qt mac ios 6.2.0 --noarchives --archives",
            "When `--noarchives` is set, the `--modules` option is mandatory.",
            False,
        ),
        (
            "install-qt mac ios 6.2.0 --noarchives --archives --modules qtcharts",
            "Options `--archives` and `--noarchives` are mutually exclusive.",
            False,
        ),
        (
            "install-src mac ios 6.2.0 --kde",
            "KDE patch: unsupported version!!",
            False,
        ),
    ),
)
def test_cli_input_errors(capsys, cmd, expect_msg, should_show_help):
    cli = Cli()
    cli._setup_settings()
    assert 1 == cli.run(cmd.split())
    out, err = capsys.readouterr()
    if should_show_help:
        assert expected_help(out)
    else:
        assert out == ""
    assert err.rstrip().endswith(expect_msg)


# These commands use the new syntax with the legacy commands
@pytest.mark.parametrize(
    "cmd",
    (
        "install linux desktop 5.10.0",
        "install linux desktop 5.10.0 gcc_64",
        "src linux desktop 5.10.0",
        "doc linux desktop 5.10.0",
        "example linux desktop 5.10.0",
        "tool windows desktop tools_ifw",
    ),
)
def test_cli_legacy_commands_with_wrong_syntax(cmd):
    cli = Cli()
    cli._setup_settings()
    with pytest.raises(SystemExit) as e:
        cli.run(cmd.split())
    assert e.type == SystemExit


@pytest.mark.parametrize(
    "cmd",
    (
        "tool windows desktop tools_ifw qt.tools.ifw.31",  # New syntax
        "tool windows desktop tools_ifw 1.2.3",
    ),
)
def test_cli_legacy_tool_new_syntax(monkeypatch, capsys, cmd):
    # These incorrect commands cannot be filtered out directly by argparse because
    # they have the correct number of arguments.
    command = cmd.split()

    expected = (
        "Warning: The command 'tool' is deprecated and marked for removal in a future version of aqt.\n"
        "In the future, please use the command 'install-tool' instead.\n"
        "Invalid version: 'tools_ifw'! Please use the form '5.X.Y'.\n"
    )

    cli = Cli()
    cli._setup_settings()
    assert 1 == cli.run(command)
    out, err = capsys.readouterr()
    actual = err[err.index("\n") + 1 :]
    assert actual == expected


# These commands come directly from examples in the legacy documentation
@pytest.mark.parametrize(
    "cmd",
    (
        "install 5.10.0 linux desktop",  # default arch
        "install 5.10.2 linux android android_armv7",
        "src 5.15.2 windows desktop --archives qtbase --kde",
        "doc 5.15.2 windows desktop -m qtcharts qtnetworkauth",
        "examples 5.15.2 windows desktop -m qtcharts qtnetworkauth",
        "tool linux tools_ifw 4.0 qt.tools.ifw.40",
    ),
)
def test_cli_legacy_commands_with_correct_syntax(monkeypatch, cmd):
    # Pretend to install correctly when any command is run
    for func in ("run_install_qt", "run_install_src", "run_install_doc", "run_install_example", "run_install_tool"):
        monkeypatch.setattr(Cli, func, lambda *args, **kwargs: 0)

    cli = Cli()
    cli._setup_settings()
    assert 0 == cli.run(cmd.split())


def test_cli_unexpected_error(monkeypatch, capsys):
    def _mocked_run(*args):
        raise RuntimeError("Some unexpected error")

    monkeypatch.setattr("aqt.installer.Cli.run_install_qt", _mocked_run)

    cli = Cli()
    cli._setup_settings()
    assert Cli.UNHANDLED_EXCEPTION_CODE == cli.run(["install-qt", "mac", "ios", "6.2.0"])
    out, err = capsys.readouterr()
    assert err.startswith("Some unexpected error")
    assert err.rstrip().endswith(
        "===========================PLEASE FILE A BUG REPORT===========================\n"
        "You have discovered a bug in aqt.\n"
        "Please file a bug report at https://github.com/miurahr/aqtinstall/issues.\n"
        "Please remember to include a copy of this program's output in your report."
    )


def test_cli_set_7zip(monkeypatch):
    cli = Cli()
    cli._setup_settings()
    with pytest.raises(CliInputError) as err:
        cli._set_sevenzip("some_nonexistent_binary")
    assert err.type == CliInputError
    assert format(err.value) == "Specified 7zip command executable does not exist: 'some_nonexistent_binary'"


@pytest.mark.parametrize(
    "archive_dest, keep, temp_dir, expect, should_make_dir",
    (
        (None, False, "temp", "temp", False),
        (None, True, "temp", ".", False),
        ("my_archives", False, "temp", "my_archives", True),
        ("my_archives", True, "temp", "my_archives", True),
    ),
)
def test_cli_choose_archive_dest(
    monkeypatch, archive_dest: Optional[str], keep: bool, temp_dir: str, expect: str, should_make_dir: bool
):
    enclosed = {"made_dir": False}

    def mock_mkdir(*args, **kwargs):
        enclosed["made_dir"] = True

    monkeypatch.setattr("aqt.installer.Path.mkdir", mock_mkdir)

    assert Cli.choose_archive_dest(archive_dest, keep, temp_dir) == Path(expect)
    assert enclosed["made_dir"] == should_make_dir

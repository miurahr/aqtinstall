import pytest

import aqt


@pytest.mark.remote_data
def test_cli_unknown_version(capsys):
    expected = ""
    cli = aqt.cli.Cli()
    cli.run(["install", "5.12", "mac", "desktop"])
    out, err = capsys.readouterr()
    assert out == expected

import sys

import pytest

import aqt


@pytest.mark.remote_data
def test_cli_unknown_version(capsys):
    wrong_version = "5.12"
    wrong_url = "https://download.qt.io/online/qtsdkrepository/mac_x64/desktop/qt5_512/Updates.xml"
    expected = [
        "<<ignore>>",
        "aqt - WARNING - Specified Qt version is unknown: {}.".format(wrong_version),
        "aqt - ERROR - Download error when access to {}"
        " Server response code: 404, reason code: Not Found".format(wrong_url),
    ]
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        cli = aqt.installer.Cli()
        cli.run(["install", wrong_version, "mac", "desktop"])
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    sys.stdout.write(out)
    sys.stderr.write(err)
    for i, line in enumerate(out):
        if i == 0:
            continue
        assert line.endswith(expected[i])

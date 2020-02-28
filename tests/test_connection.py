import pytest

import aqt


@pytest.mark.remote_data
def test_cli_unknown_version(capsys):
    expected = ["aqt - WARNING - Specified Qt version is unknown: 5.12.",
                "aqt - ERROR - Download error when access to https://download.qt.io/online/qtsdkrepository/mac_x64/desktop/qt5_512/Updates.xml Server response code: 404, reason code: Not Found"
               ]
    cli = aqt.cli.Cli()
    cli.run(["install", "5.12", "mac", "desktop"])
    out, err = capsys.readouterr()
    for i, line in enumerate(out):
        assert line.endswith(expected[i])

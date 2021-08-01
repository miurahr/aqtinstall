import re
import sys

import pytest

import aqt


@pytest.mark.remote_data
def test_cli_unknown_version(capsys):
    wrong_version = "5.16.0"
    wrong_url_ending = "mac_x64/desktop/qt5_5160/Updates.xml"
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        cli = aqt.installer.Cli()
        cli.run(["install-qt", "mac", "desktop", wrong_version])
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    sys.stdout.write(out)
    sys.stderr.write(err)
    assert not out

    """
    Expected result when no redirect occurs:

    aqtinstall(aqt) v.* on Python 3.*
    Specified Qt version is unknown: 5.16.0.
    Failed to retrieve file at https://download.qt.io/online/qtsdkrepository/mac_x64/desktop/qt5_5160/Updates.xml
    Server response code: 404, reason: Not Found

    Expected result when redirect occurs:

    aqtinstall(aqt) v.* on Python 3.*
    Specified Qt version is unknown: 5.16.0.
    Connection to the download site failed and fallback to mirror site.
    Failed to retrieve file at .*/mac_x64/desktop/qt5_5160/Updates.xml
    Server response code: 404, reason: Not Found
    Connection to the download site failed. Aborted...
    """

    matcher = re.compile(
        r"^aqtinstall\(aqt\) v.* on Python 3.*\n"
        r".*Specified Qt version is unknown: " + re.escape(wrong_version) + r"\.\n"
        r".*Failed to retrieve file at .*" + re.escape(wrong_url_ending) + r"\n"
        r".*Server response code: 404, reason: Not Found.*"
    )

    assert matcher.match(err)

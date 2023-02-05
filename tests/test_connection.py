import re
import sys

import pytest

import aqt


@pytest.mark.enable_socket
@pytest.mark.remote_data
def test_cli_unknown_version(capsys):
    wrong_version = "5.16.0"
    cli = aqt.installer.Cli()
    assert cli.run(["install-qt", "mac", "desktop", wrong_version]) == 1
    out, err = capsys.readouterr()
    sys.stdout.write(out)
    sys.stderr.write(err)
    assert not out

    """
    Expected result when no redirect occurs:

    aqtinstall(aqt) v.* on Python 3.*
    Specified Qt version is unknown: 5.16.0.
    Failed to locate XML data for Qt version '5.16.0'.
    ==============================Suggested follow-up:==============================
    * Please use 'aqt list-qt mac desktop' to show versions available.

    Expected result when redirect occurs:

    aqtinstall(aqt) v.* on Python 3.*
    Specified Qt version is unknown: 5.16.0.
    Connection to the download site failed and fallback to mirror site.
    Failed to locate XML data for Qt version '5.16.0'.
    ==============================Suggested follow-up:==============================
    * Please use 'aqt list-qt mac desktop' to show versions available.
    """

    matcher = re.compile(
        r"[^\n]*aqtinstall\(aqt\) v.* on Python 3.*\n"
        r".*Specified Qt version is unknown: " + re.escape(wrong_version) + r"\.\n"
        r".*Failed to locate XML data for Qt version '" + re.escape(wrong_version) + r"'\.\n"
        r"==============================Suggested follow-up:==============================\n"
        r"\* Please use 'aqt list-qt mac desktop' to show versions available\.\n",
    )

    assert matcher.match(err)

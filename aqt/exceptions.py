#!/usr/bin/env python3
#
# Copyright (C) 2019-2021 Hiroshi Miura <miurahr@linux.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
from typing import Iterable

DOCS_CONFIG = "https://aqtinstall.readthedocs.io/en/stable/configuration.html#configuration"


class AqtException(Exception):
    def __init__(self, *args, **kwargs):
        self.suggested_action: Iterable[str] = kwargs.pop("suggested_action", [])
        self.should_show_help: bool = kwargs.pop("should_show_help", False)
        super(AqtException, self).__init__(*args, **kwargs)

    def __format__(self, format_spec) -> str:
        base_msg = "{}".format(super(AqtException, self).__format__(format_spec))
        if not self.suggested_action:
            return base_msg
        return f"{base_msg}\n{self._format_suggested_follow_up()}"

    def _format_suggested_follow_up(self) -> str:
        return ("=" * 30 + "Suggested follow-up:" + "=" * 30 + "\n") + "\n".join(
            ["* " + suggestion for suggestion in self.suggested_action]
        )


class ArchiveDownloadError(AqtException):
    pass


class ArchiveChecksumError(ArchiveDownloadError):
    pass


class ChecksumDownloadFailure(ArchiveDownloadError):
    def __init__(self, *args, **kwargs):
        kwargs["suggested_action"] = kwargs.pop("suggested_action", []).extend(
            [
                "Check your internet connection",
                "Consider modifying `requests.max_retries_to_retrieve_hash` in settings.ini",
                f"Consider modifying `mirrors.trusted_mirrors` in settings.ini (see {DOCS_CONFIG})",
            ]
        )
        kwargs["should_show_help"] = True
        super(ChecksumDownloadFailure, self).__init__(*args, **kwargs)


class ArchiveConnectionError(AqtException):
    pass


class ArchiveListError(AqtException):
    pass


class NoPackageFound(AqtException):
    pass


class EmptyMetadata(AqtException):
    pass


class CliInputError(AqtException):
    pass


class CliKeyboardInterrupt(AqtException):
    pass


class ArchiveExtractionError(AqtException):
    pass


class UpdaterError(AqtException):
    pass


class OutOfMemory(AqtException):
    pass

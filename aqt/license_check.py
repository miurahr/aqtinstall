#!/usr/bin/env python3
#
# Copyright (C) 2026 Hiroshi Miura <miurahr@linux.com>
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
"""Best-effort LGPL / commercial-use compliance checking for Qt modules.

Qt's own package metadata (`Updates.xml`) has no machine-readable license field. In practice,
Qt embeds a consistent boilerplate sentence in the free-text `Description` of GPL-v3-only
add-ons ("...available under commercial licenses from The Qt Company, or under GPL v3...."),
while LGPL-eligible modules simply have an empty description. This module sniffs that live
text; it does not, and cannot, maintain its own list of module licenses. Anything it cannot
positively classify as LGPL-eligible is treated as blocked, since the purpose of this check is
to catch problems, not to assume the best.

This is a heuristic aid only, not legal advice: see `DISCLAIMER`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aqt.helper import Settings
from aqt.metadata import ArchiveId, MetadataFactory

DISCLAIMER = (
    "NOTE: --ensure-lgpl is a best-effort heuristic based on the free-text descriptions that Qt "
    "publishes for each module. It is NOT legal advice, it cannot detect every commercial-only "
    "component, and it cannot verify that YOUR use of a module actually complies with LGPL "
    "(for example, dynamic-linking/relinking obligations). aqtinstall and its maintainers take "
    "no legal responsibility for mistakes this check might make. Always verify licensing "
    "yourself before shipping a commercial product."
)

LGPL = "lgpl"
GPL_ONLY = "gpl_only"
UNKNOWN = "unknown"

_STATUS_LABELS = {
    LGPL: "OK (LGPL-eligible)",
    GPL_ONLY: "BLOCKED (GPL v3 only, per Qt's own description)",
    UNKNOWN: "BLOCKED (could not verify from Qt's metadata)",
}

# Matches Qt's boilerplate for GPL-v3-only add-ons, e.g.:
#   "This component is available under commercial licenses from The Qt Company, or under
#    GPL v3. For open source use, please note the additional requirements compared to LGPL v3."
_GPL_ONLY_PATTERN = re.compile(r"\bgpl\s*v?\.?\s*3\b", re.IGNORECASE)


@dataclass
class ModuleVerdict:
    module: str
    status: str  # one of LGPL, GPL_ONLY, UNKNOWN
    description: str = ""


@dataclass
class LgplCheckReport:
    verdicts: List[ModuleVerdict] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return all(v.status == LGPL for v in self.verdicts)

    def format(self) -> str:
        lines = []
        for v in self.verdicts:
            lines.append(f"  - {v.module}: {_STATUS_LABELS[v.status]}")
            if v.status != LGPL and v.description:
                snippet = " ".join(v.description.split())
                lines.append(f'      "{snippet[:200]}"')
        return "\n".join(lines)


def classify_description(description: Optional[str]) -> str:
    """Classifies a single module's Qt-published `Description` text."""
    text = (description or "").strip()
    if not text:
        return LGPL
    if _GPL_ONLY_PATTERN.search(text):
        return GPL_ONLY
    return UNKNOWN


def check_modules(
    host: str,
    target: str,
    version: str,
    arch: str,
    modules: List[str],
    base_url: Optional[str] = None,
) -> LgplCheckReport:
    """Checks a list of requested Qt module names against Qt's published metadata.

    Only modules named in `modules` are checked -- the base Qt package itself is always
    LGPL-licensed. The literal module name "all" expands to every module Qt publishes for
    this version/arch, matching the meaning "all" has for `install-qt -m`.
    """
    if not modules:
        return LgplCheckReport(verdicts=[])
    base = base_url or Settings.baseurl
    archive_id = ArchiveId("qt", host, target)
    factory = MetadataFactory(
        archive_id,
        base_url=base,
        modules_query=MetadataFactory.ModulesQuery(version, arch),
        is_long_listing=True,
    )
    module_data = factory.getList()
    table: Dict[str, Dict[str, str]] = getattr(module_data, "table_data", {})

    requested = list(table.keys()) if "all" in modules else modules

    verdicts = []
    for module in requested:
        info = table.get(module)
        if info is None:
            verdicts.append(
                ModuleVerdict(
                    module=module,
                    status=UNKNOWN,
                    description="This module was not found in Qt's metadata for this version/architecture.",
                )
            )
            continue
        description = info.get("Description", "")
        verdicts.append(ModuleVerdict(module=module, status=classify_description(description), description=description))
    return LgplCheckReport(verdicts=verdicts)

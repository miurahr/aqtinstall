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
"""Parsing and resolution of `aqt-requirements.yml` manifests.

A requirements manifest lets a repository pin the exact Qt packages it needs, so that
`aqt install --requirements` can reproduce the same install on any contributor's machine
with a single command. Each entry pins an exact version; the host OS is auto-detected from
the machine running aqt (or overridden with `--host`), and any field that varies by host
(most commonly `arch`, for Windows' MSVC/MinGW toolchains) may be given as a mapping of
host name to value instead of a plain string.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from aqt.exceptions import CliInputError

DEFAULT_REQUIREMENTS_FILENAME = "aqt-requirements.yml"

# Host keys accepted in manifest `arch`/`variant` mappings, and by the `--host` override.
# These match the `host` values accepted by `install-qt`/`install-tool`, minus `all_os`,
# which has no meaning as "the machine currently running aqt".
HOST_CHOICES = ("linux", "linux_arm64", "mac", "windows", "windows_arm64")

_SECTION_NAMES = ("qt", "tool", "src", "doc", "example")

HostKeyedStr = Union[str, Dict[str, str]]


def detect_host() -> str:
    """Detects the host key for the machine currently running aqt.

    This is the same axis as install-qt/install-tool's `host` positional argument, used to
    resolve manifest entries without requiring the manifest to hardcode which OS runs it.
    """
    machine = platform.machine().lower()
    is_arm = machine in ("arm64", "aarch64")
    platform_name = sys.platform.lower()
    if platform_name == "darwin":
        return "mac"
    if platform_name.startswith("linux"):
        return "linux_arm64" if is_arm else "linux"
    return "windows_arm64" if is_arm else "windows"


def _resolve_host_keyed(value: Optional[HostKeyedStr], host: str, field_name: str, context: str) -> Optional[str]:
    """Resolves a field that may be a plain string (applies to every host) or a mapping of host -> value."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if host not in value:
        raise CliInputError(
            f"{context}: '{field_name}' does not define a value for host '{host}'. "
            f"Available hosts in this entry: {', '.join(sorted(value)) or '(none)'}"
        )
    return value[host]


def _require_str(entry: Dict[str, Any], key: str, context: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise CliInputError(f"{context}: missing or invalid required field '{key}'")
    return value


def _require_str_list(entry: Dict[str, Any], key: str, context: str) -> List[str]:
    value = entry.get(key) or []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CliInputError(f"{context}: '{key}' must be a list of strings")
    return list(value)


@dataclass
class QtRequirement:
    """A pinned entry from the manifest's `qt:` section."""

    version: str
    target: str
    arch: HostKeyedStr
    modules: List[str] = field(default_factory=list)

    def resolved_arch(self, host: str) -> str:
        arch = _resolve_host_keyed(self.arch, host, "arch", f"qt entry '{self.version}/{self.target}'")
        assert arch is not None  # `arch` is a required field; see _parse_qt_entry
        return arch


@dataclass
class ToolRequirement:
    """A pinned entry from the manifest's `tool:` section."""

    name: str
    target: str = "desktop"
    variant: Optional[HostKeyedStr] = None

    def resolved_variant(self, host: str) -> Optional[str]:
        return _resolve_host_keyed(self.variant, host, "variant", f"tool entry '{self.name}'")


@dataclass
class SdeRequirement:
    """A pinned entry from the manifest's `src:`, `doc:`, or `example:` sections."""

    version: str
    modules: List[str] = field(default_factory=list)


@dataclass
class RequirementsManifest:
    qt: List[QtRequirement] = field(default_factory=list)
    tool: List[ToolRequirement] = field(default_factory=list)
    src: List[SdeRequirement] = field(default_factory=list)
    doc: List[SdeRequirement] = field(default_factory=list)
    example: List[SdeRequirement] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.qt or self.tool or self.src or self.doc or self.example)


def _parse_qt_entry(entry: Any, index: int) -> QtRequirement:
    context = f"qt[{index}]"
    if not isinstance(entry, dict):
        raise CliInputError(f"{context}: each entry must be a mapping")
    version = _require_str(entry, "version", context)
    target = _require_str(entry, "target", context)
    arch = entry.get("arch")
    if arch is None:
        raise CliInputError(f"{context}: missing required field 'arch'")
    if not isinstance(arch, (str, dict)):
        raise CliInputError(f"{context}: 'arch' must be a string or a mapping of host name to string")
    modules = _require_str_list(entry, "modules", context)
    return QtRequirement(version=version, target=target, arch=arch, modules=modules)


def _parse_tool_entry(entry: Any, index: int) -> ToolRequirement:
    context = f"tool[{index}]"
    if not isinstance(entry, dict):
        raise CliInputError(f"{context}: each entry must be a mapping")
    name = _require_str(entry, "name", context)
    target = entry.get("target", "desktop")
    if not isinstance(target, str):
        raise CliInputError(f"{context}: 'target' must be a string")
    variant = entry.get("variant")
    if variant is not None and not isinstance(variant, (str, dict)):
        raise CliInputError(f"{context}: 'variant' must be a string or a mapping of host name to string")
    return ToolRequirement(name=name, target=target, variant=variant)


def _parse_sde_entry(entry: Any, index: int, section: str) -> SdeRequirement:
    context = f"{section}[{index}]"
    if not isinstance(entry, dict):
        raise CliInputError(f"{context}: each entry must be a mapping")
    version = _require_str(entry, "version", context)
    modules = _require_str_list(entry, "modules", context)
    return SdeRequirement(version=version, modules=modules)


def load_requirements(path: Path) -> RequirementsManifest:
    """Parses and validates an aqt-requirements.yml manifest.

    Raises `CliInputError` if the file is missing, is not valid YAML, or fails to match the
    expected schema.
    """
    if not path.is_file():
        raise CliInputError(f"Requirements file not found: '{path}'")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise CliInputError(f"Failed to parse requirements file '{path}': {e}") from e
    if not isinstance(raw, dict):
        raise CliInputError(f"Requirements file '{path}' must contain a mapping of sections at the top level")

    unknown_sections = set(raw) - set(_SECTION_NAMES)
    if unknown_sections:
        raise CliInputError(
            f"Requirements file '{path}' has unknown section(s): {', '.join(sorted(unknown_sections))}. "
            f"Valid sections are: {', '.join(_SECTION_NAMES)}"
        )

    def section(name: str) -> list:
        value = raw.get(name) or []
        if not isinstance(value, list):
            raise CliInputError(f"Requirements file '{path}': section '{name}' must be a list of entries")
        return value

    manifest = RequirementsManifest(
        qt=[_parse_qt_entry(e, i) for i, e in enumerate(section("qt"))],
        tool=[_parse_tool_entry(e, i) for i, e in enumerate(section("tool"))],
        src=[_parse_sde_entry(e, i, "src") for i, e in enumerate(section("src"))],
        doc=[_parse_sde_entry(e, i, "doc") for i, e in enumerate(section("doc"))],
        example=[_parse_sde_entry(e, i, "example") for i, e in enumerate(section("example"))],
    )
    if manifest.is_empty():
        raise CliInputError(f"Requirements file '{path}' does not declare any packages to install")
    return manifest

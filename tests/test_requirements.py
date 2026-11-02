import textwrap
from pathlib import Path

import pytest

from aqt.exceptions import CliInputError
from aqt.requirements import detect_host, load_requirements


def write_manifest(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "aqt-requirements.yml"
    path.write_text(textwrap.dedent(content))
    return path


def test_load_requirements_missing_file(tmp_path):
    with pytest.raises(CliInputError, match="not found"):
        load_requirements(tmp_path / "does-not-exist.yml")


def test_load_requirements_invalid_yaml(tmp_path):
    path = write_manifest(tmp_path, "qt: [this is not: valid: yaml")
    with pytest.raises(CliInputError, match="Failed to parse"):
        load_requirements(path)


def test_load_requirements_empty_manifest(tmp_path):
    path = write_manifest(tmp_path, "qt: []\n")
    with pytest.raises(CliInputError, match="does not declare any packages"):
        load_requirements(path)


def test_load_requirements_unknown_section(tmp_path):
    path = write_manifest(
        tmp_path,
        """
        qt:
          - version: "6.5.3"
            target: desktop
            arch: gcc_64
        bogus_section: []
        """,
    )
    with pytest.raises(CliInputError, match="unknown section"):
        load_requirements(path)


def test_load_requirements_qt_missing_arch(tmp_path):
    path = write_manifest(
        tmp_path,
        """
        qt:
          - version: "6.5.3"
            target: desktop
        """,
    )
    with pytest.raises(CliInputError, match="missing required field 'arch'"):
        load_requirements(path)


def test_load_requirements_full_manifest(tmp_path):
    path = write_manifest(
        tmp_path,
        """
        qt:
          - version: "6.5.3"
            target: desktop
            arch:
              linux: gcc_64
              mac: clang_64
              windows: win64_msvc2019_64
            modules: [qtcharts]
          - version: "6.5.3"
            target: android
            arch: android_arm64_v8a
        tool:
          - name: ninja
            variant:
              linux: qt.tools.ninja
              windows: qt.tools.ninja
          - name: cmake
        src:
          - version: "6.5.3"
        doc:
          - version: "6.5.3"
            modules: [qtcharts]
        example:
          - version: "6.5.3"
        """,
    )
    manifest = load_requirements(path)

    assert len(manifest.qt) == 2
    assert manifest.qt[0].resolved_arch("linux") == "gcc_64"
    assert manifest.qt[0].resolved_arch("windows") == "win64_msvc2019_64"
    assert manifest.qt[0].modules == ["qtcharts"]
    assert manifest.qt[1].resolved_arch("mac") == "android_arm64_v8a"  # plain string applies to every host

    assert len(manifest.tool) == 2
    assert manifest.tool[0].resolved_variant("linux") == "qt.tools.ninja"
    assert manifest.tool[0].target == "desktop"  # default
    assert manifest.tool[1].resolved_variant("linux") is None  # no variant pinned

    assert len(manifest.src) == 1
    assert len(manifest.doc) == 1
    assert manifest.doc[0].modules == ["qtcharts"]
    assert len(manifest.example) == 1


def test_qt_requirement_arch_missing_host_raises(tmp_path):
    path = write_manifest(
        tmp_path,
        """
        qt:
          - version: "6.5.3"
            target: desktop
            arch:
              linux: gcc_64
        """,
    )
    manifest = load_requirements(path)
    with pytest.raises(CliInputError, match="does not define a value for host 'windows'"):
        manifest.qt[0].resolved_arch("windows")


def test_tool_requirement_variant_missing_host_raises(tmp_path):
    path = write_manifest(
        tmp_path,
        """
        tool:
          - name: ninja
            variant:
              linux: qt.tools.ninja
        """,
    )
    manifest = load_requirements(path)
    with pytest.raises(CliInputError, match="does not define a value for host 'windows'"):
        manifest.tool[0].resolved_variant("windows")


def test_detect_host_matches_known_choices():
    from aqt.requirements import HOST_CHOICES

    assert detect_host() in HOST_CHOICES

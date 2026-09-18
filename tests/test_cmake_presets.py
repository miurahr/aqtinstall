import json
from pathlib import Path

from aqt.cmake_presets import generate_cmake_user_presets


def make_kit(base: Path, version: str, arch: str, *, with_toolchain: bool = False) -> Path:
    kit_dir = base / version / arch
    (kit_dir / "bin").mkdir(parents=True, exist_ok=True)
    (kit_dir / "bin" / "qmake6").touch()
    if with_toolchain:
        toolchain_dir = kit_dir / "lib" / "cmake" / "Qt6"
        toolchain_dir.mkdir(parents=True, exist_ok=True)
        (toolchain_dir / "qt.toolchain.cmake").touch()
    return kit_dir


def test_generate_cmake_user_presets_empty_dir(tmp_path):
    preset_path = generate_cmake_user_presets(tmp_path)
    document = json.loads(preset_path.read_text())
    assert document["configurePresets"] == []


def test_generate_cmake_user_presets_finds_kits_and_ignores_non_version_dirs(tmp_path):
    make_kit(tmp_path, "6.5.3", "gcc_64")
    make_kit(tmp_path, "6.5.3", "android_arm64_v8a", with_toolchain=True)
    # Non-Qt-kit directories at the top level (Tools, Src, ...) must never be picked up.
    (tmp_path / "Tools" / "QtCreator" / "bin").mkdir(parents=True)

    preset_path = generate_cmake_user_presets(tmp_path)
    document = json.loads(preset_path.read_text())
    names = {p["name"] for p in document["configurePresets"]}
    assert names == {"qt-6.5.3-gcc_64", "qt-6.5.3-android_arm64_v8a"}

    android_preset = next(p for p in document["configurePresets"] if p["name"] == "qt-6.5.3-android_arm64_v8a")
    assert android_preset["cacheVariables"]["CMAKE_TOOLCHAIN_FILE"].endswith("qt.toolchain.cmake")
    assert "CMAKE_PREFIX_PATH" in android_preset["cacheVariables"]

    gcc_preset = next(p for p in document["configurePresets"] if p["name"] == "qt-6.5.3-gcc_64")
    assert "CMAKE_TOOLCHAIN_FILE" not in gcc_preset["cacheVariables"]


def test_generate_cmake_user_presets_is_regenerated_wholesale(tmp_path):
    make_kit(tmp_path, "6.5.3", "gcc_64")
    preset_path = generate_cmake_user_presets(tmp_path)
    first = json.loads(preset_path.read_text())
    assert len(first["configurePresets"]) == 1

    # Hand-edit the file, as if a developer had touched it -- the next run must still fully
    # overwrite it (it is aqt's own generated artifact, not merged with external edits).
    preset_path.write_text(json.dumps({"version": 6, "configurePresets": [{"name": "hand-written"}]}))

    make_kit(tmp_path, "6.5.4", "gcc_64")
    generate_cmake_user_presets(tmp_path)
    second = json.loads(preset_path.read_text())
    names = {p["name"] for p in second["configurePresets"]}
    assert names == {"qt-6.5.3-gcc_64", "qt-6.5.4-gcc_64"}

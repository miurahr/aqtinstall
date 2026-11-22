import json
import textwrap
from pathlib import Path

from aqt.installer import Cli
from aqt.metadata import ModuleData


def write_manifest(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "aqt-requirements.yml"
    path.write_text(textwrap.dedent(content))
    return path


def make_cli() -> Cli:
    cli = Cli()
    cli._setup_settings()
    return cli


def test_install_requires_requirements_flag(capsys):
    cli = make_cli()
    assert 1 == cli.run(["install"])
    out, err = capsys.readouterr()
    assert "requires --requirements" in err


def test_install_bare_requirements_uses_default_filename(monkeypatch, tmp_path, capsys):
    write_manifest(
        tmp_path,
        """
        qt:
          - version: "6.5.3"
            target: desktop
            arch: gcc_64
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("aqt.requirements.detect_host", lambda: "linux")
    calls = []
    monkeypatch.setattr(Cli, "run_install_qt", lambda self, ns: calls.append(ns))

    cli = make_cli()
    assert 0 == cli.run(["install", "--requirements"])

    assert len(calls) == 1
    assert calls[0].host == "linux"
    assert calls[0].target == "desktop"
    assert calls[0].qt_version_spec == "6.5.3"
    assert calls[0].arch == "gcc_64"


def test_install_explicit_path_dispatches_qt_tool_and_sde_entries(monkeypatch, tmp_path):
    manifest_path = write_manifest(
        tmp_path,
        """
        qt:
          - version: "6.5.3"
            target: desktop
            arch:
              linux: gcc_64
              windows: win64_msvc2019_64
            modules: [qtcharts]
        tool:
          - name: ninja
            variant:
              linux: qt.tools.ninja
        doc:
          - version: "6.5.3"
        """,
    )
    monkeypatch.setattr("aqt.requirements.detect_host", lambda: "linux")

    qt_calls, tool_calls, sde_calls = [], [], []
    monkeypatch.setattr(Cli, "run_install_qt", lambda self, ns: qt_calls.append(ns))
    monkeypatch.setattr(Cli, "run_install_tool", lambda self, ns: tool_calls.append(ns))
    monkeypatch.setattr(Cli, "_run_src_doc_examples", lambda self, kind, ns: sde_calls.append((kind, ns)))

    cli = make_cli()
    assert 0 == cli.run(["install", "--requirements", str(manifest_path)])

    assert len(qt_calls) == 1
    assert qt_calls[0].arch == "gcc_64"  # resolved for the detected 'linux' host
    assert qt_calls[0].modules == ["qtcharts"]

    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "ninja"
    assert tool_calls[0].tool_variant == "qt.tools.ninja"

    assert len(sde_calls) == 1
    assert sde_calls[0][0] == "doc"
    assert sde_calls[0][1].qt_version_spec == "6.5.3"


def test_install_dispatches_src_and_example_entries(monkeypatch, tmp_path):
    manifest_path = write_manifest(
        tmp_path,
        """
        src:
          - version: "6.5.3"
        example:
          - version: "6.5.3"
            modules: [qtcharts]
        """,
    )
    monkeypatch.setattr("aqt.requirements.detect_host", lambda: "linux")
    sde_calls = []
    monkeypatch.setattr(Cli, "_run_src_doc_examples", lambda self, kind, ns: sde_calls.append((kind, ns)))

    cli = make_cli()
    assert 0 == cli.run(["install", "--requirements", str(manifest_path)])

    kinds = {kind for kind, _ in sde_calls}
    assert kinds == {"src", "examples"}  # "examples" (plural) matches _run_src_doc_examples' own flavor convention
    example_ns = next(ns for kind, ns in sde_calls if kind == "examples")
    assert example_ns.modules == ["qtcharts"]


def test_install_tool_variant_missing_for_detected_host_fails_cleanly(monkeypatch, tmp_path, capsys):
    manifest_path = write_manifest(
        tmp_path,
        """
        tool:
          - name: ninja
            variant:
              windows: qt.tools.ninja
        """,
    )
    monkeypatch.setattr("aqt.requirements.detect_host", lambda: "linux")
    tool_calls = []
    monkeypatch.setattr(Cli, "run_install_tool", lambda self, ns: tool_calls.append(ns))

    cli = make_cli()
    assert 1 == cli.run(["install", "--requirements", str(manifest_path)])

    out, err = capsys.readouterr()
    assert "does not define a value for host 'linux'" in err
    assert tool_calls == []


def test_install_host_override_resolves_arch_for_a_different_host(monkeypatch, tmp_path):
    manifest_path = write_manifest(
        tmp_path,
        """
        qt:
          - version: "6.5.3"
            target: desktop
            arch:
              linux: gcc_64
              windows: win64_msvc2019_64
        """,
    )
    # Running "as if" on linux, but overriding to windows for cross-platform staging.
    monkeypatch.setattr("aqt.requirements.detect_host", lambda: "linux")
    qt_calls = []
    monkeypatch.setattr(Cli, "run_install_qt", lambda self, ns: qt_calls.append(ns))

    cli = make_cli()
    assert 0 == cli.run(["install", "--requirements", str(manifest_path), "--host", "windows"])

    assert qt_calls[0].host == "windows"
    assert qt_calls[0].arch == "win64_msvc2019_64"


GPL_DESC = (
    "This component is available under commercial licenses from The Qt Company, or under "
    "GPL v3. For open source use, please note the additional requirements compared to LGPL v3."
)


def test_install_ensure_lgpl_never_installs_and_blocks_on_violation(monkeypatch, tmp_path, capsys):
    manifest_path = write_manifest(
        tmp_path,
        """
        qt:
          - version: "6.5.3"
            target: desktop
            arch: gcc_64
            modules: [qtcharts]
        """,
    )
    monkeypatch.setattr("aqt.requirements.detect_host", lambda: "linux")
    monkeypatch.setattr(
        "aqt.metadata.MetadataFactory.fetch_long_modules",
        lambda self, version, arch: ModuleData({"qtcharts": {"Description": GPL_DESC}}),
    )
    install_calls = []
    monkeypatch.setattr(Cli, "run_install_qt", lambda self, ns: install_calls.append(ns))

    cli = make_cli()
    assert 1 == cli.run(["install", "--requirements", str(manifest_path), "--ensure-lgpl"])

    out, err = capsys.readouterr()
    assert "failed the LGPL/commercial-use check" in err
    assert "not legal advice" in err or "NOT legal advice" in err
    assert install_calls == []  # never installs, pass or fail


def test_install_ensure_lgpl_passes_clean_modules_without_installing(monkeypatch, tmp_path, capsys):
    manifest_path = write_manifest(
        tmp_path,
        """
        qt:
          - version: "6.5.3"
            target: desktop
            arch: gcc_64
            modules: [qtwebengine]
        """,
    )
    monkeypatch.setattr("aqt.requirements.detect_host", lambda: "linux")
    monkeypatch.setattr(
        "aqt.metadata.MetadataFactory.fetch_long_modules",
        lambda self, version, arch: ModuleData({"qtwebengine": {"Description": ""}}),
    )
    install_calls = []
    monkeypatch.setattr(Cli, "run_install_qt", lambda self, ns: install_calls.append(ns))

    cli = make_cli()
    assert 0 == cli.run(["install", "--requirements", str(manifest_path), "--ensure-lgpl"])

    out, err = capsys.readouterr()
    assert "passed the LGPL/commercial-use check" in err
    assert install_calls == []  # verify-only: still never installs, even when clean


def test_install_qt_ensure_lgpl_flag_never_downloads(monkeypatch, capsys):
    monkeypatch.setattr(
        "aqt.metadata.MetadataFactory.fetch_long_modules",
        lambda self, version, arch: ModuleData({"qtcharts": {"Description": GPL_DESC}}),
    )

    def fail_run_installer(*args, **kwargs):
        raise AssertionError("--ensure-lgpl must never download or install anything")

    monkeypatch.setattr("aqt.installer.run_installer", fail_run_installer)

    cli = make_cli()
    assert 1 == cli.run(["install-qt", "linux", "desktop", "6.5.3", "gcc_64", "-m", "qtcharts", "--ensure-lgpl"])
    out, err = capsys.readouterr()
    assert "failed the LGPL/commercial-use check" in err


def test_install_generate_cmake_presets_after_install(monkeypatch, tmp_path):
    manifest_path = write_manifest(
        tmp_path,
        """
        qt:
          - version: "6.5.3"
            target: desktop
            arch: gcc_64
        """,
    )
    monkeypatch.setattr("aqt.requirements.detect_host", lambda: "linux")

    def fake_install_qt(self, ns):
        kit_dir = Path(ns.outputdir) / "6.5.3" / "gcc_64" / "bin"
        kit_dir.mkdir(parents=True)
        (kit_dir / "qmake6").touch()

    monkeypatch.setattr(Cli, "run_install_qt", fake_install_qt)

    output_dir = tmp_path / "Qt"
    cli = make_cli()
    assert 0 == cli.run(
        [
            "install",
            "--requirements",
            str(manifest_path),
            "--outputdir",
            str(output_dir),
            "--generate-cmake-presets",
        ]
    )

    preset_path = output_dir / "CMakeUserPresets.json"
    assert preset_path.is_file()
    document = json.loads(preset_path.read_text())
    assert document["configurePresets"][0]["name"] == "qt-6.5.3-gcc_64"

"""iOS repository layouts and package-name compatibility."""

import pytest

from aqt.archives import QtArchives, TargetConfig, Updates
from aqt.exceptions import CliInputError
from aqt.helper import Settings, effective_package_name
from aqt.installer import Cli
from aqt.metadata import ArchiveId, MetadataFactory, QtRepoProperty, Version
from aqt.updater import Updater


@pytest.fixture(
    params=[("6.11.2", "ios"), *[("6.12.0", f"ios_{s}") for s in ("device", "simulator_arm64", "simulator_x86_64")]]
)
def ios_repository(request, monkeypatch):
    version_text, arch = request.param
    version = Version(version_text)
    digits = version_text.replace(".", "")
    split = version >= Version("6.12.0")
    suffix = arch.removeprefix("ios_") if split else ""
    root = "online/qtsdkrepository/mac_x64"
    folder = f"{root}/ios/qt6_{digits}/qt6_{digits}" + (f"_{suffix}" if split else "")
    ext_root = f"{root}/extensions/qtpdf/{digits}"
    ext_folder = ext_root + ("/61400" if split else "") + f"/{arch}"
    base_name = f"qt.qt6.{digits}." + (f"qtforios.{suffix}" if split else "ios")
    addon_name = f"qt.qt6.{digits}.addons.qt3d.{arch}"
    pdf_name = f"extensions.qtpdf.{digits}." + (f"61400.ios.{suffix}" if split else "ios")

    def package(name, archive):
        return f"""<PackageUpdate><Name>{name}</Name><Version>{version_text}-123</Version>
        <DisplayName>Test package</DisplayName><Description>Test package</Description>
        <ReleaseDate>2026-09-01</ReleaseDate><DownloadableArchives>{archive}-test.7z</DownloadableArchives>
        <UpdateFile CompressedSize="1000000" UncompressedSize="2000000"/>
        <Operations><Operation name="Extract"><Argument>@TargetDir@/{version_text}/{arch}</Argument>
        <Argument>{archive}-test.7z</Argument></Operation></Operations></PackageUpdate>"""

    xmls = {
        folder + "/Updates.xml": "<Updates>" + package(base_name, "qtbase") + package(addon_name, "qt3d") + "</Updates>",
        ext_folder + "/Updates.xml": "<Updates>" + package(pdf_name, "qtpdf") + "</Updates>",
    }
    Settings.load_settings()
    monkeypatch.setattr(QtRepoProperty, "known_extensions", lambda v: {"qtpdf": Version("6.12.0")})

    def fetch(url):
        if url == ext_root + "/":
            assert split
            return '<a href="61400/">61400/</a>'
        assert url in xmls, f"Unexpected repository path: {url}"
        return xmls[url]

    monkeypatch.setattr(MetadataFactory, "fetch_http", lambda self, url, *args: fetch(url))
    monkeypatch.setattr(QtArchives, "_download_update_xml", lambda self, url, *args: fetch(url))
    return version, arch, xmls, base_name, addon_name, pdf_name


def test_ios_module_and_archive_listing(ios_repository):
    version, arch, _, _, _, _ = ios_repository
    factory = MetadataFactory(ArchiveId("qt", "mac", "ios"))
    pdf = "qtpdf@6.140.0" if version >= Version("6.12.0") else "qtpdf"
    assert factory.fetch_modules(version, arch) == ["qt3d", pdf]
    assert set(factory.fetch_long_modules(version, arch).table_data) == {"qt3d", pdf}
    assert factory.fetch_archives(version, arch, []) == ["qtbase"]
    assert factory.fetch_archives(version, arch, ["qt3d"]) == ["qt3d"]
    assert factory.fetch_archives(version, arch, ["all"]) == ["qt3d"]


def test_ios_architecture_listing(monkeypatch):
    Settings.load_settings()
    requested = []

    def fetch(self, url, *args):
        requested.append(url)
        suffix = url.split("/qt6_6120_")[-1].split("/")[0]
        assert suffix in {"device", "simulator_arm64", "simulator_x86_64"}
        return f"""<Updates><PackageUpdate><Name>qt.qt6.6120.qtforios.{suffix}</Name>
        <DownloadableArchives>qtbase.7z</DownloadableArchives>
        <UpdateFile UncompressedSize="2000000"/></PackageUpdate></Updates>"""

    monkeypatch.setattr(MetadataFactory, "fetch_http", fetch)
    factory = MetadataFactory(ArchiveId("qt", "mac", "ios"))
    assert factory.fetch_arches(Version("6.12.0")) == ["ios_device", "ios_simulator_arm64", "ios_simulator_x86_64"]
    assert len(requested) == 3
    assert factory.archive_id.all_extensions(Version("6.11.2")) == [""]


@pytest.mark.parametrize("mode", ["base", "modules", "no_base", "all", "filtered_base"])
def test_ios_install_package_selection(ios_repository, mode):
    version, arch, xmls, base_name, addon_name, pdf_name = ios_repository
    modules = ["qt3d", "qtpdf"] if mode in ("modules", "no_base") else ["all"] if mode == "all" else []
    archives = QtArchives(
        "mac",
        "ios",
        str(version),
        arch,
        Settings.baseurl,
        modules=modules,
        all_extra=mode == "all",
        is_include_base_package=mode != "no_base",
        subarchives=["nonexistent"] if mode == "filtered_base" else None,
    ).get_packages()
    expected = {base_name} if mode == "base" else set() if mode == "filtered_base" else {base_name, addon_name, pdf_name}
    if mode == "no_base":
        expected.remove(base_name)
    assert {p.pkg_update_name for p in archives} == expected
    for package in archives:
        # Repository URLs must retain Qt's original dotted package names.
        assert f"/{package.pkg_update_name}/" in package.archive_path
        folder = package.archive_path.split(f"/{package.pkg_update_name}/")[0]
        assert folder + "/Updates.xml" in xmls
        assert package.archive_install_path == f"{version}/{arch}"
    base_xml = next(xml for url, xml in xmls.items() if "/ios/" in url)
    base = Updates.fromstring(Settings.baseurl, base_xml).get(base_name)
    assert base.arch == arch
    assert base.is_base_package()
    assert base.name == base_name


@pytest.mark.parametrize("arch", ["ios_device", "ios_simulator_arm64", "ios_simulator_x86_64"])
def test_ios_mobile_patching(monkeypatch, tmp_path, arch):
    calls = []
    for method in ("patch_qt_scripts", "patch_target_qt_conf", "patch_qdevice_file"):
        monkeypatch.setattr(Updater, method, lambda self, *args, method=method: calls.append(method))

    def unexpected(*args):
        pytest.fail("iOS must not use desktop patching")

    monkeypatch.setattr(Updater, "make_qtconf", unexpected)
    Updater.update(TargetConfig("6.12.0", "ios", arch, "mac"), tmp_path, "macos")
    assert calls == ["patch_qt_scripts", "patch_target_qt_conf", "patch_qdevice_file"]


@pytest.mark.parametrize(
    "original, expected",
    [
        ("qt.qt6.6120.qtforios.device", "qt.qt6.6120.ios_device"),
        ("extensions.qtpdf.6120.61400.ios.simulator_arm64", "extensions.qtpdf.6120.61400.ios_simulator_arm64"),
        ("qtforios.simulator_x86_64.debug_information", "ios_simulator_x86_64.debug_information"),
        ("qt.qt6.6120.addons.qt3d.ios_device", "qt.qt6.6120.addons.qt3d.ios_device"),
        ("qt.qt6.6112.ios", "qt.qt6.6112.ios"),
        ("otherios.device", "otherios.device"),
        ("ios.device_extra", "ios.device_extra"),
    ],
)
def test_effective_ios_package_name(original, expected):
    assert effective_package_name(original) == expected


@pytest.mark.parametrize("version", ["6.11.2", "6.12.0", "6.13.0"])
def test_ios_default_architecture(version):
    if Version(version) < Version("6.12.0"):
        assert Cli._set_arch(None, "mac", "ios", version) == "ios"
    else:
        with pytest.raises(CliInputError, match="ios_device, ios_simulator_arm64, or ios_simulator_x86_64"):
            Cli._set_arch(None, "mac", "ios", version)
    assert Cli._set_arch("ios_simulator_arm64", "mac", "ios", version) == "ios_simulator_arm64"

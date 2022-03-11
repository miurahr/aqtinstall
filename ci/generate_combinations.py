#!/usr/bin/env python3

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional, Tuple, Union

from jsoncomparison import NO_DIFF, Compare

from aqt.exceptions import ArchiveConnectionError, ArchiveDownloadError
from aqt.helper import Settings, setup_logging
from aqt.metadata import ArchiveId, MetadataFactory, Versions


def is_blacklisted_tool(tool_name: str) -> bool:
    for prefix in ("tools_qt3dstudio_",):
        if tool_name.startswith(prefix):
            return True
    for suffix in ("_preview", "_early_access"):
        if tool_name.endswith(suffix):
            return True
    return False


def iter_archive_ids(
    *,
    category: str,
    hosts: Iterable[str] = ArchiveId.HOSTS,
    targets: Optional[Iterable[str]] = None,
    add_extensions: bool = False,
) -> Generator[ArchiveId, None, None]:
    def iter_extensions() -> Generator[str, None, None]:
        if add_extensions and category == "qt":
            if target == "android":
                yield from ("", "x86_64", "x86", "armv7", "arm64_v8a")
                return
            elif target == "desktop":
                yield from ("wasm", "")
                return
        yield ""

    for host in sorted(hosts):
        use_targets = targets
        if use_targets is None:
            use_targets = ArchiveId.TARGETS_FOR_HOST[host]
        for target in use_targets:
            for ext in iter_extensions():
                yield ArchiveId(category, host, target, ext)


def iter_arches() -> Generator[dict, None, None]:
    logger.info("Fetching arches")
    archive_ids = list(iter_archive_ids(category="qt", add_extensions=True))
    for archive_id in tqdm(archive_ids):
        for version in ("latest", "5.15.2", "5.13.2", "5.9.9"):
            if archive_id.extension == "wasm" and (
                version == "5.9.9" or version == "latest"
            ):
                continue
            if archive_id.target == "android":
                if version == "latest" and archive_id.extension == "":
                    continue
                if version != "latest" and archive_id.extension != "":
                    continue
            for arch_name in MetadataFactory(
                archive_id, architectures_ver=version
            ).getList():
                yield {
                    "os_name": archive_id.host,
                    "target": archive_id.target,
                    "arch": arch_name,
                }


def iter_tool_variants() -> Generator[dict, None, None]:
    for archive_id in iter_archive_ids(category="tools"):
        logger.info("Fetching tool variants for {}".format(archive_id))
        for tool_name in tqdm(sorted(MetadataFactory(archive_id).fetch_tools())):
            if is_blacklisted_tool(tool_name):
                continue
            for tool_variant in MetadataFactory(
                archive_id, tool_name=tool_name
            ).getList():
                yield {
                    "os_name": archive_id.host,
                    "target": archive_id.target,
                    "tool_name": tool_name,
                    "arch": tool_variant,
                }


def iter_qt_minor_groups(
    host: str = "linux", target: str = "desktop"
) -> Generator[Tuple[int, int], None, None]:
    versions: Versions = MetadataFactory(ArchiveId("qt", host, target)).fetch_versions()
    for minor_group in versions:
        v = minor_group[0]
        yield v.major, v.minor


def iter_modules_for_qt_minor_groups(
    host: str = "linux", target: str = "desktop", arch: str = "gcc_64"
) -> Generator[Dict, None, None]:
    logger.info("Fetching qt modules for {}/{}".format(host, target))
    for major, minor in tqdm(list(iter_qt_minor_groups(host, target))):
        yield {
            "qt_version": f"{major}.{minor}",
            "modules": MetadataFactory(
                ArchiveId("qt", host, target), modules_query=(f"{major}.{minor}.0", arch)
            ).getList(),
        }


def list_qt_versions(host: str = "linux", target: str = "desktop") -> List[str]:
    all_versions = list()
    versions: Versions = MetadataFactory(ArchiveId("qt", host, target)).getList()
    for minor_group in versions:
        all_versions.extend([str(ver) for ver in minor_group])
    return all_versions


def merge_records(arch_records) -> List[Dict]:
    all_records: List[Dict] = []
    hashes = set()
    for record in arch_records:
        _hash = record["os_name"], record["target"], record["arch"]
        if _hash not in hashes:
            all_records.append(record)
            hashes.add(_hash)
    for sorting_key in ("arch", "target", "os_name"):
        all_records = sorted(all_records, key=lambda d: d[sorting_key])
    return all_records


def generate_combos(new_archive: List[str]):
    return {
        "qt": merge_records(iter_arches()),
        "tools": list(iter_tool_variants()),
        "modules": list(iter_modules_for_qt_minor_groups()),
        "versions": list_qt_versions(),
        "new_archive": new_archive,
    }


def alphabetize_modules(combos: Dict[str, Union[List[Dict], List[str]]]):
    for i, item in enumerate(combos["modules"]):
        combos["modules"][i]["modules"] = sorted(item["modules"])


def write_combinations_json(
    combos: List[Dict[str, Union[List[Dict], List[str]]]],
    filename: Path,
):
    logger.info(f"Write file {filename}")
    json_text = json.dumps(combos, sort_keys=True, indent=2)
    if filename.write_text(json_text, encoding="utf_8") == 0:
        raise RuntimeError("Failed to write file!")


def main(filename: Path, is_write_file: bool, is_verbose: bool) -> int:
    try:
        expect = json.loads(filename.read_text())
        alphabetize_modules(expect[0])
        actual = [generate_combos(new_archive=expect[0]["new_archive"])]
        diff = Compare().check(expect, actual)

        if is_verbose:
            logger.info("=" * 80)
            logger.info("Program Output:")
            logger.info(json.dumps(actual, sort_keys=True, indent=2))

            logger.info("=" * 80)
            logger.info(f"Comparison with existing '{filename}':")
            logger.info(json.dumps(diff, sort_keys=True, indent=2))
            logger.info("=" * 80)

        if diff == NO_DIFF:
            logger.info(f"{filename} is up to date! No PR is necessary this time!")
            return 0  # no difference
        if is_write_file:
            logger.info(f"{filename} has changed; writing changes to file...")
            write_combinations_json(actual, filename)
            return 0  # File written successfully
        logger.warning(f"{filename} is out of date, but no changes were written")
        return 1  # difference reported

    except (ArchiveConnectionError, ArchiveDownloadError) as e:
        logger.error(format(e))
        return 1


def get_tqdm(disable: bool):
    if disable:
        return lambda x: x

    from tqdm import tqdm as base_tqdm

    return lambda *a: base_tqdm(*a, disable=disable)


if __name__ == "__main__":
    Settings.load_settings()
    setup_logging()
    logger = logging.getLogger("aqt.generate_combos")

    json_filename = Path(__file__).parent.parent / "aqt/combinations.json"

    parser = argparse.ArgumentParser(
        description="Generate combinations.json from download.qt.io, "
        "compare with existing file, and write file to correct differences"
    )
    parser.add_argument(
        "--write",
        help="write to combinations.json if changes detected",
        action="store_true",
    )
    parser.add_argument(
        "--no-tqdm",
        help="disable progress bars (makes CI logs easier to read)",
        action="store_true",
    )
    parser.add_argument(
        "--verbose",
        help="Print a json dump of the new file, and an abbreviated diff with the old file",
        action="store_true",
    )
    args = parser.parse_args()

    tqdm = get_tqdm(args.no_tqdm)

    exit(
        main(filename=json_filename, is_write_file=args.write, is_verbose=args.verbose)
    )

"""Recompute publisher checksums and validate parsed Schneider instances.

A restricted ARC record is a recorded status, not a successful ARC download.
A checksum mismatch or a parser failure exits with status 1.
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from safe_time_evrp.data.checks import validate_instance
from safe_time_evrp.data.hashing import md5_file, sha256_file
from safe_time_evrp.data.paths import kuleuven_dir, manifest_path, schneider_dir
from safe_time_evrp.data.schneider import iter_instance_files, parse_schneider_file


def main() -> None:
    path = manifest_path()
    if not path.exists():
        raise SystemExit("manifest missing; run python -m safe_time_evrp.data.download")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    errors.extend(_check_schneider(manifest))
    errors.extend(_check_arc(manifest))
    errors.extend(_check_kuleuven(manifest))
    report = _parse_report()
    manifest["validation"] = report
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if report["failed_instances"]:
        errors.append(f"parser failures: {report['failed_instances']}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)
    print(
        f"verified Schneider instances={report['instances']} "
        f"customers_total={report['customer_total']} arc_status={manifest['datasets']['evrptw_arc']['download_status']}"
    )


def _check_schneider(manifest: dict) -> list[str]:
    entry = manifest["datasets"]["schneider_evrptw"]
    if entry.get("download_status") != "verified":
        return ["Schneider download status is not verified"]
    archive = schneider_dir() / entry["filename"]
    if sha256_file(archive) != entry["published_sha256"]:
        return ["Schneider archive SHA-256 does not match the publisher hash"]
    if archive.stat().st_size != entry["published_size"]:
        return ["Schneider archive size does not match the publisher size"]
    return []


def _check_arc(manifest: dict) -> list[str]:
    entry = manifest["datasets"]["evrptw_arc"]
    status = entry.get("download_status")
    if status == "verified":
        return []
    if status == "access_restricted":
        if entry.get("files_listed_on_record"):
            return ["ARC marked restricted but the manifest lists files"]
        return []
    return [f"ARC status {status} is not an explicit verified or restricted outcome"]


def _check_kuleuven(manifest: dict) -> list[str]:
    entry = manifest["datasets"]["kuleuven_bev"]
    if entry.get("download_status") != "verified":
        return [f"KU Leuven status is {entry.get('download_status')}: {entry.get('failure')}"]
    for info in entry.get("files", []):
        path = kuleuven_dir() / info["local_name"]
        if not path.exists():
            return [f"missing KU Leuven file {info['local_name']}"]
        if info.get("published_checksum_type", "").upper() == "MD5":
            if md5_file(path) != info["published_checksum"]:
                return [f"MD5 mismatch for {info['local_name']}"]
        if sha256_file(path) != info["sha256"]:
            return [f"SHA-256 changed for {info['local_name']}"]
    return []


def _parse_report() -> dict:
    files = iter_instance_files(schneider_dir() / "extracted")
    by_size: Counter[str] = Counter()
    by_family: Counter[str] = Counter()
    failed: list[str] = []
    customer_total = 0
    examples = []
    for path in files:
        stem = path.stem
        if "C5" in stem:
            by_size["5"] += 1
        elif "C10" in stem:
            by_size["10"] += 1
        elif "C15" in stem:
            by_size["15"] += 1
        elif stem.endswith("_21"):
            by_size["full"] += 1
        else:
            by_size["other"] += 1
        if stem.startswith("rc"):
            by_family["rc"] += 1
        elif stem.startswith("r"):
            by_family["r"] += 1
        elif stem.startswith("c"):
            by_family["c"] += 1
        try:
            instance = parse_schneider_file(path)
            report = validate_instance(instance)
        except Exception as exc:  # parser failures must be visible, not swallowed
            failed.append(f"{stem}: {exc}")
            continue
        if not report["ok"]:
            failed.append(f"{stem}: {report['errors'][:3]}")
            continue
        customer_total += int(report["customers"])
        if stem in {"c101C5", "r101_21", "rc101_21", "c201C10"} or len(examples) < 4:
            if len(examples) < 8:
                examples.append(
                    {
                        "name": stem,
                        "customers": report["customers"],
                        "chargers": report["chargers"],
                        "arcs": report["arcs"],
                        "arcs_exceeding_battery": report["arcs_exceeding_battery"],
                        "battery_capacity": report["battery_capacity"],
                        "load_capacity": report["load_capacity"],
                    }
                )
    return {
        "instances": len(files),
        "by_size_token": dict(by_size),
        "by_family": dict(by_family),
        "customer_total": customer_total,
        "failed_instances": failed,
        "examples": examples,
        "customer_ids_preserved": not failed,
    }


if __name__ == "__main__":
    main()

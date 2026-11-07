"""Download a manageable Amazon Last Mile route subset (unsigned S3)."""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from safe_time_evrp.data.hashing import md5_file, sha256_file

BASE = "https://amazon-last-mile-challenges.s3.us-west-2.amazonaws.com/"
OUT = Path("data/raw/amazon_last_mile/subset")
N_ROUTES = 25


def _get(url: str, dest: Path | None = None, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "safe-time-evrp/0.1"})
    with urllib.request.urlopen(req, timeout=600) as response:
        data = response.read()
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return data


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Stream-parse route IDs from a prefix of training route_data.
    route_key = "almrrc2021/almrrc2021-data-training/model_build_inputs/route_data.json"
    # 40 MiB prefix is enough to collect many RouteIDs.
    chunk = _get(
        BASE + route_key,
        headers={"User-Agent": "safe-time-evrp/0.1", "Range": "bytes=0-41943039"},
    ).decode("utf-8", errors="replace")
    ids = re.findall(r'"(RouteID_[^"]+)"\s*:\s*\{', chunk)
    # unique preserve order
    seen: set[str] = set()
    route_ids = []
    for rid in ids:
        if rid not in seen:
            seen.add(rid)
            route_ids.append(rid)
        if len(route_ids) >= N_ROUTES:
            break
    if len(route_ids) < 5:
        raise SystemExit(f"too few route ids in prefix: {len(route_ids)}")

    # Parse incomplete JSON prefix carefully: extract each route object by brace matching.
    routes: dict[str, dict] = {}
    for rid in route_ids:
        marker = f'"{rid}"'
        start = chunk.find(marker)
        if start < 0:
            continue
        brace = chunk.find("{", start)
        depth = 0
        end = None
        for i, ch in enumerate(chunk[brace:], brace):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        try:
            routes[rid] = json.loads(chunk[brace:end])
        except json.JSONDecodeError:
            continue
    (OUT / "route_data_subset.json").write_text(json.dumps(routes, indent=2), encoding="utf-8")

    # Package data prefix for matching routes.
    pkg_key = "almrrc2021/almrrc2021-data-training/model_build_inputs/package_data.json"
    pkg_chunk = _get(
        BASE + pkg_key,
        headers={"User-Agent": "safe-time-evrp/0.1", "Range": "bytes=0-83886079"},
    ).decode("utf-8", errors="replace")
    packages: dict[str, dict] = {}
    for rid in routes:
        marker = f'"{rid}"'
        start = pkg_chunk.find(marker)
        if start < 0:
            continue
        brace = pkg_chunk.find("{", start)
        depth = 0
        end = None
        for i, ch in enumerate(pkg_chunk[brace:], brace):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        try:
            packages[rid] = json.loads(pkg_chunk[brace:end])
        except json.JSONDecodeError:
            continue
    (OUT / "package_data_subset.json").write_text(json.dumps(packages, indent=2), encoding="utf-8")

    # Travel times: for each route, stops are keys; we synthesize from route stop lat/lon
    # ONLY if travel_times unavailable — plan forbids Euclidean substitute for Amazon.
    # Fetch travel_times entries by scanning a large prefix for our route IDs.
    tt_key = "almrrc2021/almrrc2021-data-training/model_build_inputs/travel_times.json"
    # 200 MiB is heavy; try 80 MiB first and keep whatever routes we find.
    tt_chunk = _get(
        BASE + tt_key,
        headers={"User-Agent": "safe-time-evrp/0.1", "Range": "bytes=0-83886079"},
    ).decode("utf-8", errors="replace")
    travel: dict[str, dict] = {}
    for rid in list(routes):
        marker = f'"{rid}"'
        start = tt_chunk.find(marker)
        if start < 0:
            continue
        brace = tt_chunk.find("{", start)
        depth = 0
        end = None
        for i, ch in enumerate(tt_chunk[brace:], brace):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            continue
        try:
            travel[rid] = json.loads(tt_chunk[brace:end])
        except json.JSONDecodeError:
            continue

    # Keep only routes that have travel times (no Euclidean fallback).
    kept = sorted(set(routes) & set(travel) & set(packages))
    routes = {k: routes[k] for k in kept}
    packages = {k: packages[k] for k in kept}
    travel = {k: travel[k] for k in kept}
    (OUT / "route_data_subset.json").write_text(json.dumps(routes, indent=2), encoding="utf-8")
    (OUT / "package_data_subset.json").write_text(json.dumps(packages, indent=2), encoding="utf-8")
    (OUT / "travel_times_subset.json").write_text(json.dumps(travel, indent=2), encoding="utf-8")

    meta = {
        "n_routes": len(kept),
        "route_ids": kept,
        "files": {
            name: {
                "bytes": (OUT / name).stat().st_size,
                "md5": md5_file(OUT / name),
                "sha256": sha256_file(OUT / name),
            }
            for name in (
                "route_data_subset.json",
                "package_data_subset.json",
                "travel_times_subset.json",
            )
        },
        "note": "Electrification is modeled separately; Amazon routes are not observed EVs.",
    }
    (OUT / "subset_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    if len(kept) < 3:
        raise SystemExit("insufficient Amazon routes with travel times in sampled prefixes")


if __name__ == "__main__":
    main()

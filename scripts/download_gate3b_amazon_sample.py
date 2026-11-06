"""Download a representative Amazon Last Mile sample via unsigned S3 requests."""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

from safe_time_evrp.data.hashing import md5_file, sha256_file

BASE = "https://amazon-last-mile-challenges.s3.us-west-2.amazonaws.com/"
OUT = Path("data/raw/amazon_last_mile")


def head_size(key: str) -> str | None:
    req = urllib.request.Request(BASE + key, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.headers.get("Content-Length")


def download(key: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(BASE + key, timeout=300) as response:
        dest.write_bytes(response.read())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key in [
        "almrrc2021/License.txt",
        "almrrc2021/Readme.txt",
        "almrrc2021/almrrc2021-data-training/model_build_inputs/readme.md",
    ]:
        dest = OUT / Path(key).name
        if key.endswith("readme.md"):
            dest = OUT / "training_readme.md"
        print("get", key, "size", head_size(key))
        download(key, dest)
        print(dest.name, dest.stat().st_size, md5_file(dest), sha256_file(dest))

    for key in [
        "almrrc2021/almrrc2021-data-training/model_build_inputs/route_data.json",
        "almrrc2021/almrrc2021-data-training/model_build_inputs/package_data.json",
        "almrrc2021/almrrc2021-data-training/model_build_inputs/travel_times.json",
    ]:
        print(Path(key).name, "full_size", head_size(key))

    # Representative sample: first 5 MiB of route_data.json (unsigned Range).
    key = "almrrc2021/almrrc2021-data-training/model_build_inputs/route_data.json"
    req = urllib.request.Request(BASE + key, headers={"Range": "bytes=0-5242879"})
    with urllib.request.urlopen(req, timeout=120) as response:
        chunk = response.read().decode("utf-8", errors="replace")
    sample = OUT / "route_data_prefix_5mb.json"
    sample.write_text(chunk, encoding="utf-8")
    match = re.search(r'"(RouteID_[^"]+)"\s*:\s*\{', chunk)
    print("sample_chars", len(chunk), "first_route", match.group(1) if match else None)
    print(sample.name, sample.stat().st_size, md5_file(sample), sha256_file(sample))

    # Same for package windows prefix.
    key = "almrrc2021/almrrc2021-data-training/model_build_inputs/package_data.json"
    req = urllib.request.Request(BASE + key, headers={"Range": "bytes=0-2097151"})
    with urllib.request.urlopen(req, timeout=120) as response:
        chunk = response.read().decode("utf-8", errors="replace")
    sample = OUT / "package_data_prefix_2mb.json"
    sample.write_text(chunk, encoding="utf-8")
    print(sample.name, sample.stat().st_size, md5_file(sample), sha256_file(sample))
    print("snippet", chunk[:200].replace("\n", " "))


if __name__ == "__main__":
    main()

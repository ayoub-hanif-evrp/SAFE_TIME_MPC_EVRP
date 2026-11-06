"""Download and verify EVRP-TW-D from Zenodo (Gate 3B)."""

from __future__ import annotations

import tarfile
import time
import urllib.request
from pathlib import Path

from safe_time_evrp.data.hashing import md5_file, sha256_file
from safe_time_evrp.data.http_util import USER_AGENT

URLS = [
    "https://zenodo.org/records/18529191/files/EVRP-TW-D-B-v1.0.tar.gz?download=1",
    "https://zenodo.org/api/records/18529191/files/EVRP-TW-D-B-v1.0.tar.gz/content",
]
EXPECTED_MD5 = "7cc5ddd617dff8792b167f45ab7e4ed3"
EXPECTED_SIZE = 527733122
DEST = Path("data/raw/evrp_tw_d/EVRP-TW-D-B-v1.0.tar.gz")
EXTRACT = Path("data/raw/evrp_tw_d/extract")


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    partial = DEST.with_suffix(DEST.suffix + ".partial")
    if DEST.exists() and DEST.stat().st_size == EXPECTED_SIZE and md5_file(DEST) == EXPECTED_MD5:
        print("already verified", DEST)
    else:
        last: Exception | None = None
        for attempt in range(10):
            url = URLS[attempt % len(URLS)]
            print("attempt", attempt, url, flush=True)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=7200) as resp, partial.open("wb") as handle:
                    n = 0
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        handle.write(chunk)
                        n += len(chunk)
                        if n % (50 << 20) < (1 << 20):
                            print("bytes", n, flush=True)
                partial.replace(DEST)
                break
            except Exception as exc:  # noqa: BLE001 — download resilience
                last = exc
                print("fail", exc, flush=True)
                time.sleep(min(60, 2**attempt))
        else:
            raise SystemExit(f"download failed: {last}")
        digest = md5_file(DEST)
        print("size", DEST.stat().st_size)
        print("md5", digest)
        print("sha256", sha256_file(DEST))
        if digest != EXPECTED_MD5:
            raise SystemExit(f"MD5 mismatch: {digest} != {EXPECTED_MD5}")
        if DEST.stat().st_size != EXPECTED_SIZE:
            raise SystemExit(f"size mismatch: {DEST.stat().st_size} != {EXPECTED_SIZE}")

    EXTRACT.mkdir(parents=True, exist_ok=True)
    if not any(EXTRACT.iterdir()):
        print("extracting...")
        with tarfile.open(DEST, "r:gz") as archive:
            archive.extractall(EXTRACT)
    print("extract root entries", sorted(p.name for p in EXTRACT.iterdir())[:20])


if __name__ == "__main__":
    main()

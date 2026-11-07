"""Local Gate 3C data verification (set GATE3C_DATA=1)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from safe_time_evrp.data.hashing import md5_file


def main() -> None:
    if os.environ.get("GATE3C_DATA") != "1":
        print("GATE3C_DATA not set; skip")
        return
    evrp = Path("data/raw/evrp_tw_d/EVRP-TW-D-B-v1.0.tar.gz")
    if not evrp.exists() or md5_file(evrp) != "7cc5ddd617dff8792b167f45ab7e4ed3":
        raise SystemExit("EVRP-TW-D archive missing or MD5 mismatch")
    amazon = Path("data/raw/amazon_last_mile/subset/subset_manifest.json")
    if not amazon.exists():
        raise SystemExit("Amazon subset missing; run scripts/download_gate3c_amazon_subset.py")
    print("Gate 3C data OK")


if __name__ == "__main__":
    main()
    sys.exit(0)

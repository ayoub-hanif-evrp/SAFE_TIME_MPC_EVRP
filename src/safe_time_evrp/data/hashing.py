"""File hashes and guarded archive extraction."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(
    archive: Path,
    destination: Path,
    *,
    max_files: int = 100_000,
    max_uncompressed_bytes: int = 4_000_000_000,
) -> dict[str, int | str]:
    """Extract a zip, rejecting traversal and oversized payloads."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    total = 0
    files = 0
    with zipfile.ZipFile(archive) as bundle:
        infos = [info for info in bundle.infolist() if not info.is_dir()]
        if len(infos) > max_files:
            raise RuntimeError(f"{archive.name} has {len(infos)} files; limit is {max_files}")
        for info in infos:
            parts = Path(info.filename).parts
            if info.filename.startswith(("/", "\\")) or ".." in parts or Path(info.filename).is_absolute():
                raise RuntimeError(f"refusing to extract {info.filename}")
            total += info.file_size
            if total > max_uncompressed_bytes:
                raise RuntimeError(f"uncompressed size of {archive.name} exceeds {max_uncompressed_bytes} bytes")
            target = (root / info.filename).resolve()
            if root != target and root not in target.parents:
                raise RuntimeError(f"refusing to extract outside {root}: {info.filename}")
        bundle.extractall(root)
        files = len(infos)
    return {"files": files, "uncompressed_bytes": total, "destination": str(root)}

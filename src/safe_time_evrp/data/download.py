"""Download official benchmark files. Idempotent: verified files are kept.

EVRPTW-ARC is queried from the Zenodo record named by the project brief. If that
record exposes no files, the failure is stored and the Schneider deposit is used
as the operational foundation. Nothing else is renamed to EVRPTW-ARC.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from safe_time_evrp.data.hashing import md5_file, safe_extract, sha256_file
from safe_time_evrp.data.http_util import download_file, fetch_json
from safe_time_evrp.data.paths import arc_dir, kuleuven_dir, manifest_path, project_root, schneider_dir

ZENODO_RECORD = "https://zenodo.org/api/records/22800776"
ZENODO_FILES = "https://zenodo.org/api/records/22800776/files"
MENDELEY = "https://data.mendeley.com/public-api/datasets/h3mrm5dhxw"
MENDELEY_ACCEPT = "application/json"
KULEUVEN = "https://rdr.kuleuven.be/api/datasets/:persistentId/?persistentId=doi:10.48804/8KPDTW"


def main() -> None:
    manifest = {
        "generated_at": _now(),
        "datasets": {
            "evrptw_arc": _zenodo(),
            "schneider_evrptw": _schneider(),
            "kuleuven_bev": _kuleuven(),
        },
    }
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_relativize(manifest), indent=2), encoding="utf-8")
    schneider = manifest["datasets"]["schneider_evrptw"]
    if schneider.get("download_status") != "verified":
        raise SystemExit("Schneider E-VRPTW download is not verified. See data/manifests/source_manifest.json")
    print(path)


def _zenodo() -> dict:
    status, payload = fetch_json(ZENODO_RECORD)
    record: dict = {
        "role": "intended_primary_road_enriched_benchmark",
        "queried_url": ZENODO_RECORD,
        "http_status": status,
        "download_status": "not_downloaded",
        "transformations": [],
    }
    if status != 200 or not isinstance(payload, dict) or "metadata" not in payload:
        record["download_status"] = "metadata_request_failed"
        record["failure"] = payload
        return record
    metadata = payload["metadata"]
    files = payload.get("files") or []
    file_status, file_payload = fetch_json(ZENODO_FILES)
    record.update(
        {
            "title": metadata.get("title"),
            "doi": payload.get("doi") or metadata.get("doi"),
            "version": metadata.get("version"),
            "publication_date": metadata.get("publication_date"),
            "license": (metadata.get("license") or {}).get("id"),
            "access_right": metadata.get("access_right"),
            "creators": [creator.get("name") for creator in metadata.get("creators", [])],
            "files_listed_on_record": files,
            "files_endpoint_status": file_status,
            "download_date": _now(),
        }
    )
    blocked = metadata.get("access_right") == "restricted" or file_status == 403 or not files
    if blocked:
        record["download_status"] = "access_restricted"
        record["failure"] = (
            "Zenodo record 22800776 is published but did not provide downloadable files. "
            f"access_right={metadata.get('access_right')}, files={len(files)}, "
            f"files_endpoint_http={file_status}. No substitute archive was saved as EVRPTW-ARC."
        )
        arc_dir().mkdir(parents=True, exist_ok=True)
        return record
    record["download_status"] = "files_present_but_not_fetched_by_this_version"
    record["failure"] = "The record listed files; this downloader refuses to guess their URLs."
    return record


def _schneider() -> dict:
    status, payload = fetch_json(MENDELEY, accept="application/json")
    entry: dict = {
        "role": "operational_foundation_because_arc_is_restricted",
        "queried_url": MENDELEY,
        "landing_page": "https://data.mendeley.com/datasets/h3mrm5dhxw/1",
        "doi": "10.17632/h3mrm5dhxw.1",
        "http_status": status,
        "download_date": _now(),
        "transformations": ["safe_extract of the official zip; original zip kept"],
    }
    if status != 200 or not isinstance(payload, dict) or "files" not in payload:
        entry["download_status"] = "metadata_request_failed"
        entry["failure"] = payload
        return entry
    licence = payload.get("data_licence") or {}
    files = payload["files"]
    if len(files) != 1:
        entry["download_status"] = "unexpected_file_inventory"
        entry["failure"] = f"expected one archive, found {len(files)}"
        return entry
    file_info = files[0]
    details = file_info["content_details"]
    destination = schneider_dir() / file_info["filename"]
    published = details["sha256_hash"]
    entry.update(
        {
            "title": payload.get("name"),
            "version": payload.get("version"),
            "publication_date": payload.get("publish_date"),
            "authors": [
                f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                for person in payload.get("contributors", [])
            ],
            "license": licence.get("short_name"),
            "license_url": licence.get("url"),
            "filename": file_info["filename"],
            "published_size": details.get("size"),
            "published_sha256": published,
            "download_url_host": "data.mendeley.com",
        }
    )
    if not (destination.exists() and sha256_file(destination) == published):
        download_file(details["download_url"], destination)
    actual = sha256_file(destination)
    size = destination.stat().st_size
    entry["size_bytes"] = size
    entry["sha256"] = actual
    if actual != published or size != details.get("size"):
        entry["download_status"] = "checksum_mismatch"
        entry["failure"] = "downloaded Schneider archive does not match the Mendeley content hash or size"
        return entry
    extracted = schneider_dir() / "extracted"
    marker = extracted / ".sha256"
    if marker.exists() and marker.read_text(encoding="utf-8").strip() == actual and any(extracted.rglob("*.txt")):
        entry["extraction"] = {"status": "skipped_existing_verified_extract"}
    else:
        if extracted.exists():
            # Keep the original zip. Replace only the extract.
            _clear_directory(extracted)
        entry["extraction"] = safe_extract(destination, extracted)
        marker.write_text(actual, encoding="utf-8")
    entry["download_status"] = "verified"
    entry["validation_status"] = "archive_hash_matches_publisher"
    return entry


def _kuleuven() -> dict:
    status, payload = fetch_json(KULEUVEN)
    entry: dict = {
        "role": "energy_calibration_source_not_an_evrp_benchmark",
        "queried_url": KULEUVEN,
        "landing_page": "https://rdr.kuleuven.be/dataset.xhtml?persistentId=doi:10.48804/8KPDTW",
        "doi": "10.48804/8KPDTW",
        "http_status": status,
        "download_date": _now(),
        "transformations": ["safe_extract of the V2 zip; original zip kept; not converted to routing energy"],
        "known_limitations": [
            "This is a high-frequency BEV measurement archive.",
            "It does not describe Schneider customers, Lille arcs, or EVRPTW-ARC routes.",
            "Part 1 does not fit an energy model to these traces.",
        ],
    }
    if status != 200 or not isinstance(payload, dict):
        entry["download_status"] = "metadata_request_failed"
        entry["failure"] = payload
        return entry
    latest = payload["data"]["latestVersion"]
    citation = {
        field["typeName"]: field.get("value")
        for field in latest.get("metadataBlocks", {}).get("citation", {}).get("fields", [])
    }
    entry.update(
        {
            "title": citation.get("title"),
            "version": latest.get("versionNumber"),
            "version_state": latest.get("versionState"),
            "publication_date": latest.get("releaseTime") or payload["data"].get("publicationDate"),
            "license": (latest.get("license") or {}).get("name"),
            "license_uri": (latest.get("license") or {}).get("uri"),
            "authors": [
                author.get("authorName", {}).get("value")
                for author in citation.get("author", [])
                if isinstance(author, dict)
            ],
        }
    )
    files = []
    for item in latest.get("files", []):
        data_file = item.get("dataFile") or item
        checksum = data_file.get("checksum") or {}
        files.append(
            {
                "filename": data_file["filename"],
                "file_id": data_file["id"],
                "size": data_file.get("filesize"),
                "published_checksum": checksum.get("value"),
                "published_checksum_type": checksum.get("type"),
            }
        )
    entry["files"] = []
    kuleuven_dir().mkdir(parents=True, exist_ok=True)
    for info in files:
        safe_name = info["filename"].replace(" ", "_")
        destination = kuleuven_dir() / safe_name
        url = f"https://rdr.kuleuven.be/api/access/datafile/{info['file_id']}"
        published = (info.get("published_checksum") or "").lower()
        checksum_type = (info.get("published_checksum_type") or "").upper()
        if not _checksum_matches(destination, published, checksum_type, info.get("size")):
            download_file(url, destination, timeout=600)
        digest_md5 = md5_file(destination)
        digest_sha = sha256_file(destination)
        file_record = {
            **info,
            "local_name": safe_name,
            "size_bytes": destination.stat().st_size,
            "md5": digest_md5,
            "sha256": digest_sha,
        }
        if checksum_type == "MD5" and digest_md5 != published:
            entry["download_status"] = "checksum_mismatch"
            entry["failure"] = f"{safe_name} MD5 does not match the Dataverse record"
            entry["files"].append(file_record)
            return entry
        if info.get("size") is not None and destination.stat().st_size != info["size"]:
            entry["download_status"] = "checksum_mismatch"
            entry["failure"] = f"{safe_name} size does not match the Dataverse record"
            entry["files"].append(file_record)
            return entry
        entry["files"].append(file_record)
        if safe_name.endswith(".zip"):
            extracted = kuleuven_dir() / "extracted"
            marker = extracted / ".sha256"
            if marker.exists() and marker.read_text(encoding="utf-8").strip() == digest_sha:
                file_record["extraction"] = {"status": "skipped_existing_verified_extract"}
            else:
                if extracted.exists():
                    _clear_directory(extracted)
                file_record["extraction"] = safe_extract(destination, extracted)
                marker.write_text(digest_sha, encoding="utf-8")
    entry["download_status"] = "verified"
    entry["validation_status"] = "publisher_checksums_match"
    return entry


def _checksum_matches(path: Path, published: str, checksum_type: str, size: int | None) -> bool:
    if not path.exists():
        return False
    if size is not None and path.stat().st_size != size:
        return False
    if checksum_type == "MD5" and published:
        return md5_file(path) == published
    if checksum_type == "SHA-256" and published:
        return sha256_file(path) == published
    return False


def _clear_directory(path: Path) -> None:
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            child.rmdir()


def _relativize(value):
    root = project_root().resolve()
    if isinstance(value, dict):
        return {key: _relativize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_relativize(item) for item in value]
    if isinstance(value, str) and "://" not in value:
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                resolved = candidate.resolve()
            except OSError:
                return value
            if resolved == root or root in resolved.parents:
                return resolved.relative_to(root).as_posix()
    return value


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    main()

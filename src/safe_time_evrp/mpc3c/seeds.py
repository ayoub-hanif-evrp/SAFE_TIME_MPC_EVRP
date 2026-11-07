"""Stable, policy-independent experiment seeds (Gate 3E)."""

from __future__ import annotations

import hashlib


def stable_seed(*parts: str, bits: int = 31) -> int:
    """SHA-256-derived non-negative integer seed (stable across processes)."""
    payload = "\0".join(parts).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    value = int.from_bytes(digest[:8], "big")
    mask = (1 << bits) - 1
    return value & mask


def instance_content_hash(instance) -> str:
    """Short content fingerprint for manifests (not a cryptographic claim)."""
    parts = [
        instance.name,
        instance.depot_id,
        f"Q={instance.vehicle_type.battery_capacity}",
        f"r={instance.vehicle_type.consumption_rate}",
        ",".join(instance.customer_ids()),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]

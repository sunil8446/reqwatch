"""Content hashing + schema snapshots for change / drift detection."""
from __future__ import annotations

import hashlib

from .cleaning import normalize_for_hash


def content_hash(title: str, location: str | None, department: str | None, cleaned_text: str) -> str:
    return hashlib.sha256(normalize_for_hash(title, location, department, cleaned_text).encode("utf-8")).hexdigest()


def schema_snapshot(jobs: list[dict]) -> tuple[str, list[str]]:
    """Return (hash, sorted field names) for a board response.

    Uses top-level response keys plus the union of the first 5 jobs' keys.
    Only names are kept -- never values, never payloads.
    """
    names: set[str] = set()
    for job in jobs[:5]:
        if isinstance(job, dict):
            names.update(job.keys())
    ordered = sorted(names)
    digest = hashlib.sha256("|".join(ordered).encode("utf-8")).hexdigest()
    return digest, ordered

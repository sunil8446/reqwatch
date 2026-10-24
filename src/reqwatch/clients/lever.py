"""Lever public postings API (no auth). Returns a bare JSON array.

Always pass an explicit limit and paginate with skip: boards larger than
the limit would otherwise be silently truncated, which the closure logic
would misread as mass closures.
"""
from __future__ import annotations

import os

from ..hashing import schema_snapshot
from ..title_filter import title_keeps
from .base import BoardFetch, RawPosting, get_with_backoff

BASE = "https://api.lever.co/v0/postings"
PAGE = 100


def fetch_board(board_token: str, *, transport=None) -> BoardFetch:
    ua = os.environ.get("REQWATCH_USER_AGENT", "Reqwatch/1.0 (job-market research; portfolio project)")
    jobs: list[dict] = []
    skip = 0
    status = 200
    while True:
        resp = get_with_backoff(f"{BASE}/{board_token}?mode=json&limit={PAGE}&skip={skip}",
                                user_agent=ua, transport=transport)
        status = resp.status_code
        page = resp.json()
        if not isinstance(page, list) or not page:
            break
        jobs.extend(page)
        if len(page) < PAGE:
            break
        skip += PAGE
    listed = len(jobs)
    jobs = [j for j in jobs if title_keeps(j.get("text", ""))]  # filter BEFORE storing
    postings = []
    for job in jobs:
        cats = job.get("categories") or {}
        postings.append(RawPosting(
            source_posting_id=str(job["id"]),
            title=job.get("text", ""),
            location=cats.get("location"),
            department=cats.get("department") or cats.get("team"),
            # Prefer the plain-text field; fall back to HTML description.
            description_raw=job.get("descriptionPlain") or job.get("description") or "",
        ))
    digest, names = schema_snapshot(jobs)
    return BoardFetch(postings=postings, schema_hash=digest, field_names=names,
                      http_status=status, postings_listed=listed)

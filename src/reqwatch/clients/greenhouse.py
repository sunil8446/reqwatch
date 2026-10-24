"""Greenhouse Job Board API (public, unauthenticated). NOT the Harvest API.

List first without content (cheap), then ?content=true only when needed:
Phase 1 fetches content for all postings on a board because SCD2 needs text;
Phase 2 token work builds on the list/content split.
"""
from __future__ import annotations

import os

from ..hashing import schema_snapshot
from .base import BoardFetch, RawPosting, get_with_backoff

BASE = "https://boards-api.greenhouse.io/v1/boards"


def fetch_board(board_token: str, *, transport=None) -> BoardFetch:
    ua = os.environ.get("REQWATCH_USER_AGENT", "Reqwatch/1.0 (job-market research; portfolio project)")
    resp = get_with_backoff(f"{BASE}/{board_token}/jobs?content=true", user_agent=ua, transport=transport)
    data = resp.json()
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    postings = []
    for job in jobs:
        loc = (job.get("location") or {}).get("name")
        depts = job.get("departments") or []
        postings.append(RawPosting(
            source_posting_id=str(job["id"]),
            title=job.get("title", ""),
            location=loc,
            department=depts[0].get("name") if depts else None,
            description_raw=job.get("content") or "",
        ))
    digest, names = schema_snapshot(jobs)
    return BoardFetch(postings=postings, schema_hash=digest, field_names=names, http_status=resp.status_code)

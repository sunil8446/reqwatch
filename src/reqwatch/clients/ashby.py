"""Ashby public posting API (unauthenticated job-board endpoint).

Board names are case-sensitive. workplaceType is authoritative for work
mode (Phase 2 extraction); isRemote is not (Hybrid boards set it true).
"""
from __future__ import annotations

import os

from ..hashing import schema_snapshot
from ..title_filter import title_keeps
from .base import BoardFetch, RawPosting, get_with_backoff

BASE = "https://api.ashbyhq.com/posting-api/job-board"


def fetch_board(board_token: str, *, transport=None, known: dict | None = None) -> BoardFetch:
    ua = os.environ.get("REQWATCH_USER_AGENT", "Reqwatch/1.0 (job-market research; portfolio project)")
    resp = get_with_backoff(f"{BASE}/{board_token}?includeCompensation=true", user_agent=ua, transport=transport)
    data = resp.json()
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    listed = len(jobs)
    postings = []
    for job in jobs:
        if job.get("isListed") is False:
            continue
        if not title_keeps(job.get("title", "")):  # filter BEFORE storing
            continue
        postings.append(RawPosting(
            source_posting_id=str(job["id"]),
            title=job.get("title", ""),
            location=job.get("locationName") or job.get("location"),
            department=job.get("departmentName") or job.get("teamName"),
            description_raw=job.get("descriptionPlain") or job.get("descriptionHtml") or "",
        ))
    digest, names = schema_snapshot(jobs)
    return BoardFetch(postings=postings, schema_hash=digest, field_names=names,
                      http_status=resp.status_code, postings_listed=listed)

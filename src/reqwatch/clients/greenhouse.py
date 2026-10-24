"""Greenhouse Job Board API (public, unauthenticated). NOT the Harvest API.

Two-stage fetch (Sunil's filter-first condition, 2026-10-24):
1. List WITHOUT content -> apply the title filter to titles.
2. Fetch full content ONLY for kept postings, one /jobs/{id} call each.
Non-matching postings are counted (postings_listed) and never fetched or stored.
"""
from __future__ import annotations

import os

from ..hashing import schema_snapshot
from ..title_filter import title_keeps
from .base import BoardFetch, RawPosting, get_with_backoff

BASE = "https://boards-api.greenhouse.io/v1/boards"


def _parse_job(job: dict, content: str) -> RawPosting:
    loc = (job.get("location") or {}).get("name")
    depts = job.get("departments") or []
    return RawPosting(
        source_posting_id=str(job["id"]),
        title=job.get("title", ""),
        location=loc,
        department=depts[0].get("name") if depts else None,
        description_raw=content,
    )


def fetch_board(board_token: str, *, transport=None) -> BoardFetch:
    ua = os.environ.get("REQWATCH_USER_AGENT", "Reqwatch/1.0 (job-market research; portfolio project)")
    resp = get_with_backoff(f"{BASE}/{board_token}/jobs", user_agent=ua, transport=transport)
    data = resp.json()
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    digest, names = schema_snapshot(jobs)

    kept_jobs = [j for j in jobs if title_keeps(j.get("title", ""))]
    postings: list[RawPosting] = []
    for job in kept_jobs:
        detail = get_with_backoff(f"{BASE}/{board_token}/jobs/{job['id']}",
                                   user_agent=ua, transport=transport)
        dj = detail.json()
        postings.append(_parse_job(dj, dj.get("content") or ""))
    return BoardFetch(postings=postings, schema_hash=digest, field_names=names,
                      http_status=resp.status_code, postings_listed=len(jobs))

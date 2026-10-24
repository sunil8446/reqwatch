"""Greenhouse Job Board API (public, unauthenticated). NOT the Harvest API.

Two-stage fetch (Sunil's filter-first condition, 2026-10-24):
1. List WITHOUT content -> apply the title filter to titles.
2. Fetch full content ONLY for kept postings, one /jobs/{id} call each.
Non-matching postings are counted (postings_listed) and never fetched or stored.

Unchanged-skip (2026-10-24): when `known` ({posting_id: (title, updated_at)})
is provided, a kept posting whose title AND updated_at match the stored
state skips its content fetch entirely and is returned flagged unchanged.
That turns daily runs from thousands of content fetches into list calls
plus fetches for only new/changed postings.
"""
from __future__ import annotations

import os

from ..hashing import schema_snapshot
from ..title_filter import title_keeps
from .base import BoardFetch, RawPosting, get_with_backoff

BASE = "https://boards-api.greenhouse.io/v1/boards"


def _loc_dept(job: dict) -> tuple[str | None, str | None]:
    loc = (job.get("location") or {}).get("name")
    depts = job.get("departments") or []
    return loc, (depts[0].get("name") if depts else None)


def fetch_board(board_token: str, *, transport=None, known: dict | None = None) -> BoardFetch:
    ua = os.environ.get("REQWATCH_USER_AGENT", "Reqwatch/1.0 (job-market research; portfolio project)")
    resp = get_with_backoff(f"{BASE}/{board_token}/jobs", user_agent=ua, transport=transport)
    data = resp.json()
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    digest, names = schema_snapshot(jobs)

    known = known or {}
    postings: list[RawPosting] = []
    skipped = 0
    for job in jobs:
        title = job.get("title", "")
        if not title_keeps(title):
            continue
        pid = str(job["id"])
        updated_at = job.get("updated_at")
        loc, dept = _loc_dept(job)
        if known.get(pid) == (title, updated_at) and updated_at is not None:
            postings.append(RawPosting(pid, title, loc, dept, "",
                                       source_updated_at=updated_at, unchanged=True))
            skipped += 1
            continue
        detail = get_with_backoff(f"{BASE}/{board_token}/jobs/{job['id']}",
                                   user_agent=ua, transport=transport)
        dj = detail.json()
        dloc, ddept = _loc_dept(dj)
        postings.append(RawPosting(pid, dj.get("title", title), dloc, ddept,
                                     dj.get("content") or "",
                                     source_updated_at=updated_at))
    return BoardFetch(postings=postings, schema_hash=digest, field_names=names,
                      http_status=resp.status_code, postings_listed=len(jobs),
                      content_fetches_skipped=skipped)

"""Ingestion core: idempotent loads, SCD2 versioning, 2-miss closure,
source-health tracking, schema-drift snapshots, pipeline_runs logging.

Invariants (all covered by tests):
- Re-running with identical board data changes nothing (no new versions,
  no timestamp churn beyond last_seen_at on postings actually seen).
- A new posting_versions row is created ONLY when content_hash changes;
  the previous current version is closed (valid_to) in the same transaction.
- A posting is closed only after it is absent from 2 consecutive
  SUCCESSFUL fetches of its board. A failed fetch never increments misses.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import psycopg

from .cleaning import html_to_cleaned_text
from .clients.base import BoardError, BoardFetch
from .db import database_size_bytes, project_months_until_limit
from .hashing import content_hash

FETCHERS = {}  # ats_type -> callable(board_token) -> BoardFetch, filled by run_pipeline


def register_fetchers() -> dict:
    from .clients import ashby, greenhouse, lever
    return {"greenhouse": greenhouse.fetch_board, "lever": lever.fetch_board, "ashby": ashby.fetch_board}


@dataclass
class RunTotals:
    companies_ok: int = 0
    companies_failed: int = 0
    postings_new: int = 0
    postings_changed: int = 0
    postings_closed: int = 0
    postings_seen: int = 0
    health_alerts: list[str] = field(default_factory=list)
    drift_alerts: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def apply_board(conn: psycopg.Connection, run_id: uuid.UUID, company_id: int,
                fetch: BoardFetch, now: datetime, totals: RunTotals) -> None:
    """Apply one successfully fetched board inside the caller's transaction."""
    seen_ids: set[str] = set()
    for raw in fetch.postings:
        seen_ids.add(raw.source_posting_id)
        cleaned = html_to_cleaned_text(raw.description_raw)
        digest = content_hash(raw.title, raw.location, raw.department, cleaned)
        row = conn.execute(
            "select id, current_hash, status from postings where company_id=%s and source_posting_id=%s",
            (company_id, raw.source_posting_id)).fetchone()
        if row is None:
            posting_id = conn.execute(
                """insert into postings (company_id, source_posting_id, current_hash, first_seen_at, last_seen_at, status)
                   values (%s,%s,%s,%s,%s,'open') returning id""",
                (company_id, raw.source_posting_id, digest, now, now)).fetchone()[0]
            conn.execute(
                """insert into posting_versions (posting_id, version, content_hash, title, location, department, cleaned_text, valid_from, is_current)
                   values (%s,1,%s,%s,%s,%s,%s,%s,true)""",
                (posting_id, digest, raw.title, raw.location, raw.department, cleaned, now))
            totals.postings_new += 1
        else:
            posting_id, old_hash, status = row
            if status == "closed":
                # Reappeared after closure: reopen as a new version.
                conn.execute(
                    "update postings set status='open', closed_at=null, miss_count=0, current_hash=%s, last_seen_at=%s where id=%s",
                    (digest, now, posting_id))
                _new_version(conn, posting_id, digest, raw, cleaned, now)
                totals.postings_changed += 1
            elif digest != old_hash:
                conn.execute("update postings set current_hash=%s, last_seen_at=%s, miss_count=0 where id=%s",
                             (digest, now, posting_id))
                _new_version(conn, posting_id, digest, raw, cleaned, now)
                totals.postings_changed += 1
            else:
                conn.execute("update postings set last_seen_at=%s, miss_count=0 where id=%s", (now, posting_id))
        totals.postings_seen += 1

    # Closure: absent from this successful fetch -> miss_count + 1; close at 2.
    open_rows = conn.execute(
        "select id, source_posting_id, miss_count from postings where company_id=%s and status='open'",
        (company_id,)).fetchall()
    for posting_id, source_id, misses in open_rows:
        if source_id not in seen_ids:
            new_misses = misses + 1
            if new_misses >= 2:
                conn.execute(
                    "update postings set miss_count=%s, status='closed', closed_at=%s where id=%s",
                    (new_misses, now, posting_id))
                conn.execute(
                    "update posting_versions set valid_to=%s where posting_id=%s and is_current",
                    (now, posting_id))
                totals.postings_closed += 1
            else:
                conn.execute("update postings set miss_count=%s where id=%s", (new_misses, posting_id))

    # Schema drift snapshot: store ONLY field names + hash. Alert on change vs previous snapshot.
    prev = conn.execute(
        "select schema_hash from board_schema_snapshots where company_id=%s order by captured_at desc limit 1",
        (company_id,)).fetchone()
    conn.execute(
        "insert into board_schema_snapshots (company_id, run_id, schema_hash, field_names) values (%s,%s,%s,%s)",
        (company_id, run_id, fetch.schema_hash, fetch.field_names))
    if prev is not None and prev[0] != fetch.schema_hash:
        totals.drift_alerts.append(f"company_id={company_id}: schema changed {prev[0][:8]} -> {fetch.schema_hash[:8]}")


def _new_version(conn, posting_id, digest, raw, cleaned, now) -> None:
    conn.execute(
        "update posting_versions set valid_to=%s, is_current=false where posting_id=%s and is_current",
        (now, posting_id))
    next_version = conn.execute(
        "select coalesce(max(version),0)+1 from posting_versions where posting_id=%s", (posting_id,)).fetchone()[0]
    conn.execute(
        """insert into posting_versions (posting_id, version, content_hash, title, location, department, cleaned_text, valid_from, is_current)
           values (%s,%s,%s,%s,%s,%s,%s,%s,true)""",
        (posting_id, next_version, digest, raw.title, raw.location, raw.department, cleaned, now))


def consecutive_errors(conn: psycopg.Connection, company_id: int) -> int:
    rows = conn.execute(
        """select outcome from company_runs where company_id=%s
           order by run_id desc limit 10""", (company_id,)).fetchall()
    # Order by run start time, not uuid: join pipeline_runs for correct ordering.
    rows = conn.execute(
        """select cr.outcome from company_runs cr join pipeline_runs pr on pr.run_id=cr.run_id
           where cr.company_id=%s order by pr.started_at desc limit 10""", (company_id,)).fetchall()
    count = 0
    for (outcome,) in rows:
        if outcome == "error":
            count += 1
        else:
            break
    return count


def run_pipeline(conn: psycopg.Connection, fetchers: dict | None = None) -> tuple[uuid.UUID, RunTotals, dict]:
    fetchers = fetchers or register_fetchers()
    run_id = uuid.uuid4()
    started = _now()
    totals = RunTotals()
    conn.execute(
        "insert into pipeline_runs (run_id, started_at, status) values (%s,%s,'running')", (run_id, started))
    conn.commit()

    companies = conn.execute("select id, name, ats_type, board_token from companies where active order by id").fetchall()
    for company_id, name, ats_type, token in companies:
        now = _now()
        try:
            fetch = fetchers[ats_type](token)
        except BoardError as exc:
            conn.execute(
                "insert into company_runs (run_id, company_id, outcome, http_status, error) values (%s,%s,'error',%s,%s)",
                (run_id, company_id, exc.http_status, str(exc)[:500]))
            conn.commit()
            totals.companies_failed += 1
            if consecutive_errors(conn, company_id) >= 3:
                totals.health_alerts.append(f"{name} ({ats_type}:{token}): 3+ consecutive failed runs")
            continue
        except Exception as exc:  # unexpected: record as error, keep other companies going
            conn.rollback()
            conn.execute(
                "insert into company_runs (run_id, company_id, outcome, error) values (%s,%s,'error',%s)",
                (run_id, company_id, str(exc)[:500]))
            conn.commit()
            totals.companies_failed += 1
            continue
        with conn.transaction():
            apply_board(conn, run_id, company_id, fetch, now, totals)
            conn.execute(
                "insert into company_runs (run_id, company_id, outcome, http_status, postings_seen) values (%s,%s,'ok',%s,%s)",
                (run_id, company_id, fetch.http_status, len(fetch.postings)))
        totals.companies_ok += 1

    size = database_size_bytes(conn)
    prev = conn.execute(
        "select db_size_bytes from pipeline_runs where status='success' and db_size_bytes is not null order by started_at desc limit 1"
    ).fetchone()
    growth = (size - prev[0]) if prev else None
    finished = _now()
    conn.execute(
        """update pipeline_runs set finished_at=%s, status='success', companies_ok=%s, companies_failed=%s,
           postings_new=%s, postings_changed=%s, postings_closed=%s, postings_seen=%s,
           db_size_bytes=%s, db_growth_bytes=%s where run_id=%s""",
        (finished, totals.companies_ok, totals.companies_failed, totals.postings_new,
         totals.postings_changed, totals.postings_closed, totals.postings_seen, size, growth, run_id))
    conn.commit()
    report = {
        "run_id": str(run_id),
        "db_size_bytes": size,
        "db_growth_bytes": growth,
        "projected_months_until_1gb": project_months_until_limit(size, growth),
    }
    return run_id, totals, report

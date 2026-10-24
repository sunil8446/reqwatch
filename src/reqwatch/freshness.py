"""Missing-run detection (Phase 1 addition, Sunil 2026-10-24).

A failed run is visible in pipeline_runs. A MISSING run is not: if the
GitHub Actions schedule silently stops (GitHub disables scheduled
workflows in public repos after 60 days without repo activity, or the
workflow is disabled/broken), no row is ever written. This checker runs
on an independent schedule and fails loudly when the newest successful
run is too old -- or does not exist.

Exit codes: 0 = fresh, 2 = stale/missing (CI turns this into a failed
workflow + GitHub notification; Phase 6 wires Grafana/UptimeRobot).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg

MAX_AGE = timedelta(hours=30)  # daily pipeline + generous cron-delay slack


def last_successful_run_age(conn: psycopg.Connection, now: datetime | None = None) -> timedelta | None:
    now = now or datetime.now(timezone.utc)
    row = conn.execute(
        "select max(finished_at) from pipeline_runs where status='success'").fetchone()
    if row is None or row[0] is None:
        return None
    return now - row[0]


def check_freshness(conn: psycopg.Connection, max_age: timedelta = MAX_AGE,
                    now: datetime | None = None) -> tuple[bool, str]:
    age = last_successful_run_age(conn, now)
    if age is None:
        return False, "MISSING RUN: no successful pipeline run has ever been recorded."
    if age > max_age:
        return False, f"MISSING/STALE RUN: last successful run finished {age} ago (limit {max_age}). " \
                      "Possible silent stop: check whether GitHub disabled the scheduled workflow " \
                      "(auto-disabled after 60 days without repo activity)."
    return True, f"Fresh: last successful run {age} ago (limit {max_age})."


def main() -> int:
    from .db import connect
    with connect() as conn:
        ok, message = check_freshness(conn)
    print(message)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

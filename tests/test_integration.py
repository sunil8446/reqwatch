"""Integration tests against a real throwaway Postgres (pgserver).

Proves the Phase 1 invariants end to end:
- first run inserts postings + version 1
- identical second run changes NOTHING (idempotency)
- a wording change creates exactly version 2 and closes version 1
- a posting missing once stays open; missing twice closes
- a FAILED fetch never increments the miss counter
- freshness checker flags a missing run
"""
from __future__ import annotations

import pytest

pgserver = pytest.importorskip("pgserver")

from reqwatch.clients.base import BoardError, BoardFetch, RawPosting  # noqa: E402
from reqwatch.db import apply_schema  # noqa: E402
from reqwatch.freshness import check_freshness  # noqa: E402
from reqwatch.ingest import run_pipeline  # noqa: E402
import psycopg  # noqa: E402


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    import os
    test_url = os.environ.get("TEST_DATABASE_URL")
    srv = None
    if test_url:
        c = psycopg.connect(test_url)
    else:
        srv = pgserver.get_server(tmp_path_factory.mktemp("pg"))
        c = psycopg.connect(srv.get_uri())
    apply_schema(c)
    c.execute("insert into companies (name, ats_type, board_token) values ('Acme','greenhouse','acme')")
    c.commit()
    yield c
    c.close()
    if srv is not None:
        srv.cleanup()


def fetch_of(*postings: RawPosting, schema_hash="s1", fields=("id", "title")) -> BoardFetch:
    return BoardFetch(postings=list(postings), schema_hash=schema_hash, field_names=list(fields), http_status=200)


P1 = RawPosting("1", "Data Engineer", "Remote", "Data", "<p>Build pipelines in Python</p>")
P2 = RawPosting("2", "ML Engineer", "NYC", "AI", "<p>Train models</p>")


def test_full_lifecycle(conn):
    # Run 1: two new postings
    _, totals, report = run_pipeline(conn, fetchers={"greenhouse": lambda t: fetch_of(P1, P2)})
    assert (totals.postings_new, totals.postings_changed, totals.postings_closed) == (2, 0, 0)
    assert report["db_size_bytes"] > 0

    versions = conn.execute("select count(*) from posting_versions").fetchone()[0]
    assert versions == 2

    # Run 2: identical data -> idempotent, no new versions
    _, totals, _ = run_pipeline(conn, fetchers={"greenhouse": lambda t: fetch_of(P1, P2)})
    assert (totals.postings_new, totals.postings_changed, totals.postings_closed) == (0, 0, 0)
    assert conn.execute("select count(*) from posting_versions").fetchone()[0] == 2

    # Run 3: P1 wording changes -> exactly one new version; P2 missing once -> still open
    p1_changed = RawPosting("1", "Data Engineer", "Remote", "Data", "<p>Build pipelines in Rust</p>")
    _, totals, _ = run_pipeline(conn, fetchers={"greenhouse": lambda t: fetch_of(p1_changed)})
    assert (totals.postings_new, totals.postings_changed, totals.postings_closed) == (0, 1, 0)
    rows = conn.execute(
        """select version, is_current from posting_versions pv join postings p on p.id=pv.posting_id
           where p.source_posting_id='1' order by version""").fetchall()
    assert rows == [(1, False), (2, True)]
    assert conn.execute("select status from postings where source_posting_id='2'").fetchone()[0] == "open"

    # Run 4: board fetch FAILS -> P2 miss counter must NOT move
    def boom(token):
        raise BoardError("HTTP 503", 503)
    _, totals, _ = run_pipeline(conn, fetchers={"greenhouse": boom})
    assert totals.companies_failed == 1
    assert conn.execute("select status, miss_count from postings where source_posting_id='2'").fetchone() == ("open", 1)

    # Run 5: P2 missing a second successful time -> closed, version closed out
    _, totals, _ = run_pipeline(conn, fetchers={"greenhouse": lambda t: fetch_of(p1_changed)})
    assert totals.postings_closed == 1
    assert conn.execute("select status from postings where source_posting_id='2'").fetchone()[0] == "closed"
    assert conn.execute(
        """select valid_to is not null from posting_versions pv join postings p on p.id=pv.posting_id
           where p.source_posting_id='2'""").fetchone()[0] is True

    # Freshness: a successful run just happened -> fresh
    ok, _msg = check_freshness(conn)
    assert ok


def test_freshness_flags_missing_run(conn):
    from datetime import datetime, timedelta, timezone
    future = datetime.now(timezone.utc) + timedelta(hours=100)
    ok, msg = check_freshness(conn, now=future)
    assert not ok and "MISSING" in msg

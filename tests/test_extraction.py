"""Extraction runner tests with a scripted fake provider (no model needed)."""
from __future__ import annotations

import pytest

from reqwatch.db import apply_schema, connect
from reqwatch.extraction.runner import run_extraction
from reqwatch.providers.base import ExtractionOutput, ExtractionResult


class FakeProvider:
    name = "fake"
    prompt_version = "extract-v1"

    def __init__(self, model: str, script: list):
        self.model = model
        self.script = list(script)  # each item: ExtractionResult or ValueError

    def extract(self, cleaned_text, *, retry_hint=None):
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return ExtractionOutput(result=item, input_tokens=100, output_tokens=20, raw_text="{}")


GOOD = ExtractionResult(skills=["Python"], role_family="data_engineering",
                        required_years=3, tech_stack=["dbt"], work_mode="remote")

pytestmark = pytest.mark.usefixtures("pg_dsn")


@pytest.fixture()
def seeded(pg_dsn):
    with connect(pg_dsn) as conn:
        apply_schema(conn)
        conn.execute("truncate extractions, extraction_dead_letters, posting_versions, postings, companies restart identity cascade")
        cid = conn.execute(
            "insert into companies (name, ats_type, board_token) values ('Acme','greenhouse','acme') returning id"
        ).fetchone()[0]
        for i in (1, 2):
            pid = conn.execute(
                """insert into postings (company_id, source_posting_id, current_hash, first_seen_at, last_seen_at)
                   values (%s,%s,'h',now(),now()) returning id""", (cid, str(i))).fetchone()[0]
            conn.execute(
                """insert into posting_versions (posting_id, version, content_hash, title, cleaned_text, valid_from, is_current)
                   values (%s,1,'h','Data Engineer','body text',now(),true)""", (pid,))
        conn.commit()
    return pg_dsn


def test_extract_success_and_idempotent_skip(seeded):
    with connect(seeded) as conn:
        totals = run_extraction(conn, FakeProvider("m1", [GOOD, GOOD]))
        assert (totals.considered, totals.extracted, totals.dead_lettered) == (2, 2, 0)
        assert totals.input_tokens == 200
        totals2 = run_extraction(conn, FakeProvider("m1", []))
        assert totals2.considered == 0 and totals2.skipped_already_extracted == 2
        assert totals2.estimated_input_tokens_saved is None  # no extractions this run to base a mean on


def test_retry_then_success(seeded):
    bad = ValueError("invalid extraction output: nope")
    with connect(seeded) as conn:
        totals = run_extraction(conn, FakeProvider("m1", [bad, GOOD, GOOD]))
        assert totals.retried == 1 and totals.extracted == 2 and totals.dead_lettered == 0


def test_double_failure_dead_letters_with_raw_output(seeded):
    bad1 = ValueError("bad1"); bad1.raw_text = "{oops"
    bad2 = ValueError("bad2"); bad2.raw_text = "{oops2"
    with connect(seeded) as conn:
        totals = run_extraction(conn, FakeProvider("m1", [bad1, bad2, GOOD]))
        assert totals.dead_lettered == 1 and totals.extracted == 1
        row = conn.execute("select error, raw_output, attempts from extraction_dead_letters").fetchone()
        assert row[1] == "{oops2" and row[2] == 2

"""Extraction runner: extracts CURRENT posting versions that have no
extraction yet for (provider, model, prompt_version). One retry with the
validation error as a hint; a second failure goes to the dead-letter table
with the raw model output preserved. Successful extractions store the
provider-reported token counts.

Versioning rule: an unchanged posting is never re-extracted — its existing
extraction stays valid because a new extraction row is keyed to the new
posting version. That is the measured token-saving mechanism; the run
report counts avoided extractions and estimates saved input tokens from
this run's measured mean input tokens (labelled as an estimate).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import psycopg

from ..providers.base import ExtractionProvider


@dataclass
class ExtractionRunTotals:
    considered: int = 0
    extracted: int = 0
    retried: int = 0
    dead_lettered: int = 0
    skipped_already_extracted: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    per_posting_seconds: list[float] = field(default_factory=list)

    @property
    def mean_input_tokens(self) -> float | None:
        return (self.input_tokens / self.extracted) if self.extracted else None

    @property
    def estimated_input_tokens_saved(self) -> int | None:
        mean = self.mean_input_tokens
        if mean is None:
            return None
        return int(self.skipped_already_extracted * mean)


def pending_postings(conn: psycopg.Connection, provider: ExtractionProvider,
                     *, limit: int | None = None, posting_ids: list[int] | None = None,
                     priority_recent_days: int | None = None):
    """Current versions lacking an extraction for this provider/model/prompt.

    Backfill plan (docs/backfill-plan.md): with priority_recent_days set,
    postings first seen within that window come first, newest first;
    the remainder follows. Idempotency makes any interruption resumable.
    """
    q = """
        select pv.posting_id, pv.version, pv.cleaned_text
        from posting_versions pv
        join postings p on p.id = pv.posting_id
        where pv.is_current and p.status = 'open'
          and not exists (
            select 1 from extractions e
            where e.posting_id = pv.posting_id and e.version = pv.version
              and e.provider = %s and e.model = %s and e.prompt_version = %s)
    """
    params: list = [provider.name, provider.model, provider.prompt_version]
    if posting_ids:
        q += " and pv.posting_id = any(%s)"
        params.append(posting_ids)
    if priority_recent_days is not None:
        q += f" order by (p.first_seen_at >= now() - interval '{int(priority_recent_days)} days') desc, p.first_seen_at desc"
    else:
        q += " order by pv.posting_id"
    if limit:
        q += " limit %s"
        params.append(limit)
    return conn.execute(q, params).fetchall()


def already_extracted_count(conn: psycopg.Connection, provider: ExtractionProvider) -> int:
    return conn.execute(
        """select count(*) from posting_versions pv
           join postings p on p.id = pv.posting_id
           where pv.is_current and p.status = 'open' and exists (
             select 1 from extractions e where e.posting_id = pv.posting_id
               and e.version = pv.version and e.provider = %s and e.model = %s
               and e.prompt_version = %s)""",
        (provider.name, provider.model, provider.prompt_version)).fetchone()[0]


def extract_one(conn, provider: ExtractionProvider, posting_id: int, version: int,
                cleaned_text: str, totals: ExtractionRunTotals) -> None:
    import time
    start = time.monotonic()
    raw_text = None
    try:
        out = provider.extract(cleaned_text)
    except ValueError as first_exc:
        totals.retried += 1
        raw_text = getattr(first_exc, "raw_text", None)
        try:
            out = provider.extract(cleaned_text, retry_hint=str(first_exc)[:300])
        except ValueError as second_exc:
            raw_text = getattr(second_exc, "raw_text", raw_text)
            conn.execute(
                """insert into extraction_dead_letters
                   (posting_id, version, provider, model, prompt_version, error, raw_output, attempts)
                   values (%s,%s,%s,%s,%s,%s,%s,2)""",
                (posting_id, version, provider.name, provider.model,
                 provider.prompt_version, str(second_exc)[:1000], raw_text))
            conn.commit()
            totals.dead_lettered += 1
            totals.per_posting_seconds.append(time.monotonic() - start)
            return
    conn.execute(
        """insert into extractions (posting_id, version, provider, model, prompt_version,
           extracted_json, input_tokens, output_tokens)
           values (%s,%s,%s,%s,%s,%s,%s,%s)
           on conflict (posting_id, version, provider, model, prompt_version) do nothing""",
        (posting_id, version, provider.name, provider.model, provider.prompt_version,
         json.dumps(out.result.model_dump()), out.input_tokens, out.output_tokens))
    conn.commit()
    totals.extracted += 1
    totals.input_tokens += out.input_tokens or 0
    totals.output_tokens += out.output_tokens or 0
    totals.per_posting_seconds.append(time.monotonic() - start)


def run_extraction(conn: psycopg.Connection, provider: ExtractionProvider,
                   *, limit: int | None = None, posting_ids: list[int] | None = None,
                   priority_recent_days: int | None = None) -> ExtractionRunTotals:
    totals = ExtractionRunTotals()
    totals.skipped_already_extracted = already_extracted_count(conn, provider)
    rows = pending_postings(conn, provider, limit=limit, posting_ids=posting_ids,
                            priority_recent_days=priority_recent_days)
    totals.considered = len(rows)
    for posting_id, version, cleaned_text in rows:
        extract_one(conn, provider, posting_id, version, cleaned_text, totals)
    return totals

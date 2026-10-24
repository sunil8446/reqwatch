"""CLI entrypoint: python -m reqwatch.run_pipeline

Seeds companies from seed/seed_companies.csv (only rows Sunil has approved:
verification_status starting with 'approved'), applies the schema, runs one
ingestion pass, and prints the run report including Neon DB size and the
projected months until the 1 GB free-tier limit.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .db import apply_schema, connect
from .ingest import run_pipeline

SEED_PATH = Path(__file__).resolve().parents[2] / "seed" / "seed_companies.csv"


def seed_companies(conn) -> int:
    if not SEED_PATH.exists():
        return 0
    inserted = 0
    with SEED_PATH.open() as fh:
        for row in csv.DictReader(fh):
            if not row.get("verification_status", "").startswith("approved"):
                continue
            cur = conn.execute(
                """insert into companies (name, ats_type, board_token) values (%s,%s,%s)
                   on conflict (ats_type, board_token) do nothing""",
                (row["company_name"], row["ats_type"], row["board_token"]))
            inserted += cur.rowcount
    conn.commit()
    return inserted


def main() -> int:
    with connect() as conn:
        apply_schema(conn)
        seeded = seed_companies(conn)
        run_id, totals, report = run_pipeline(conn)
    print(json.dumps({
        "seeded_companies": seeded,
        **report,
        "companies_ok": totals.companies_ok,
        "companies_failed": totals.companies_failed,
        "postings_new": totals.postings_new,
        "postings_changed": totals.postings_changed,
        "postings_closed": totals.postings_closed,
        "postings_seen": totals.postings_seen,
        "health_alerts": totals.health_alerts,
        "drift_alerts": totals.drift_alerts,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

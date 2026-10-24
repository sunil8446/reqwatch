# Reqwatch

Job-market intelligence from public ATS job boards (Greenhouse, Lever, Ashby):
incremental, idempotent ingestion with SCD2 posting history, LLM extraction
with measured evals, dbt marts, a typed API, and a public analytics dashboard.

**Scale:** not measured yet (populated from `pipeline_runs` after the first
production runs; see `bench/last_run.json`).

## Architecture (Phase 1 state)

```
Greenhouse / Lever / Ashby public job-board APIs (no auth)
        |  daily GitHub Actions cron, backoff + jitter, descriptive UA
        v
Ingestion (Python 3.12): clean (HTML -> text) -> hash -> SCD2 diff -> Postgres (Neon Free)
        |  pipeline_runs + company_runs + schema snapshots per run
        v
Freshness checker (separate 6h workflow) — alerts on failed AND missing runs
```

Phases: 1 ingestion (this) · 2 extraction + labeling · 3 dbt · 4 API/alerts ·
5 frontend/dashboard · 6 SLOs/Terraform/CI gating · 7 docs/demo.

## Key design rules
- **Idempotent:** re-running a day with identical board data changes nothing.
- **SCD2:** a new `posting_versions` row exists only when the content hash changes.
- **Closure:** a posting closes only after missing 2 consecutive *successful*
  board fetches — one flaky fetch never closes anything.
- **Storage:** `posting_versions` stores **cleaned text only**. No raw HTML or
  raw JSON payloads are stored in Postgres. Drift detection keeps only sorted
  field names + their hash per board per run.
- **Capacity:** every run records DB size + growth and projects months until
  Neon's 1 GB free-tier limit at the measured growth rate.
- **Costs:** $0 stack. Anything that would cost money or need a payment
  method requires explicit per-item approval (see project brief).

## Known limitation: Render cold starts
The API (Phase 4) will run on Render Free, which spins down after ~15 min
idle; the next request pays a cold start. **We do not use keep-alive pings.**
The API availability/latency SLO is defined on warm requests, and cold-start
latency is measured and reported separately (see `docs/slo.md`).

## Setup
1. Create a Neon Free project; copy its pooled connection string.
2. Add GitHub Actions secrets/variables exactly as listed in `docs/secrets.md`
   (Phase 1 needs one secret: `DATABASE_URL`).
3. Locally: `cp .env.example .env`, fill in `DATABASE_URL`,
   `pip install -e ".[dev]"`, `python -m reqwatch.run_pipeline`.
4. Review `seed/seed_companies.csv`: only rows whose `verification_status`
   starts with `approved` are loaded. Edit after the sweep report.

Seed verification sweep (2026-10-24): **98 of 150 boards verified** and
loaded active (67 on the ATS as listed + 31 found on another ATS and
reassigned); 6 boards verified real but currently listing 0 jobs (loaded
inactive); 46 not found on Greenhouse/Lever/Ashby (dropped).

## Tests
`python -m pytest -q` — unit tests plus an integration suite that runs the
full pipeline twice against a throwaway Postgres to prove idempotency,
SCD2 change handling, and 2-miss closure.

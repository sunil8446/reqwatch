# REQWATCH SLOs

Defined in Phase 1; monitoring/alert wiring completes in Phase 6.
Every SLO is measured from `pipeline_runs` / `company_runs` queries or the
bench scripts in `/bench` — never estimated.

## Pipeline success (SLO-P1)
- Definition: a daily run row in `pipeline_runs` with `status='success'`.
- Target: ≥ 95% of days in a rolling 30-day window (denominator: calendar days).
- Alert: freshness-check failure (below) or a run with `status='failed'`.

## Data freshness, including MISSING runs (SLO-F1)
- Definition: age of the newest `pipeline_runs.finished_at` where `status='success'`.
- Target: < 30 hours at every check (checks run every 6 hours).
- A missing run produces no row, so this SLO is checked by an independent
  workflow (`.github/workflows/freshness-check.yml`), not by the pipeline itself.
- Known silent-stop cause: **GitHub disables scheduled workflows in public
  repos after 60 days without repo activity.** Mitigations: (1) the pipeline
  commits its own run report (`bench/last_run.json`, numbers only) each run,
  which counts as repo activity; (2) the freshness checker fails loudly if
  runs stop anyway; (3) if the checker itself goes silent, UptimeRobot
  (Phase 6) watches the public dashboard/API health endpoint as an outside
  witness.

## Source health (SLO-S1)
- Alert when a company board errors on 3 consecutive runs (`company_runs`),
  or when its schema snapshot hash changes (drift). Tracked per run;
  denominator: active companies.

## API availability & latency (SLO-A1) — applies from Phase 4
- Host: Render Free. **No keep-alive pings are used** (decision 2026-10-24):
  the service spins down after ~15 min idle and the next request pays a
  cold start (~60 s class; measured value to be reported from Phase 4 logs,
  not assumed).
- Availability and latency SLOs are therefore defined on **warm requests
  only** (requests arriving while the service is already up).
- Cold-start latency is measured and reported **separately** in the README
  and Phase reports, with its denominator (number of cold starts observed).
- Target (warm): 99% of warm requests < 800 ms over a rolling 30 days.
  Status until Phase 4: not measured yet.

## Database capacity (SLO-D1)
- Neon Free limit: 1 GB per project.
- Every pipeline run records `db_size_bytes` and `db_growth_bytes` in
  `pipeline_runs` and prints projected months until 1 GB at the observed
  per-run growth. Projection shows "not measured yet" until a successful
  run has a predecessor to diff against, and is recomputed each run —
  it is a measured-rate projection, not a guarantee.
- Alert threshold: projection < 2 months, or size > 800 MB.

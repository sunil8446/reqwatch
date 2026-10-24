# Extraction Backfill Plan (Sunil's amendment, 2026-10-24)

Order of work once the eval sets the model route:

1. **Priority subset first:** postings whose `first_seen_at` is within the
   last 30 days, newest first. (The runner's pending query orders by
   first_seen_at desc when priority mode is on.)
2. **Then the remainder**, oldest boards' postings in posting_id order,
   resumable at any point — extraction is idempotent per
   (posting, version, provider, model, prompt_version), so an interrupted
   backfill simply continues where it stopped.

## If sharded on GitHub Actions
- The model (~2 GB for 3B / ~4.7 GB for 7B GGUF) is **cached between jobs**
  with actions/cache keyed by model name + quant; jobs never re-download
  unless the key changes.
- **Modest parallelism:** at most 4 concurrent shard jobs, each handling a
  disjoint posting_id range. Total request volume stays within ordinary
  use of a personal account on a public repo; shards exist to shorten
  wall-clock, not to maximize throughput.
- Each shard writes extractions directly to Neon (DATABASE_URL secret);
  no artifacts carry posting data.
- Daily-delta extraction remains a separate path governed by the Phase 2
  rule: CI 3B only if it passes the post-labeling eval threshold,
  otherwise local.

"""CLI: run extraction over pending current versions.

Env: DATABASE_URL, REQWATCH_EXTRACT_MODEL (e.g. qwen2.5:7b), OLLAMA_HOST,
optional REQWATCH_EXTRACT_LIMIT. Prints a JSON run report (numbers only).
"""
from __future__ import annotations

import json
import os
import statistics

from .db import apply_schema, connect
from .extraction.runner import run_extraction
from .providers.ollama import OllamaProvider


def main() -> int:
    model = os.environ.get("REQWATCH_EXTRACT_MODEL", "qwen2.5:7b")
    limit = int(os.environ["REQWATCH_EXTRACT_LIMIT"]) if os.environ.get("REQWATCH_EXTRACT_LIMIT") else None
    provider = OllamaProvider(model)
    with connect() as conn:
        apply_schema(conn)
        totals = run_extraction(conn, provider, limit=limit)
    secs = totals.per_posting_seconds
    print(json.dumps({
        "provider": provider.name, "model": provider.model,
        "prompt_version": provider.prompt_version,
        "considered": totals.considered,
        "extracted": totals.extracted,
        "retried": totals.retried,
        "dead_lettered": totals.dead_lettered,
        "skipped_already_extracted": totals.skipped_already_extracted,
        "input_tokens": totals.input_tokens,
        "output_tokens": totals.output_tokens,
        "mean_input_tokens": totals.mean_input_tokens,
        "estimated_input_tokens_saved": totals.estimated_input_tokens_saved,
        "mean_seconds_per_posting": round(statistics.mean(secs), 2) if secs else None,
        "median_seconds_per_posting": round(statistics.median(secs), 2) if secs else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

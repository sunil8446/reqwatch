"""Measure extraction validity + speed of a local Ollama model on REAL
postings from the labeling corpus (label_sample.csv: a stratified sample
of production postings). Uses the production provider + prompt.

Reports, per model: n, schema-valid count on FIRST attempt (the provider's
constrained decoding either yields a valid ExtractionResult or raises),
mean/median seconds, token counts as reported by Ollama.

Usage:
  REQWATCH_BENCH_MODEL=qwen2.5:3b REQWATCH_BENCH_CSV=label_sample.csv \
    python bench/measure_extraction_speed.py [n_postings] [start_offset]
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reqwatch.providers.ollama import OllamaProvider  # noqa: E402


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    model = os.environ.get("REQWATCH_BENCH_MODEL", "qwen2.5:3b")
    csv_path = os.environ.get("REQWATCH_BENCH_CSV", "label_sample.csv")
    with open(csv_path) as fh:
        rows = list(csv.DictReader(fh))[offset:offset + n]
    provider = OllamaProvider(model)
    results = []
    for r in rows:
        start = time.monotonic()
        try:
            out = provider.extract(r["cleaned_text"])
            results.append({"posting_id": r["posting_id"], "title": r["title"],
                            "chars": len(r["cleaned_text"]), "ok": True,
                            "seconds": round(time.monotonic() - start, 2),
                            "input_tokens": out.input_tokens, "output_tokens": out.output_tokens})
        except Exception as exc:
            results.append({"posting_id": r["posting_id"], "title": r["title"],
                            "chars": len(r["cleaned_text"]), "ok": False,
                            "seconds": round(time.monotonic() - start, 2),
                            "error": str(exc)[:160]})
        print(f"[{len(results)}/{len(rows)}] ok={results[-1]['ok']} {results[-1]['seconds']}s", flush=True)
    secs = [r["seconds"] for r in results if r["ok"]]
    summary = {
        "model": model, "prompt_version": provider.prompt_version,
        "constrained_decoding": "json_schema_via_format_parameter",
        "postings_measured": len(results),
        "valid_first_attempt": sum(1 for r in results if r["ok"]),
        "mean_seconds": round(statistics.mean(secs), 2) if secs else None,
        "median_seconds": round(statistics.median(secs), 2) if secs else None,
        "rows": results,
    }
    out_path = os.environ.get("REQWATCH_BENCH_OUT")
    if out_path:
        with open(out_path, "w") as fh:
            json.dump(summary, fh, indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""LLM extraction provider interface (Phase 2 implements this; defined in
Phase 1 so the Phase 2 rule Sunil set on 2026-10-24 is encoded in the repo):

- The local 7B model (Ollama) runs the one-time backfill.
- The CI 3B model runs the daily delta ONLY if it passes the eval threshold
  set after hand-labeling; otherwise daily extraction runs locally too.
- Muse subscription tokens are NOT usable as an external API (Phase 0).
  The Meta Model API provider stays a disabled stub until a per-item cost
  approval exists.
"""
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class ExtractionResult(BaseModel):
    skills: list[str]
    seniority: str | None = None
    role_family: str
    required_years: int | None = None
    tech_stack: list[str] = []
    work_mode: str | None = None
    location: str | None = None


class ExtractionProvider(Protocol):
    name: str
    model: str
    prompt_version: str

    def extract(self, cleaned_text: str) -> ExtractionResult: ...
    def count_tokens(self, text: str) -> int: ...

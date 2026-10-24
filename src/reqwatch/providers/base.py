"""LLM extraction provider interface + the Phase 2 routing rule Sunil set
on 2026-10-24, encoded in the repo:

- The local 7B model (Ollama) runs the one-time backfill.
- The CI 3B model runs the daily delta ONLY if it passes the eval threshold
  set after hand-labeling; otherwise daily extraction runs locally too.
- Muse subscription tokens are NOT usable as an external API (Phase 0).
  The Meta Model API provider stays a disabled stub until a per-item cost
  approval exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, Field

RoleFamily = Literal[
    "data_engineering", "analytics_engineering", "data_science", "ml_ai",
    "software_engineering", "infrastructure_devops", "other",
]
Seniority = Literal["intern", "junior", "mid", "senior", "staff_plus", "leadership"]
WorkMode = Literal["remote", "hybrid", "onsite"]


class ExtractionResult(BaseModel):
    """Strict extraction schema. Anything the model returns that does not
    validate against this is a failed extraction (one retry, then dead-letter)."""
    skills: list[str] = Field(default_factory=list)
    seniority: Seniority | None = None
    role_family: RoleFamily
    required_years: int | None = None
    tech_stack: list[str] = Field(default_factory=list)
    work_mode: WorkMode | None = None
    location: str | None = None


@dataclass
class ExtractionOutput:
    result: ExtractionResult
    input_tokens: int | None  # as reported by the provider; None if unreported
    output_tokens: int | None
    raw_text: str  # model's raw reply, kept for dead-letter/debug only, never stored on success paths beyond the row


class ExtractionProvider(Protocol):
    name: str
    model: str
    prompt_version: str

    def extract(self, cleaned_text: str, *, retry_hint: str | None = None) -> ExtractionOutput: ...

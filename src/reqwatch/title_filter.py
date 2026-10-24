"""Rule-based title filter — applied to the LIST response BEFORE any
content fetch or storage (Sunil's condition, 2026-10-24).

Keeps tech / data / AI / infra roles. Non-matching postings are counted
(postings_listed vs postings_kept_by_filter per board per run), never stored.
The keep-rate is a measured pipeline output, reported per run.

FILTER_VERSION is bumped whenever these rules change so keep-rates are
never compared across different rule sets without knowing it.
"""
from __future__ import annotations

import re

FILTER_VERSION = "title-filter-v1"

# Any of these (substring, case-insensitive) keeps a title...
INCLUDE = [
    "engineer", "developer", "software", "programmer",
    "data", "analytics", "analyst", "scientist",
    "machine learning", "ml ", " ml", "ai ", " ai", "artificial intelligence",
    "deep learning", "nlp", "computer vision", "llm",
    "infrastructure", "platform", "devops", "sre", "site reliability",
    "backend", "back-end", "frontend", "front-end", "full stack", "full-stack",
    "cloud", "security", "cybersecurity", "infosec",
    "ios", "android", "mobile",
    "qa", "quality assurance", "sdet", "test automation",
    "network", "systems", "database", "etl", "business intelligence",
    "architect", "robotics", "embedded", "firmware", "hardware engineer",
    "research engineer", "research scientist", "applied scientist",
    "quantitative", "compiler", "kernel", "distributed systems",
]

# ...unless any of these matches (exclude wins). These cut the classic
# false positives: commercial, people, finance, legal, support, design, PM.
EXCLUDE = [
    "sales", "account executive", "account manager", "account lead",
    "account specialist", "customer success", "customer support",
    "technical support", "support specialist", "data entry",
    "recruiter", "recruiting", "talent acquisition", "talent partner",
    "marketing", "brand", "communications", "public relations",
    "legal", "counsel", "paralegal", "compliance analyst",
    "accountant", "accounting", "accounts payable", "accounts receivable",
    "finance", "financial analyst", "fp&a", "payroll", "bookkeeper",
    "human resources", "people operations", "people partner", "hr ",
    "administrative", "executive assistant", "office manager",
    "product manager", "program manager", "project manager",
    "product designer", "ux designer", "ui designer", "graphic designer",
    "designer", "writer", "editor", "content strategist",
    "operations manager", "operations specialist", "supply chain",
    "manufacturing", "technician", "mechanic", "welder", "machinist",
    "inspector", "assembler", "plumber", "electrician",
    "driver", "warehouse", "logistics", "procurement", "buyer",
    "chef", "cook", "barista", "janitor", "custodian",
    "nurse", "physician", "clinical", "therapist", "pharmacist",
    "teacher", "instructor", "tutor",
    "intern ", " intern", "internship",
]

_INCLUDE_RE = [re.compile(re.escape(pat)) for pat in INCLUDE]
_EXCLUDE_RE = [re.compile(re.escape(pat)) for pat in EXCLUDE]


def _norm(title: str) -> str:
    return f" {title.casefold().strip()} "


def title_keeps(title: str) -> bool:
    t = _norm(title)
    if any(p.search(t) for p in _EXCLUDE_RE):
        # 'support engineer' is excluded above, but a real engineering title
        # that merely contains an excluded word inside a longer tech phrase
        # is still cut: exclude wins, deliberately (precision over recall
        # for v1; the eval in Phase 3 will measure what this costs).
        return False
    return any(p.search(t) for p in _INCLUDE_RE)

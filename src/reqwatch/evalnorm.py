"""Term normalization for eval scoring (Sunil's rule, 2026-10-24).

Labels and model output keep the posting's own names verbatim; the alias
map is applied ONLY at scoring time so that e.g. "Postgres" in a label and
"PostgreSQL" in a prediction score as the same term. Matching is
case-insensitive and trims/collapses whitespace.
"""
from __future__ import annotations

# canonical -> aliases (all compared case-insensitively)
ALIASES: dict[str, list[str]] = {
    "postgresql": ["postgres", "psql"],
    "kubernetes": ["k8s"],
    "javascript": ["js", "ecmascript"],
    "typescript": ["ts"],
    "amazon web services": ["aws"],
    "google cloud platform": ["gcp", "google cloud"],
    "microsoft azure": ["azure"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "natural language processing": ["nlp"],
    "large language model": ["llm", "large language models"],
    "continuous integration": ["ci"],
    "continuous integration/continuous delivery": ["ci/cd", "cicd"],
    "structured query language": ["sql"],
    "amazon s3": ["s3"],
    "amazon ec2": ["ec2"],
    "google bigquery": ["bigquery"],
    "apache spark": ["spark", "pyspark"],
    "apache kafka": ["kafka"],
    "apache airflow": ["airflow"],
    "visual studio code": ["vs code", "vscode"],
    "node.js": ["nodejs", "node"],
    "react": ["react.js", "reactjs"],
}

_LOOKUP: dict[str, str] = {}
for canonical, aliases in ALIASES.items():
    _LOOKUP[canonical] = canonical
    for a in aliases:
        _LOOKUP[a] = canonical


def normalize_term(term: str) -> str:
    t = " ".join(term.strip().casefold().split())
    return _LOOKUP.get(t, t)


def normalize_set(items) -> set[str]:
    return {normalize_term(x) for x in items if str(x).strip()}

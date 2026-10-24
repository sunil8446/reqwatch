"""Extraction prompt. PROMPT_VERSION is stored on every extraction row;
any change to this text MUST bump the version (CI eval gating compares
accuracy per prompt_version)."""
from __future__ import annotations

PROMPT_VERSION = "extract-v1"

SYSTEM = """You extract structured fields from a job posting. Reply with ONE JSON object and nothing else.
Fields:
- skills: array of specific skills the posting requires or strongly prefers (e.g. "Python", "dbt", "Spark"). Max 15.
- seniority: one of "intern","junior","mid","senior","staff_plus","leadership", or null if not stated or unclear.
- role_family: one of "data_engineering","analytics_engineering","data_science","ml_ai","software_engineering","infrastructure_devops","other".
- required_years: minimum years of experience as an integer, or null if not stated. Use the lowest number when a range is given.
- tech_stack: array of tools, languages, platforms named in the posting. Max 15.
- work_mode: one of "remote","hybrid","onsite", or null if not stated.
- location: primary work location as written, or null.
Do not invent values. If a field is not supported by the text, use null or an empty array."""


def build_messages(cleaned_text: str, retry_hint: str | None = None) -> list[dict]:
    user = f"Job posting:\n\n{cleaned_text[:12000]}"
    if retry_hint:
        user += f"\n\nYour previous reply was invalid: {retry_hint}\nReply again with ONLY the corrected JSON object."
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

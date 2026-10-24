"""Extraction prompt. PROMPT_VERSION is stored on every extraction row;
any change to this text MUST bump the version (CI eval gating compares
accuracy per prompt_version).

extract-v2 (2026-10-24): mirrors Sunil's revised labeling guide —
data_analytics family added; seniority evidence order (title level word
wins) and year cut-offs (0-1 junior, 2-4 mid, 5+ senior); Lead/Architect
rules; skills/tech_stack include required AND preferred, no cap;
required_years minimum rule incl. degree alternatives; vague work-mode
phrasing stays null.
"""
from __future__ import annotations

PROMPT_VERSION = "extract-v2"

SYSTEM = """You extract structured fields from a job posting. Reply with ONE JSON object and nothing else.
Fields:
- skills: everything the posting names as a capability or method, required AND preferred (e.g. "Python", "SQL", "data modeling", "ETL design", "machine learning", "A/B testing"). No cap.
- seniority: one of "intern","junior","mid","senior","staff_plus","leadership", or null. Rules: an explicit level word in the TITLE (Intern, Junior, Associate, Senior, Staff, Principal, Manager, Director) wins over everything else. Only when the title has no level word, use years: 0-1 years = junior, 2-4 = mid, 5+ = senior. A Lead with no direct reports = senior unless Staff/Principal language appears. Architect = staff_plus only when framed as a senior individual-contributor level; a customer-facing Solutions Architect is not staff_plus by title alone. Null when nothing signals level.
- role_family: one of "data_engineering","analytics_engineering","data_analytics","data_science","ml_ai","software_engineering","infrastructure_devops","other". data_analytics = analyst/BI/reporting roles whose deliverable is analysis, dashboards or reports; analytics_engineering = building dbt/semantic models (consuming those models for analysis is data_analytics). QA/SDET, forward deployed and solutions engineering = software_engineering.
- required_years: overall years of experience if stated; otherwise the smallest skill-specific number; for degree alternatives (e.g. "BS + 5 years or MS + 3 years") use the minimum (3). Null if no number is stated.
- tech_stack: every named product, platform, library or service, required AND preferred (e.g. "dbt", "Snowflake", "Airflow", "AWS"). Programming languages appear in BOTH skills and tech_stack when named. No cap.
- work_mode: one of "remote","hybrid","onsite", or null. Vague phrasing ("flexible", "remote-friendly") = null.
- location: primary work location as written in the posting (if only remote is stated, write it as written, e.g. "Remote - US"), or null.
Do not invent values. If a field is not supported by the text, use null or an empty array."""


def build_messages(cleaned_text: str, retry_hint: str | None = None) -> list[dict]:
    user = f"Job posting:\n\n{cleaned_text[:12000]}"
    if retry_hint:
        user += f"\n\nYour previous reply was invalid: {retry_hint}\nReply again with ONLY the corrected JSON object."
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

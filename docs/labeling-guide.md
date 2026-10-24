# REQWATCH Labeling Guide (revised 2026-10-24)

Label what the posting **says**, not what the title implies. When a field is not
stated or genuinely ambiguous, leave it **blank** (that is a valid label — the
model is scored against it). Your labels are ground truth for the extraction
eval, and you label **blind**: the labeling file contains no model output, and
no model output will ever be added to it. Use the `notes` column to flag hard
cases; notes never affect scoring.

## seniority — pick exactly one, or blank
**Evidence order (no exceptions):**
1. **An explicit level word in the title wins** — Intern, Junior, Senior,
   Staff, Principal, Manager, Director, **Lead**. If the title has one, use it
   and ignore years and body text. Two refinements:
   - **Associate is a conditional level word:** it means `junior` **only when
     no years are stated anywhere**. If years are stated, ignore "Associate"
     and apply rule 2 (in finance, Associate is often a 2–5 year band).
   - **Lead = `senior`** by title; **`leadership` if the text describes direct
     reports**. Staff/Principal language still overrides Lead to `staff_plus`.
2. Only when the title has **no** level word: use stated years —
   **0–1 years = `junior`, 2–4 = `mid`, 5+ = `senior`** (no overlaps) —
   and level language in the text.
3. **Blank** if neither the title nor the text signals level.

| value | definition |
|---|---|
| `intern` | Title/text says internship, co-op, or student role. |
| `junior` | Title says Junior, or Associate **with no years stated** (see rule 1), or 0–1 years by rule 2. |
| `mid` | No title level word, and 2–4 years (or clearly mid-level text). |
| `senior` | Title says Senior/Sr. or **Lead** (no direct reports described), or 5+ years by rule 2. Staff/Principal language overrides Lead to `staff_plus`. |
| `staff_plus` | Title says Staff, Principal, or Distinguished, or Architect **framed as a senior IC level**. A customer-facing **Solutions Architect is NOT `staff_plus` by title alone** — judge it by the same title/years rules as any role. |
| `leadership` | Title says Manager, Director, VP, or Head of X, **or** the role has direct reports (hiring / performance duties in the text) — including a **Lead** whose text describes direct reports. |

## role_family — fixed list, pick exactly one
- `data_engineering` — pipelines, ETL/ELT, warehouses/lakes, streaming, data infrastructure.
- `analytics_engineering` — **building** dbt models, semantic layers, metrics modeling for others to consume.
- `data_analytics` — data analyst, BI, and reporting roles whose deliverable is **analysis, dashboards, or reports**. Tie-break vs analytics_engineering: building dbt/semantic models = `analytics_engineering`; **consuming** them for analysis = `data_analytics`.
- `data_science` — statistics, experimentation, modeling/research where the deliverable is insight or a model, not a production system.
- `ml_ai` — production ML/AI systems: LLM apps, ML platforms serving models, applied AI engineering. Tie-break vs data_science: shipping models into a product = `ml_ai`.
- `software_engineering` — product/backend/frontend/full-stack software not primarily data or ML. **QA/SDET, forward deployed, and solutions engineering roles are `software_engineering`.**
- `infrastructure_devops` — cloud/platform infra, SRE, DevOps, security engineering, systems.
- `other` — anything that fits none of the above (including non-tech roles that slipped the filter).

## skills vs tech_stack — the one rule
- **skills = what you can DO** (capabilities, methods, concepts): "SQL", "Python",
  "data modeling", "ETL design", "machine learning", "A/B testing", "statistics".
- **tech_stack = what you USE** (named products, platforms, libraries, services):
  "dbt", "Snowflake", "Airflow", "Spark", "Kafka", "AWS", "Kubernetes", "Tableau".
- **Include everything named — required AND preferred.** No cap, no ordering;
  list them as they come.
- **Languages go in BOTH** when named (Python is a skill you have and part of
  the stack).
- Copy the posting's own names; do not normalize brands ("Postgres" stays
  "Postgres", "k8s" stays "k8s"). An alias map is applied at **scoring time
  only** (Postgres = PostgreSQL, k8s = Kubernetes, JS = JavaScript, …), so
  your labels never need to match the model's spelling. Semicolon-separated.

## other fields
- `label_required_years` — **overall experience if stated**; otherwise the
  **smallest skill-specific number** ("Python 3+, Spark 5+" → 3). For
  degree-dependent alternatives ("BS + 5 years or MS + 3 years") use the
  **minimum** (3). Blank if no number is stated anywhere.
- `label_work_mode` — `remote` / `hybrid` / `onsite`, only as clearly stated.
  **Vague phrasing ("flexible", "remote-friendly", "work from anywhere
  culture") = blank.**
- `label_location` — the primary work location as written (first one if
  several). **If only remote is stated, write it as written** (e.g.
  "Remote - US").

## self-agreement check
After your first batch, you will receive 30 of your own labeled rows again,
shuffled, labels removed. Label them fresh. Agreement between your two passes
is reported per field — it measures label consistency, and low-agreement fields
get their definitions tightened before the model eval is trusted.

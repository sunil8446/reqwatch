# REQWATCH Labeling Guide (one page)

Label what the posting **says**, not what the title implies. When a field is not
stated or genuinely ambiguous, leave it **blank** (that is a valid label — the
model is scored against it). Your labels are ground truth for the extraction
eval, and you label **blind**: the labeling file contains no model output, and
no model output will ever be added to it.

## seniority — pick exactly one, or blank
| value | definition |
|---|---|
| `intern` | Internship, co-op, or student role, explicitly. |
| `junior` | Entry level: 0–2 years asked, "entry level", Associate in an entry band, new-grad programs. |
| `mid` | The default professional band: roughly 2–5 years, no Senior/Staff markers in title or text. A bare title ("Data Engineer") with no other signal is `mid` **only** if the text reads mid-level; if nothing signals level at all, leave blank. |
| `senior` | Title says Senior/Sr., **or** 5+ years required with independent-ownership language ("own", "lead projects", "mentor"). |
| `staff_plus` | Staff, Principal, Distinguished, or Architect as an IC level; team-level technical leadership **without** direct reports. |
| `leadership` | Manages people or an org: Manager, Director, VP, Head of X, or a Lead whose posting describes direct reports / hiring / performance duties. |

Order of evidence: (1) explicit years + level language in the text, (2) title,
(3) blank. Never infer seniority from the company's prestige or the salary.

## role_family — fixed list, pick exactly one
- `data_engineering` — pipelines, ETL/ELT, warehouses/lakes, streaming, data infrastructure.
- `analytics_engineering` — dbt/semantic layer, analytics pipelines feeding BI, metrics modeling. Tie-break vs data_engineering: if the deliverable is dashboards/metrics for analysts, it's analytics_engineering; if it's platform/ingestion, data_engineering.
- `data_science` — statistics, experimentation, ML research/modeling where the deliverable is insight or a model, not a production system.
- `ml_ai` — production ML/AI systems: LLM apps, ML platform serving models, applied AI engineering. Tie-break vs data_science: shipping models into a product = ml_ai.
- `software_engineering` — product/backend/frontend/full-stack software that is not primarily data or ML.
- `infrastructure_devops` — cloud/platform infra, SRE, DevOps, security engineering, systems.
- `other` — anything that fits none of the above (including non-tech roles that slipped the filter).

## skills vs tech_stack — the one rule
- **skills = what you can DO** (capabilities, methods, concepts): "SQL", "Python",
  "data modeling", "ETL design", "machine learning", "A/B testing", "statistics",
  "distributed systems", "data warehousing".
- **tech_stack = what you USE** (named products, platforms, libraries, services):
  "dbt", "Snowflake", "Airflow", "Spark", "Kafka", "AWS", "Kubernetes", "Tableau".
- **Languages are the exception: they go in BOTH** when named (Python is a skill
  you have and part of the stack). Generic phrases ("cloud experience") are a
  skill; the named cloud ("AWS") is tech_stack.
- Copy the posting's own names; do not normalize brands ("GCP" stays "GCP").
  Semicolon-separated, max ~15 each, most important first.

## other fields
- `label_required_years` — the **minimum** of any stated range ("5–8 years" → 5;
  "5+" → 5). Blank if no number is stated anywhere.
- `label_work_mode` — `remote` / `hybrid` / `onsite`, only as stated. "Remote"
  in a location string counts; a list of office cities with no statement = blank.
- `label_location` — the primary work location as written (first one if several).

## self-agreement check
After your first batch, you will receive 30 of your own labeled rows again,
shuffled, labels removed. Label them fresh. Agreement between your two passes
is reported per field — it measures label consistency, and low-agreement fields
get their definitions tightened before the model eval is trusted.

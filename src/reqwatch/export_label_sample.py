"""Export a stratified labeling sample of current postings as CSV.

Deterministic pseudo-random order (md5 of posting id), capped per company
so one huge board (SpaceX) cannot dominate. Output goes to a GitHub
Actions artifact — posting text is never committed to the repo.

Label columns are left empty for Sunil to fill:
skills/tech_stack as semicolon-separated lists; seniority/role_family/
work_mode use the extraction schema's vocabularies.
"""
from __future__ import annotations

import csv
import os
import sys

from .db import connect

SAMPLE_SIZE = int(os.environ.get("REQWATCH_LABEL_SAMPLE_SIZE", "300"))
PER_COMPANY_CAP = int(os.environ.get("REQWATCH_LABEL_PER_COMPANY_CAP", "8"))
OUT = os.environ.get("REQWATCH_LABEL_OUT", "label_sample.csv")

FIELDS = ["posting_id", "company", "ats", "title", "location", "cleaned_text",
          "label_skills", "label_seniority", "label_role_family",
          "label_required_years", "label_tech_stack", "label_work_mode", "label_location"]


def main() -> int:
    with connect() as conn:
        rows = conn.execute(
            """select pv.posting_id, c.name, c.ats_type, pv.title, pv.location, pv.cleaned_text
               from posting_versions pv
               join postings p on p.id = pv.posting_id
               join companies c on c.id = p.company_id
               where pv.is_current and p.status = 'open'
               order by md5(pv.posting_id::text)""").fetchall()
    picked, per_company = [], {}
    for r in rows:
        if len(picked) >= SAMPLE_SIZE:
            break
        if per_company.get(r[1], 0) >= PER_COMPANY_CAP:
            continue
        per_company[r[1]] = per_company.get(r[1], 0) + 1
        picked.append(r)
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(FIELDS)
        for pid, company, ats, title, location, text in picked:
            w.writerow([pid, company, ats, title, location or "", text, "", "", "", "", "", "", ""])
    companies_covered = len(per_company)
    print(f"sample_rows={len(picked)} companies_covered={companies_covered} "
          f"pool={len(rows)} per_company_cap={PER_COMPANY_CAP} out={OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

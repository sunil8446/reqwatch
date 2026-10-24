# Secrets and variables — exactly what to create

Sunil creates these himself. Never paste secret values into chat.
Repo → Settings → Secrets and variables → Actions.

## Phase 1 — required now

### Secrets (tab: Secrets → New repository secret)
| Name | Value | Used by |
|---|---|---|
| `DATABASE_URL` | Neon **pooled** connection string for the Reqwatch project, e.g. `postgresql://<user>:<password>@<host>-pooler.<region>.aws.neon.tech/<db>?sslmode=require` | daily-pipeline, freshness-check |

That is the only secret Phase 1 needs.

### Variables (tab: Variables → New repository variable) — not secret
| Name | Value |
|---|---|
| `REQWATCH_USER_AGENT` | `Reqwatch/1.0 (+https://YOUR-DOMAIN/about; portfolio research)` — replace YOUR-DOMAIN once the Phase 5 subdomain is approved |

## Later phases (do NOT create yet)
| Phase | Secret | Purpose |
|---|---|---|
| 4 | `BREVO_API_KEY` | Email digests + magic-link mail (Brevo Free) |
| 4 | `MAGIC_LINK_SECRET` | Signing magic-link tokens (generate: `openssl rand -hex 32`) |
| 5/6 | `RENDER_DEPLOY_HOOK_URL` | Only if deploy-hook deploys are chosen over Render's GitHub integration |

## Local development
Copy `.env.example` to `.env` (gitignored) and put the same `DATABASE_URL`
there. A separate Neon **branch** (free tier includes branches) is
recommended for local/dev so test writes never touch production data.

## Hygiene rules
- No data files are committed (see `.gitignore`); the seed CSV under
  `seed/` is configuration, not scraped data.
- The DB URL appears only in Actions secrets / local `.env` — never in
  code, issues, or logs (the app never prints it).

-- REQWATCH schema (Phase 1). Postgres. Applied idempotently by reqwatch.db.apply_schema.
-- Storage rule: posting_versions stores CLEANED TEXT ONLY. No raw HTML / raw JSON payloads
-- are stored anywhere in Postgres. Drift detection keeps only a schema snapshot
-- (sorted field names + a hash of them) per board per run.

create table if not exists companies (
    id          bigint generated always as identity primary key,
    name        text not null,
    ats_type    text not null check (ats_type in ('greenhouse','lever','ashby')),
    board_token text not null,
    active      boolean not null default true,
    added_at    timestamptz not null default now(),
    unique (ats_type, board_token)
);

create table if not exists postings (
    id               bigint generated always as identity primary key,
    company_id       bigint not null references companies(id),
    source_posting_id text not null,
    current_hash     text not null,
    first_seen_at    timestamptz not null,
    last_seen_at     timestamptz not null,
    closed_at        timestamptz,
    status           text not null default 'open' check (status in ('open','closed')),
    -- consecutive successful board fetches in which this posting was absent.
    -- Closure requires miss_count >= 2 (guards against one flaky fetch).
    miss_count       int not null default 0,
    source_updated_at text,  -- source-reported last-change stamp (Greenhouse list); drives fetch skipping
    unique (company_id, source_posting_id)
);
alter table postings add column if not exists source_updated_at text;
create index if not exists idx_postings_company_status on postings(company_id, status);

create table if not exists posting_versions (
    id           bigint generated always as identity primary key,
    posting_id   bigint not null references postings(id),
    version      int not null,
    content_hash text not null,
    title        text not null,
    location     text,
    department   text,
    cleaned_text text not null,  -- cleaned text only; never raw HTML
    valid_from   timestamptz not null,
    valid_to     timestamptz,    -- null while current
    is_current   boolean not null default true,
    unique (posting_id, version)
);
create index if not exists idx_versions_posting_current on posting_versions(posting_id) where is_current;

-- LLM extractions land in Phase 2; table defined now so the FK shape is stable.
create table if not exists extractions (
    id             bigint generated always as identity primary key,
    posting_id     bigint not null references postings(id),
    version        int not null,
    provider       text not null,
    model          text not null,
    prompt_version text not null,
    extracted_json jsonb,
    extracted_at   timestamptz not null default now(),
    input_tokens   int,
    output_tokens  int,
    unique (posting_id, version, provider, model, prompt_version)
);

create table if not exists extraction_dead_letters (
    id             bigint generated always as identity primary key,
    posting_id     bigint not null references postings(id),
    version        int not null,
    provider       text not null,
    model          text not null,
    prompt_version text not null,
    error          text not null,
    raw_output     text,
    attempts       int not null default 2,
    created_at     timestamptz not null default now()
);

create table if not exists users (
    id         bigint generated always as identity primary key,
    email      text not null unique,
    created_at timestamptz not null default now()
);

create table if not exists saved_searches (
    id         bigint generated always as identity primary key,
    user_id    bigint not null references users(id),
    filters    jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists alerts_sent (
    id              bigint generated always as identity primary key,
    saved_search_id bigint not null references saved_searches(id),
    posting_id      bigint not null references postings(id),
    sent_at         timestamptz not null default now(),
    unique (saved_search_id, posting_id)
);

create table if not exists pipeline_runs (
    run_id            uuid primary key,
    started_at        timestamptz not null,
    finished_at       timestamptz,
    status            text not null default 'running' check (status in ('running','success','failed')),
    companies_ok      int not null default 0,
    companies_failed  int not null default 0,
    postings_new      int not null default 0,
    postings_changed  int not null default 0,
    postings_closed   int not null default 0,
    postings_seen     int not null default 0,
    db_size_bytes     bigint,  -- pg_database_size at end of run
    db_growth_bytes   bigint   -- db_size_bytes minus previous successful run's size
);

-- One row per company per run: powers closure logic, source health
-- (3 consecutive errored runs => alert) and per-company audit.
create table if not exists company_runs (
    run_id      uuid not null references pipeline_runs(run_id),
    company_id  bigint not null references companies(id),
    outcome     text not null check (outcome in ('ok','error')),
    http_status int,
    postings_seen int not null default 0,
    -- Title-filter accounting (filter-first condition, 2026-10-24):
    postings_listed int not null default 0,  -- titles in the list response
    postings_kept   int not null default 0,  -- titles passing the filter
    postings_stored int not null default 0,  -- kept postings upserted this run
    error       text,
    primary key (run_id, company_id)
);
alter table company_runs add column if not exists postings_listed int not null default 0;
alter table company_runs add column if not exists postings_kept int not null default 0;
alter table company_runs add column if not exists postings_stored int not null default 0;

-- Drift detection: ONLY the sorted top-level + first-job field names and their hash.
-- No payload is stored.
create table if not exists board_schema_snapshots (
    id           bigint generated always as identity primary key,
    company_id   bigint not null references companies(id),
    run_id       uuid not null references pipeline_runs(run_id),
    schema_hash  text not null,
    field_names  text[] not null,
    captured_at  timestamptz not null default now()
);
create index if not exists idx_snapshots_company_time on board_schema_snapshots(company_id, captured_at desc);

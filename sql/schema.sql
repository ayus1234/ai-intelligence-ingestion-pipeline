CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    base_url TEXT NOT NULL,
    fetch_mode TEXT NOT NULL,
    crawl_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crawl_targets (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES sources(id),
    url TEXT NOT NULL,
    normalized_url_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 100,
    next_retry_at TIMESTAMPTZ,
    claimed_by TEXT,
    claimed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_documents (
    id BIGSERIAL PRIMARY KEY,
    crawl_target_id BIGINT REFERENCES crawl_targets(id),
    source_url TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    http_status INTEGER NOT NULL,
    headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_hash TEXT NOT NULL UNIQUE,
    cleaned_text TEXT,
    raw_html TEXT,
    raw_blob_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS extraction_runs (
    id BIGSERIAL PRIMARY KEY,
    raw_document_id BIGINT NOT NULL REFERENCES raw_documents(id),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    token_estimate INTEGER,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    source_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    success_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    export_status TEXT NOT NULL DEFAULT 'not_started',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS canonical_records (
    id BIGSERIAL PRIMARY KEY,
    record_type TEXT NOT NULL,
    natural_key TEXT NOT NULL,
    source_url TEXT,
    schema_version TEXT NOT NULL,
    payload JSONB NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (record_type, natural_key)
);

CREATE TABLE IF NOT EXISTS startups (
    canonical_record_id BIGINT PRIMARY KEY REFERENCES canonical_records(id) ON DELETE CASCADE,
    entity_name TEXT NOT NULL UNIQUE,
    raw_entity_name TEXT,
    employee_count INTEGER,
    employee_count_raw TEXT,
    website_url TEXT,
    company_domain TEXT,
    batch TEXT,
    industry TEXT,
    source_collected_at TIMESTAMPTZ,
    source_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    canonical_record_id BIGINT PRIMARY KEY REFERENCES canonical_records(id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    startup_name TEXT NOT NULL,
    raw_startup_name TEXT,
    pricing_model TEXT NOT NULL,
    category TEXT,
    source_url TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS research_papers (
    canonical_record_id BIGINT PRIMARY KEY REFERENCES canonical_records(id) ON DELETE CASCADE,
    arxiv_id TEXT UNIQUE,
    papers_with_code_id TEXT,
    title TEXT NOT NULL,
    authors JSONB NOT NULL,
    paper_url TEXT NOT NULL UNIQUE,
    primary_github_url TEXT,
    github_url TEXT,
    github_repositories JSONB NOT NULL DEFAULT '[]'::jsonb,
    github_stars INTEGER,
    github_stars_fetched_at TIMESTAMPTZ,
    source_collected_at TIMESTAMPTZ,
    github_metrics_collected_at TIMESTAMPTZ,
    repository_source TEXT NOT NULL DEFAULT 'NONE',
    published_date TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    canonical_record_id BIGINT PRIMARY KEY REFERENCES canonical_records(id) ON DELETE CASCADE,
    company TEXT NOT NULL,
    raw_company TEXT NOT NULL,
    company_domain TEXT,
    role_title TEXT NOT NULL,
    normalized_role TEXT NOT NULL,
    role_family TEXT NOT NULL,
    location TEXT,
    is_remote BOOLEAN NOT NULL DEFAULT false,
    employment_type TEXT,
    salary_text TEXT,
    description TEXT NOT NULL,
    posted_date TIMESTAMPTZ NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    source_job_id TEXT,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS news (
    canonical_record_id BIGINT PRIMARY KEY REFERENCES canonical_records(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    publication_date TIMESTAMPTZ NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    date_source TEXT NOT NULL,
    freshness_verified BOOLEAN NOT NULL DEFAULT false,
    content_hash TEXT NOT NULL UNIQUE
);

CREATE UNIQUE INDEX IF NOT EXISTS news_source_or_content_uq
ON news (source_url, COALESCE(content_hash, ''));

CREATE TABLE IF NOT EXISTS entities (
    id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_type, normalized_name)
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id BIGSERIAL PRIMARY KEY,
    entity_id BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    raw_alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    confidence NUMERIC(5,4) NOT NULL,
    method TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_id, normalized_alias)
);

CREATE TABLE IF NOT EXISTS entity_mapping_log (
    id BIGSERIAL PRIMARY KEY,
    canonical_id TEXT,
    raw_name TEXT NOT NULL,
    canonical_name TEXT,
    entity_type TEXT NOT NULL,
    confidence NUMERIC(5,4) NOT NULL,
    method TEXT NOT NULL,
    resolution_tier TEXT NOT NULL DEFAULT 'unresolved',
    signals_evaluated JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_url TEXT,
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS github_repo_metrics (
    id BIGSERIAL PRIMARY KEY,
    github_url TEXT NOT NULL UNIQUE,
    owner TEXT,
    repo TEXT,
    stars INTEGER,
    forks INTEGER,
    watchers INTEGER,
    open_issues INTEGER,
    default_branch TEXT,
    archived BOOLEAN,
    license TEXT,
    fetched_at TIMESTAMPTZ NOT NULL,
    api_status INTEGER NOT NULL,
    response_hash TEXT
);

CREATE TABLE IF NOT EXISTS export_runs (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    sheet_id TEXT NOT NULL,
    row_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL,
    errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

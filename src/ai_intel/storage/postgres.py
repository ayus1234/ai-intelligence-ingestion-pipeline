"""Async PostgreSQL repository implementation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import TracebackType

from ai_intel.config import Settings
from ai_intel.schemas import CrawlTarget, EntityMappingLog, RawDocument, RecordEnvelope
from ai_intel.schemas.records import JobRecord, NewsRecord, ProductRecord, ResearchPaperRecord, StartupRecord
from ai_intel.schemas.research import GitHubRepoMetrics
from ai_intel.storage.base import StorageRepository
from ai_intel.utils.hashing import sha256_text
from ai_intel.utils.urls import normalize_url


try:
    import asyncpg  # type: ignore[import-not-found,import-untyped]
except ImportError:
    asyncpg = None  # type: ignore[assignment]


class PostgresStorageRepository(StorageRepository):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pool = None

    async def __aenter__(self) -> "PostgresStorageRepository":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def connect(self) -> None:
        if asyncpg is None:
            raise RuntimeError("asyncpg is required to connect to PostgreSQL. Install it with pip install asyncpg.")
        self._pool = await asyncpg.create_pool(self.settings.database_url, min_size=1, max_size=5)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def start_pipeline_run(
        self,
        run_id: str,
        source_counts: dict[str, int] | None = None,
    ) -> None:
        pool = self._require_pool()
        await pool.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, started_at, status, source_counts, success_counts, failure_counts, export_status
            )
            VALUES ($1, $2, 'running', $3::jsonb, '{}'::jsonb, '{}'::jsonb, 'not_started')
            ON CONFLICT (run_id) DO UPDATE SET
                started_at = EXCLUDED.started_at,
                completed_at = NULL,
                status = 'running',
                source_counts = EXCLUDED.source_counts,
                updated_at = now()
            """,
            run_id,
            datetime.now(timezone.utc),
            json.dumps(source_counts or {}),
        )

    async def complete_pipeline_run(
        self,
        run_id: str,
        success_counts: dict[str, int],
        failure_counts: dict[str, int],
        export_status: str = "not_started",
        source_counts: dict[str, int] | None = None,
    ) -> None:
        pool = self._require_pool()
        await pool.execute(
            """
            UPDATE pipeline_runs
            SET completed_at = $2,
                status = 'completed',
                success_counts = $3::jsonb,
                failure_counts = $4::jsonb,
                export_status = $5,
                source_counts = COALESCE($6::jsonb, source_counts),
                updated_at = now()
            WHERE run_id = $1
            """,
            run_id,
            datetime.now(timezone.utc),
            json.dumps(success_counts),
            json.dumps(failure_counts),
            export_status,
            json.dumps(source_counts) if source_counts is not None else None,
        )

    async def upsert_github_metrics(self, metrics: GitHubRepoMetrics) -> bool:
        pool = self._require_pool()
        inserted = await pool.fetchval(
            """
            INSERT INTO github_repo_metrics (
                github_url, owner, repo, stars, forks, watchers, open_issues,
                default_branch, archived, license, fetched_at, api_status, response_hash
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (github_url) DO UPDATE SET
                owner = EXCLUDED.owner,
                repo = EXCLUDED.repo,
                stars = EXCLUDED.stars,
                forks = EXCLUDED.forks,
                watchers = EXCLUDED.watchers,
                open_issues = EXCLUDED.open_issues,
                default_branch = EXCLUDED.default_branch,
                archived = EXCLUDED.archived,
                license = EXCLUDED.license,
                fetched_at = EXCLUDED.fetched_at,
                api_status = EXCLUDED.api_status,
                response_hash = EXCLUDED.response_hash
            RETURNING (xmax = 0) AS inserted
            """,
            str(metrics.github_url),
            metrics.owner,
            metrics.repo,
            metrics.stars,
            metrics.forks,
            metrics.watchers,
            metrics.open_issues,
            metrics.default_branch,
            metrics.archived,
            metrics.license,
            metrics.fetched_at,
            metrics.api_status,
            metrics.response_hash,
        )
        return bool(inserted)

    async def upsert_research_paper(self, record: ResearchPaperRecord) -> bool:
        pool = self._require_pool()
        payload = record.model_dump(mode="json", by_alias=True)
        source_url = str(record.source.url) if record.source else str(record.content.paper_url)
        async with pool.acquire() as connection:
            async with connection.transaction():
                canonical_id = await connection.fetchval(
                    """
                    INSERT INTO canonical_records (
                        record_type, natural_key, source_url, schema_version, payload, collected_at
                    )
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                    ON CONFLICT (record_type, natural_key) DO UPDATE SET
                        source_url = EXCLUDED.source_url,
                        schema_version = EXCLUDED.schema_version,
                        payload = EXCLUDED.payload,
                        collected_at = EXCLUDED.collected_at,
                        updated_at = now()
                    RETURNING id
                    """,
                    record.record_type.value,
                    record.natural_key(),
                    source_url,
                    record.schema_version,
                    json.dumps(payload),
                    record.collected_at,
                )
                inserted = await connection.fetchval(
                    """
                    INSERT INTO research_papers (
                        canonical_record_id,
                        arxiv_id,
                        papers_with_code_id,
                        title,
                        authors,
                        paper_url,
                        primary_github_url,
                        github_url,
                        github_repositories,
                        github_stars,
                        github_stars_fetched_at,
                        source_collected_at,
                        github_metrics_collected_at,
                        repository_source,
                        published_date
                    )
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9::jsonb, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (paper_url) DO UPDATE SET
                        canonical_record_id = EXCLUDED.canonical_record_id,
                        arxiv_id = EXCLUDED.arxiv_id,
                        papers_with_code_id = EXCLUDED.papers_with_code_id,
                        title = EXCLUDED.title,
                        authors = EXCLUDED.authors,
                        primary_github_url = EXCLUDED.primary_github_url,
                        github_url = EXCLUDED.github_url,
                        github_repositories = EXCLUDED.github_repositories,
                        github_stars = EXCLUDED.github_stars,
                        github_stars_fetched_at = EXCLUDED.github_stars_fetched_at,
                        source_collected_at = EXCLUDED.source_collected_at,
                        github_metrics_collected_at = EXCLUDED.github_metrics_collected_at,
                        repository_source = EXCLUDED.repository_source,
                        published_date = EXCLUDED.published_date
                    RETURNING (xmax = 0) AS inserted
                    """,
                    canonical_id,
                    record.content.arxiv_id,
                    record.content.papers_with_code_id,
                    record.content.title,
                    json.dumps(record.content.authors),
                    str(record.content.paper_url),
                    str(record.content.primary_github_url) if record.content.primary_github_url else None,
                    str(record.content.github_url) if record.content.github_url else None,
                    json.dumps([str(url) for url in record.content.github_repositories]),
                    record.content.github_stars,
                    record.content.github_stars_fetched_at,
                    record.content.source_collected_at,
                    record.content.github_metrics_collected_at,
                    record.content.repository_source.value,
                    record.content.published_date,
                )
                return bool(inserted)

    async def upsert_startup(self, record: StartupRecord) -> bool:
        pool = self._require_pool()
        payload = record.model_dump(mode="json", by_alias=True)
        source_url = str(record.source.url) if record.source else str(record.content.data.website_url or "")
        async with pool.acquire() as connection:
            async with connection.transaction():
                canonical_id = await connection.fetchval(
                    """
                    INSERT INTO canonical_records (
                        record_type, natural_key, source_url, schema_version, payload, collected_at
                    )
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                    ON CONFLICT (record_type, natural_key) DO UPDATE SET
                        source_url = EXCLUDED.source_url,
                        schema_version = EXCLUDED.schema_version,
                        payload = EXCLUDED.payload,
                        collected_at = EXCLUDED.collected_at,
                        updated_at = now()
                    RETURNING id
                    """,
                    record.record_type.value,
                    record.natural_key(),
                    source_url,
                    record.schema_version,
                    json.dumps(payload),
                    record.collected_at,
                )
                inserted = await connection.fetchval(
                    """
                    INSERT INTO startups (
                        canonical_record_id,
                        entity_name,
                        raw_entity_name,
                        employee_count,
                        employee_count_raw,
                        website_url,
                        company_domain,
                        batch,
                        industry,
                        source_url,
                        source_collected_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (entity_name) DO UPDATE SET
                        canonical_record_id = EXCLUDED.canonical_record_id,
                        raw_entity_name = EXCLUDED.raw_entity_name,
                        employee_count = COALESCE(EXCLUDED.employee_count, startups.employee_count),
                        employee_count_raw = COALESCE(EXCLUDED.employee_count_raw, startups.employee_count_raw),
                        website_url = COALESCE(EXCLUDED.website_url, startups.website_url),
                        company_domain = COALESCE(EXCLUDED.company_domain, startups.company_domain),
                        batch = COALESCE(EXCLUDED.batch, startups.batch),
                        industry = COALESCE(EXCLUDED.industry, startups.industry),
                        source_url = EXCLUDED.source_url,
                        source_collected_at = EXCLUDED.source_collected_at
                    RETURNING (xmax = 0) AS inserted
                    """,
                    canonical_id,
                    record.content.entity_name,
                    record.content.raw_entity_name,
                    record.content.data.employee_count,
                    record.content.data.employee_count_raw,
                    str(record.content.data.website_url) if record.content.data.website_url else None,
                    record.content.data.company_domain,
                    record.content.data.batch,
                    record.content.data.industry,
                    source_url,
                    record.content.data.source_collected_at,
                )
                return bool(inserted)

    async def upsert_product(self, record: ProductRecord) -> bool:
        pool = self._require_pool()
        payload = record.model_dump(mode="json", by_alias=True)
        source_url = str(record.content.source_url)
        async with pool.acquire() as connection:
            async with connection.transaction():
                canonical_id = await connection.fetchval(
                    """
                    INSERT INTO canonical_records (
                        record_type, natural_key, source_url, schema_version, payload, collected_at
                    )
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                    ON CONFLICT (record_type, natural_key) DO UPDATE SET
                        source_url = EXCLUDED.source_url,
                        schema_version = EXCLUDED.schema_version,
                        payload = EXCLUDED.payload,
                        collected_at = EXCLUDED.collected_at,
                        updated_at = now()
                    RETURNING id
                    """,
                    record.record_type.value,
                    record.natural_key(),
                    source_url,
                    record.schema_version,
                    json.dumps(payload),
                    record.collected_at,
                )
                inserted = await connection.fetchval(
                    """
                    INSERT INTO products (
                        canonical_record_id, product_name, startup_name, raw_startup_name, pricing_model, category, source_url
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (source_url) DO UPDATE SET
                        canonical_record_id = EXCLUDED.canonical_record_id,
                        product_name = EXCLUDED.product_name,
                        startup_name = EXCLUDED.startup_name,
                        raw_startup_name = EXCLUDED.raw_startup_name,
                        pricing_model = EXCLUDED.pricing_model,
                        category = EXCLUDED.category
                    RETURNING (xmax = 0) AS inserted
                    """,
                    canonical_id,
                    record.content.product_name,
                    record.content.startup_name,
                    record.content.raw_startup_name,
                    record.content.pricing_model.value,
                    record.content.category,
                    source_url,
                )
                return bool(inserted)

    async def upsert_news(self, record: NewsRecord) -> bool:
        pool = self._require_pool()
        payload = record.model_dump(mode="json", by_alias=True)
        source_url = str(record.content.source_url)
        async with pool.acquire() as connection:
            async with connection.transaction():
                canonical_id = await connection.fetchval(
                    """
                    INSERT INTO canonical_records (
                        record_type, natural_key, source_url, schema_version, payload, collected_at
                    )
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                    ON CONFLICT (record_type, natural_key) DO UPDATE SET
                        source_url = EXCLUDED.source_url,
                        schema_version = EXCLUDED.schema_version,
                        payload = EXCLUDED.payload,
                        collected_at = EXCLUDED.collected_at,
                        updated_at = now()
                    RETURNING id
                    """,
                    record.record_type.value,
                    record.natural_key(),
                    source_url,
                    record.schema_version,
                    json.dumps(payload),
                    record.collected_at,
                )
                inserted = await connection.fetchval(
                    """
                    INSERT INTO news (
                        canonical_record_id, title, content, publication_date, source_name, source_url, date_source, freshness_verified, content_hash
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (source_url) DO UPDATE SET
                        canonical_record_id = EXCLUDED.canonical_record_id,
                        title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        publication_date = EXCLUDED.publication_date,
                        source_name = EXCLUDED.source_name,
                        date_source = EXCLUDED.date_source,
                        freshness_verified = EXCLUDED.freshness_verified,
                        content_hash = EXCLUDED.content_hash
                    RETURNING (xmax = 0) AS inserted
                    """,
                    canonical_id,
                    record.content.title,
                    record.content.content,
                    record.content.publication_date,
                    record.content.source_name,
                    source_url,
                    record.content.date_source,
                    record.content.freshness_verified,
                    record.content.content_hash,
                )
                return bool(inserted)

    async def upsert_job(self, record: JobRecord) -> bool:
        pool = self._require_pool()
        payload = record.model_dump(mode="json", by_alias=True)
        source_url = str(record.content.source_url)
        async with pool.acquire() as connection:
            async with connection.transaction():
                canonical_id = await connection.fetchval(
                    """
                    INSERT INTO canonical_records (
                        record_type, natural_key, source_url, schema_version, payload, collected_at
                    )
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                    ON CONFLICT (record_type, natural_key) DO UPDATE SET
                        source_url = EXCLUDED.source_url,
                        schema_version = EXCLUDED.schema_version,
                        payload = EXCLUDED.payload,
                        collected_at = EXCLUDED.collected_at,
                        updated_at = now()
                    RETURNING id
                    """,
                    record.record_type.value,
                    record.natural_key(),
                    source_url,
                    record.schema_version,
                    json.dumps(payload),
                    record.collected_at,
                )
                inserted = await connection.fetchval(
                    """
                    INSERT INTO jobs (
                        canonical_record_id, company, raw_company, company_domain, role_title, normalized_role,
                        role_family, location, is_remote, employment_type, salary_text, description,
                        posted_date, first_seen_at, source_job_id, source_name, source_url
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    ON CONFLICT (source_url) DO UPDATE SET
                        canonical_record_id = EXCLUDED.canonical_record_id,
                        company = EXCLUDED.company,
                        raw_company = EXCLUDED.raw_company,
                        company_domain = EXCLUDED.company_domain,
                        role_title = EXCLUDED.role_title,
                        normalized_role = EXCLUDED.normalized_role,
                        role_family = EXCLUDED.role_family,
                        location = EXCLUDED.location,
                        is_remote = EXCLUDED.is_remote,
                        employment_type = EXCLUDED.employment_type,
                        salary_text = EXCLUDED.salary_text,
                        description = EXCLUDED.description,
                        posted_date = EXCLUDED.posted_date,
                        source_job_id = EXCLUDED.source_job_id,
                        source_name = EXCLUDED.source_name
                    RETURNING (xmax = 0) AS inserted
                    """,
                    canonical_id,
                    record.content.company,
                    record.content.raw_company,
                    record.content.company_domain,
                    record.content.role_title,
                    record.content.normalized_role,
                    record.content.role_family,
                    record.content.location,
                    record.content.is_remote,
                    record.content.employment_type,
                    record.content.salary_text,
                    record.content.description,
                    record.content.posted_date,
                    record.content.first_seen_at,
                    record.content.source_job_id,
                    record.content.source_name,
                    source_url,
                )
                return bool(inserted)

    async def log_mapping(self, mapping: EntityMappingLog) -> None:
        pool = self._require_pool()
        await pool.execute(
            """
            INSERT INTO entity_mapping_log (
                canonical_id, raw_name, canonical_name, entity_type, confidence, method, resolution_tier, signals_evaluated, source_url, resolved_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)
            """,
            mapping.canonical_id,
            mapping.raw_name,
            mapping.canonical_name,
            mapping.entity_type,
            mapping.confidence,
            mapping.method,
            mapping.resolution_tier,
            json.dumps(mapping.signals_evaluated),
            str(mapping.source_url) if mapping.source_url else None,
            mapping.resolved_at,
        )

    async def enqueue(self, target: CrawlTarget) -> bool:
        pool = self._require_pool()
        url_hash = sha256_text(normalize_url(str(target.url)))
        source_id = await pool.fetchval(
            """
            INSERT INTO sources (name, kind, base_url, fetch_mode)
            VALUES ($1, $2, $3, 'httpx')
            ON CONFLICT (name) DO UPDATE SET kind = EXCLUDED.kind
            RETURNING id
            """,
            target.source_name,
            target.source_kind,
            str(target.url),
        )
        inserted = await pool.fetchval(
            """
            INSERT INTO crawl_targets (source_id, url, normalized_url_hash, status, priority, metadata)
            VALUES ($1, $2, $3, 'pending', $4, $5::jsonb)
            ON CONFLICT (normalized_url_hash) DO NOTHING
            RETURNING id
            """,
            source_id,
            str(target.url),
            url_hash,
            target.priority,
            json.dumps(target.metadata),
        )
        return bool(inserted is not None)

    async def claim_batch(self, limit: int) -> list[CrawlTarget]:
        pool = self._require_pool()
        rows = await pool.fetch(
            """
            UPDATE crawl_targets
            SET status = 'claimed', claimed_at = now()
            WHERE id IN (
                SELECT ct.id FROM crawl_targets ct
                WHERE ct.status = 'pending'
                ORDER BY ct.priority DESC, ct.id ASC
                LIMIT $1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING url, priority, metadata,
                      (SELECT name FROM sources WHERE id = crawl_targets.source_id) AS source_name,
                      (SELECT kind FROM sources WHERE id = crawl_targets.source_id) AS source_kind
            """,
            limit,
        )
        return [
            CrawlTarget(
                url=row["url"],
                source_name=row["source_name"] or "unknown",
                source_kind=row["source_kind"] or "unknown",
                priority=row["priority"],
                metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
            )
            for row in rows
        ]

    async def save_raw(self, raw: RawDocument) -> bool:
        pool = self._require_pool()
        inserted = await pool.fetchval(
            """
            INSERT INTO raw_documents (
                source_url, fetched_at, http_status, headers, content_hash, cleaned_text, raw_html
            )
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
            ON CONFLICT (content_hash) DO NOTHING
            RETURNING id
            """,
            str(raw.source_url),
            raw.fetched_at,
            raw.http_status,
            json.dumps(raw.headers),
            raw.content_hash,
            raw.cleaned_text,
            raw.raw_html,
        )
        return bool(inserted is not None)

    async def upsert_record(self, record: RecordEnvelope) -> bool:
        pool = self._require_pool()
        payload = record.model_dump(mode="json", by_alias=True)
        source_url = str(record.source.url) if record.source else None
        inserted = await pool.fetchval(
            """
            INSERT INTO canonical_records (
                record_type, natural_key, source_url, schema_version, payload, collected_at
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            ON CONFLICT (record_type, natural_key) DO UPDATE SET
                source_url = EXCLUDED.source_url,
                schema_version = EXCLUDED.schema_version,
                payload = EXCLUDED.payload,
                collected_at = EXCLUDED.collected_at,
                updated_at = now()
            RETURNING (xmax = 0) AS inserted
            """,
            record.record_type.value,
            record.natural_key(),
            source_url,
            record.schema_version,
            json.dumps(payload),
            record.collected_at,
        )
        return bool(inserted)

    async def mark_done(self, target: CrawlTarget) -> None:
        pool = self._require_pool()
        url_hash = sha256_text(normalize_url(str(target.url)))
        await pool.execute(
            """
            UPDATE crawl_targets
            SET status = 'completed', updated_at = now()
            WHERE normalized_url_hash = $1
            """,
            url_hash,
        )

    def _require_pool(self):
        if self._pool is None:
            raise RuntimeError("PostgresStorageRepository is not connected")
        return self._pool

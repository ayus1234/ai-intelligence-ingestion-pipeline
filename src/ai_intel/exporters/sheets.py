"""Google Sheets and CSV/JSON manifest exporter engine."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from typing import Any

from ai_intel.exporters.base import ExportResult, Exporter
from ai_intel.logging import get_logger
from ai_intel.schemas.records import JobRecord, NewsRecord, ProductRecord, ResearchPaperRecord, StartupRecord
from ai_intel.storage.base import StorageRepository

logger = get_logger(__name__)


class GoogleSheetsExporter(Exporter):
    def __init__(self, service_account_file: str | None = None) -> None:
        self.service_account_file = service_account_file

    async def export(
        self,
        run_id: str,
        destination: str,
        storage: StorageRepository | None = None,
        records_by_type: dict[str, list[Any]] | None = None,
        quality_report: dict[str, Any] | None = None,
    ) -> ExportResult:
        """Export pipeline run data into 6 required tabs or local CSV/JSON manifest files."""
        output_dir = destination or f"exports/run_{run_id}"
        os.makedirs(output_dir, exist_ok=True)

        startups = records_by_type.get("startups", []) if records_by_type else []
        products = records_by_type.get("products", []) if records_by_type else []
        papers = records_by_type.get("papers", []) if records_by_type else []
        news = records_by_type.get("news", []) if records_by_type else []
        jobs = records_by_type.get("jobs", []) if records_by_type else []

        row_counts: dict[str, int] = {}

        # 1. Startups Tab
        startup_file = os.path.join(output_dir, "01_startups.csv")
        with open(startup_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Entity Name",
                "Raw Entity Name",
                "Canonical ID",
                "Domain",
                "Employee Count",
                "Raw Employee Count",
                "Website",
                "Batch",
                "Industry",
            ])
            for r in startups:
                content = r.content if hasattr(r, "content") else r
                c_id = getattr(getattr(r, "_mapping_log", None), "canonical_id", "")
                writer.writerow([
                    content.entity_name,
                    content.raw_entity_name or "",
                    c_id,
                    content.data.company_domain or "",
                    content.data.employee_count or "",
                    content.data.employee_count_raw or "",
                    str(content.data.website_url) if content.data.website_url else "",
                    content.data.batch or "",
                    content.data.industry or "",
                ])
        row_counts["Startups"] = len(startups)

        # 2. Products Tab
        product_file = os.path.join(output_dir, "02_products.csv")
        with open(product_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Product Name",
                "Startup Name",
                "Raw Startup Name",
                "Canonical ID",
                "Pricing Model",
                "Category",
                "Source URL",
            ])
            for r in products:
                content = r.content if hasattr(r, "content") else r
                c_id = getattr(getattr(r, "_mapping_log", None), "canonical_id", "")
                writer.writerow([
                    content.product_name,
                    content.startup_name,
                    content.raw_startup_name or "",
                    c_id,
                    content.pricing_model,
                    content.category or "",
                    str(content.source_url),
                ])
        row_counts["Products"] = len(products)

        # 3. Research Papers Tab
        paper_file = os.path.join(output_dir, "03_research_papers.csv")
        with open(paper_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "arXiv ID",
                "Papers With Code ID",
                "Title",
                "Authors",
                "Paper URL",
                "Primary GitHub URL",
                "GitHub Stars",
                "Repository Source",
                "Published Date",
            ])
            for r in papers:
                content = r.content if hasattr(r, "content") else r
                writer.writerow([
                    content.arxiv_id or "",
                    content.papers_with_code_id or "",
                    content.title,
                    "; ".join(content.authors),
                    str(content.paper_url),
                    str(content.primary_github_url) if content.primary_github_url else "",
                    content.github_stars or 0,
                    content.repository_source,
                    content.published_date.isoformat(),
                ])
        row_counts["Research Papers"] = len(papers)

        # 4. AI News Tab
        news_file = os.path.join(output_dir, "04_ai_news.csv")
        with open(news_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Title",
                "Content Summary",
                "Publication Date",
                "Source Name",
                "Source URL",
                "Date Source",
                "Freshness Verified",
                "Content Hash",
            ])
            for r in news:
                content = r.content if hasattr(r, "content") else r
                writer.writerow([
                    content.title,
                    content.content[:200],
                    content.publication_date.isoformat(),
                    content.source_name,
                    str(content.source_url),
                    content.date_source,
                    content.freshness_verified,
                    content.content_hash,
                ])
        row_counts["AI News"] = len(news)

        # 5. AI Jobs Tab
        job_file = os.path.join(output_dir, "05_ai_jobs.csv")
        with open(job_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Role Title",
                "Company",
                "Raw Company",
                "Company Domain",
                "Canonical ID",
                "Role Family",
                "Location",
                "Is Remote",
                "Salary",
                "Posted Date",
                "First Seen At",
                "Source Name",
                "Source URL",
            ])
            for r in jobs:
                content = r.content if hasattr(r, "content") else r
                c_id = getattr(getattr(r, "_mapping_log", None), "canonical_id", "")
                writer.writerow([
                    content.role_title,
                    content.company,
                    content.raw_company,
                    content.company_domain or "",
                    c_id,
                    content.role_family,
                    content.location or "",
                    content.is_remote,
                    content.salary_text or "",
                    content.posted_date.isoformat(),
                    content.first_seen_at.isoformat(),
                    content.source_name,
                    str(content.source_url),
                ])
        row_counts["AI Jobs"] = len(jobs)

        # 6. Entity Mapping Log Tab
        mapping_file = os.path.join(output_dir, "06_entity_mapping_log.csv")
        mapping_count = 0
        with open(mapping_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Raw Name",
                "Canonical Name",
                "Canonical ID",
                "Entity Type",
                "Resolution Tier",
                "Confidence Score",
                "Signals Evaluated",
                "Method",
            ])
            for cat_list in [startups, products, jobs]:
                for r in cat_list:
                    mlog = getattr(r, "_mapping_log", None)
                    if mlog is not None:
                        writer.writerow([
                            getattr(mlog, "raw_name", ""),
                            getattr(mlog, "canonical_name", "") or "",
                            getattr(mlog, "canonical_id", "") or "",
                            getattr(mlog, "entity_type", ""),
                            getattr(mlog, "resolution_tier", ""),
                            getattr(mlog, "confidence", 0.0),
                            "; ".join(getattr(mlog, "signals_evaluated", [])),
                            getattr(mlog, "method", ""),
                        ])
                        mapping_count += 1
        row_counts["Entity Mapping Log"] = mapping_count

        # 7. Pipeline Run Manifest Tab
        manifest = {
            "run_id": run_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "destination_directory": output_dir,
            "row_counts": row_counts,
            "quality_report": quality_report or {},
        }
        manifest_file = os.path.join(output_dir, "07_pipeline_manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        row_counts["Pipeline Run Manifest"] = 1

        # 8. Upload to Live Google Sheet if credentials and spreadsheet ID are present
        from ai_intel.config import get_settings
        settings = get_settings()
        creds_file = self.service_account_file or settings.google_application_credentials
        sheet_id = settings.google_sheets_spreadsheet_id

        if creds_file and sheet_id and os.path.exists(creds_file):
            try:
                self._upload_to_live_google_sheet(creds_file, sheet_id, output_dir)
            except Exception as exc:
                logger.warning("google_sheets_live_upload_failed", extra={"error": str(exc)})

        logger.info("google_sheets_export_completed", extra={"run_id": run_id, "output_dir": output_dir})

        return ExportResult(
            destination=output_dir,
            row_counts=row_counts,
            status="SUCCESS",
        )

    def _upload_to_live_google_sheet(self, creds_file: str, spreadsheet_id: str, output_dir: str) -> None:
        try:
            import gspread  # type: ignore[import-not-found,import-untyped]
        except ImportError:
            logger.warning("gspread_not_installed_skipping_live_upload")
            return

        gc = gspread.service_account(filename=creds_file)
        sh = gc.open_by_key(spreadsheet_id)

        tab_mapping = {
            "Startups": "01_startups.csv",
            "Products": "02_products.csv",
            "Research Papers": "03_research_papers.csv",
            "AI News": "04_ai_news.csv",
            "AI Jobs": "05_ai_jobs.csv",
            "Entity Mapping Log": "06_entity_mapping_log.csv",
        }

        for tab_name, csv_filename in tab_mapping.items():
            csv_path = os.path.join(output_dir, csv_filename)
            if not os.path.exists(csv_path):
                continue
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = list(csv.reader(f))
            if not reader:
                continue

            try:
                ws = sh.worksheet(tab_name)
                ws.clear()
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title=tab_name, rows=len(reader) + 10, cols=len(reader[0]) + 5)

            ws.update(values=reader, range_name="A1")
            logger.info("google_sheets_tab_updated", extra={"tab": tab_name, "rows": len(reader)})


"""Environment-backed settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ai_intel",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    google_sheets_spreadsheet_id: str | None = Field(
        default=None,
        alias="GOOGLE_SHEETS_SPREADSHEET_ID",
    )
    google_application_credentials: str | None = Field(
        default=None,
        alias="GOOGLE_APPLICATION_CREDENTIALS",
    )
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_api_key_1: str | None = Field(default=None, alias="GROQ_API_KEY_1")
    groq_api_key_2: str | None = Field(default=None, alias="GROQ_API_KEY_2")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")

    @property
    def primary_groq_key(self) -> str | None:
        return self.groq_api_key or self.groq_api_key_1

    arxiv_query: str = Field(
        default="cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.CV OR cat:stat.ML",
        alias="ARXIV_QUERY",
    )
    arxiv_page_size: PositiveInt = Field(default=100, alias="ARXIV_PAGE_SIZE")
    arxiv_polite_delay_seconds: PositiveInt = Field(
        default=3,
        alias="ARXIV_POLITE_DELAY_SECONDS",
    )
    papers_with_code_dataset: str = Field(
        default="pwc-archive/links-between-paper-and-code",
        alias="PAPERS_WITH_CODE_DATASET",
    )
    papers_with_code_config: str = Field(default="default", alias="PAPERS_WITH_CODE_CONFIG")
    papers_with_code_split: str = Field(default="train", alias="PAPERS_WITH_CODE_SPLIT")
    github_api_version: str = Field(default="2022-11-28", alias="GITHUB_API_VERSION")
    yc_companies_endpoint: str = Field(
        default="https://yc-oss.github.io/api/companies/all.json",
        alias="YC_COMPANIES_ENDPOINT",
    )
    wellfound_jobs_url: str = Field(default="https://wellfound.com/jobs", alias="WELLFOUND_JOBS_URL")

    default_http_timeout_seconds: PositiveInt = Field(
        default=30,
        alias="DEFAULT_HTTP_TIMEOUT_SECONDS",
    )
    max_concurrent_requests: PositiveInt = Field(default=50, alias="MAX_CONCURRENT_REQUESTS")
    max_concurrent_llm_requests: PositiveInt = Field(
        default=8,
        alias="MAX_CONCURRENT_LLM_REQUESTS",
    )
    crawl_user_agent: str = Field(
        default="ai-intelligence-pipeline-demo/0.1",
        alias="CRAWL_USER_AGENT",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

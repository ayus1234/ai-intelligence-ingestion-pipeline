"""Tests for job board crawlers."""

from ai_intel.crawlers.jobs import (
    AIJobsCrawler,
    JobicyCrawler,
    MachineLearningJobsCrawler,
    RemoteOKCrawler,
    WellfoundJobsCrawler,
)


def test_aijobs_crawler_fallback() -> None:
    jobs = AIJobsCrawler._fallback_candidates(limit=2)
    assert len(jobs) == 2
    assert jobs[0].role_title == "Senior Machine Learning Engineer"
    assert jobs[0].raw_company_name == "OpenAI"
    assert jobs[0].company_domain == "openai.com"


def test_wellfound_jobs_crawler_fallback() -> None:
    jobs = WellfoundJobsCrawler._fallback_candidates(limit=2)
    assert len(jobs) == 2
    assert jobs[0].role_title == "Lead AI Product Manager"
    assert jobs[0].raw_company_name == "Perplexity"


def test_mljobs_crawler_fallback() -> None:
    jobs = MachineLearningJobsCrawler._fallback_candidates(limit=2)
    assert len(jobs) == 2
    assert jobs[0].role_title == "Deep Learning Researcher"
    assert jobs[0].raw_company_name == "Meta AI"


def test_jobicy_crawler_fallback() -> None:
    jobs = JobicyCrawler._fallback_candidates(limit=2)
    assert len(jobs) == 2
    assert jobs[0].role_title == "Senior AI Infrastructure Architect"
    assert jobs[0].raw_company_name == "Mistral AI"


def test_remoteok_crawler_fallback() -> None:
    jobs = RemoteOKCrawler._fallback_candidates(limit=2)
    assert len(jobs) == 2
    assert jobs[0].role_title == "Lead LLM Evaluation Engineer"
    assert jobs[0].raw_company_name == "Anyscale"

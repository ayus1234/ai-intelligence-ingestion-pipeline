"""AI job board crawlers and role classifier."""

from ai_intel.crawlers.jobs.aijobs import AIJobsCrawler
from ai_intel.crawlers.jobs.classifier import classify_role_family, normalize_role_title
from ai_intel.crawlers.jobs.jobicy import JobicyCrawler
from ai_intel.crawlers.jobs.machinelearningjobs import MachineLearningJobsCrawler
from ai_intel.crawlers.jobs.remoteok import RemoteOKCrawler
from ai_intel.crawlers.jobs.wellfound_jobs import WellfoundJobsCrawler

__all__ = [
    "AIJobsCrawler",
    "JobicyCrawler",
    "MachineLearningJobsCrawler",
    "RemoteOKCrawler",
    "WellfoundJobsCrawler",
    "classify_role_family",
    "normalize_role_title",
]

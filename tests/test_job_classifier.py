"""Tests for role family classifier and title normalization."""

from ai_intel.crawlers.jobs.classifier import classify_role_family, normalize_role_title


def test_normalize_role_title() -> None:
    assert normalize_role_title("Senior Machine Learning Engineer (Remote)") == "senior machine learning engineer"
    assert normalize_role_title("[FULL-TIME] AI Research Scientist") == "ai research scientist"
    assert normalize_role_title("Backend Developer - Python / FastAPI!") == "backend developer - python fastapi"


def test_classify_role_family() -> None:
    assert classify_role_family("Senior Machine Learning Engineer") == "ML Engineer"
    assert classify_role_family("Staff AI Researcher", "Conduct fundamental research on LLMs") == "Research"
    assert classify_role_family("MLOps Platform Lead") == "Infrastructure"
    assert classify_role_family("Full Stack Software Engineer") == "Full Stack"
    assert classify_role_family("Senior Python Backend Developer") == "Backend"
    assert classify_role_family("React Frontend Engineer") == "Frontend"
    assert classify_role_family("Principal Data Engineer") == "Data"
    assert classify_role_family("Group Product Manager - AI Platform") == "Product"
    assert classify_role_family("Lead Product Designer (UI/UX)") == "Design"
    assert classify_role_family("Office Operations Specialist") == "Other"

"""Deterministic role-family classifier and title normalization rules."""

from __future__ import annotations

import re

ROLE_FAMILY_KEYWORDS: list[tuple[str, list[str]]] = [
    (
        "Product",
        [
            "product manager",
            "product lead",
            "product owner",
            "head of product",
            "group product manager",
            "product lead",
        ],
    ),
    (
        "Design",
        [
            "product designer",
            "ux designer",
            "ui designer",
            "graphic designer",
            "creative director",
        ],
    ),
    (
        "ML Engineer",
        [
            "machine learning",
            "ml engineer",
            "ai engineer",
            "deep learning",
            "llm engineer",
            "nlp engineer",
            "computer vision",
            "applied scientist",
            "algorithm engineer",
        ],
    ),
    (
        "Research",
        [
            "research scientist",
            "research engineer",
            "researcher",
            "phd",
            "postdoc",
            "ai researcher",
            "principal scientist",
        ],
    ),
    (
        "Infrastructure",
        [
            "devops",
            "mlops",
            "infrastructure",
            "platform engineer",
            "platform lead",
            "sre",
            "site reliability",
            "cloud engineer",
            "systems engineer",
            "kubernetes",
        ],
    ),
    (
        "Full Stack",
        [
            "fullstack",
            "full stack",
            "full-stack",
        ],
    ),
    (
        "Backend",
        [
            "backend",
            "back end",
            "python engineer",
            "python developer",
            "golang",
            "java engineer",
            "api engineer",
            "server engineer",
        ],
    ),
    (
        "Frontend",
        [
            "frontend",
            "front end",
            "react engineer",
            "vue engineer",
            "ui engineer",
            "web developer",
        ],
    ),
    (
        "Data",
        [
            "data engineer",
            "data analyst",
            "data scientist",
            "bi engineer",
            "analytics engineer",
            "database administrator",
        ],
    ),
]


def normalize_role_title(title: str) -> str:
    """Normalize role title for canonical comparison (e.g., 'Senior ML Engineer (Remote)' -> 'senior ml engineer')."""
    if not title:
        return ""
    text = title.lower().strip()
    # Remove parenthetical tags like (Remote), (Full Time), (US/Canada)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    # Remove non-alphanumeric chars except space and hyphen
    text = re.sub(r"[^a-z0-9\s\-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or title.lower().strip()


def classify_role_family(role_title: str, description: str = "") -> str:
    """Classify role family deterministically based on keyword priorities."""
    title_lowered = role_title.lower()
    for family, keywords in ROLE_FAMILY_KEYWORDS:
        for kw in keywords:
            if kw in title_lowered:
                return family

    desc_lowered = description.lower()
    for family, keywords in ROLE_FAMILY_KEYWORDS:
        for kw in keywords:
            if kw in desc_lowered:
                return family

    return "Other"

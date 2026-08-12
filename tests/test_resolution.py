from __future__ import annotations

from ai_intel.resolution import EntityResolver, normalize_entity_name


def test_normalize_entity_name_removes_legal_suffixes_and_spacing() -> None:
    assert normalize_entity_name("OpenAI, Inc.") == "openai"
    assert normalize_entity_name("Open AI") == "openai"


def test_resolver_maps_openai_variants() -> None:
    resolver = EntityResolver()

    assert resolver.resolve("OpenAI, Inc.").canonical_name == "OpenAI"
    assert resolver.resolve("Open AI").canonical_name == "OpenAI"


def test_resolver_leaves_low_confidence_names_unresolved() -> None:
    resolver = EntityResolver()
    result = resolver.resolve("Completely Different Ventures")
    assert result.canonical_name is None
    assert result.method == "unresolved"


"""Tests for hardened EntityResolver, Alias Graph, Canonical IDs, and multi-signal audit logs."""

from ai_intel.resolution import AliasGraph, EntityResolver, generate_canonical_id


def test_generate_canonical_id() -> None:
    assert generate_canonical_id("startup", "OpenAI, Inc.") == "ent_startup_openai"
    assert generate_canonical_id("product", "ChatGPT Assistant Pro") == "ent_product_chatgpt_assistant_pro"
    assert generate_canonical_id("startup", "Pinecone Systems LLC") == "ent_startup_pinecone"


def test_alias_graph() -> None:
    graph = AliasGraph()
    graph.add_alias("OpenAI", "OpenAI Inc.")
    graph.add_alias("OpenAI", "Open AI")

    assert graph.get_canonical("OpenAI Inc.") == "OpenAI"
    assert graph.get_canonical("Open AI") == "OpenAI"
    assert "OpenAI Inc." in graph.get_aliases("OpenAI")


def test_multi_signal_entity_resolver() -> None:
    resolver = EntityResolver()

    # Signal 1: Domain Match
    res1 = resolver.resolve("Unknown AI Vendor", company_domain="openai.com")
    assert res1.canonical_name == "OpenAI"
    assert res1.canonical_id == "ent_startup_openai"
    assert res1.resolution_tier == "domain"
    assert res1.confidence == 1.0

    # Signal 2: Exact Alias Graph Match
    res2 = resolver.resolve("OpenAI Inc.")
    assert res2.canonical_name == "OpenAI"
    assert res2.canonical_id == "ent_startup_openai"
    assert res2.resolution_tier == "alias"
    assert res2.confidence == 0.98

    # Signal 3: GitHub Org Context Match
    res3 = resolver.resolve("Custom Org Name", context={"github_org": "openai.com"})
    assert res3.canonical_name == "OpenAI"
    assert res3.resolution_tier == "github_org"

    # Signal 4: Fuzzy Match
    res4 = resolver.resolve("Anthropic PBC AI")
    assert res4.canonical_name == "Anthropic"
    assert res4.resolution_tier in {"alias", "fuzzy"}

    # Signal 5: Unresolved Fallback
    res5 = resolver.resolve("Totally Anonymous Startup 99")
    assert res5.canonical_name is None
    assert res5.canonical_id == "ent_startup_totally_anonymous_startup_99"
    assert res5.resolution_tier == "unresolved"
    assert res5.confidence == 0.0

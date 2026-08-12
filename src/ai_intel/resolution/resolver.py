"""Hardened Entity Resolver with multi-signal matching, Alias Graph, and canonical IDs."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ai_intel.resolution.alias_graph import AliasGraph
from ai_intel.resolution.canonical_id import generate_canonical_id
from ai_intel.resolution.normalizer import normalize_entity_name
from ai_intel.resolution.seed_entities import SEED_ENTITIES

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    raw_name: str
    canonical_name: str | None
    canonical_id: str | None
    entity_type: str
    confidence: float
    method: str
    resolution_tier: str
    normalized_name: str
    signals_evaluated: list[str] = field(default_factory=list)

    @property
    def is_resolved(self) -> bool:
        return self.canonical_name is not None


class EntityResolver:
    def __init__(
        self,
        seed_entities: tuple[str, ...] = SEED_ENTITIES,
        auto_threshold: float = 0.95,
        contextual_threshold: float = 0.85,
        alias_graph: AliasGraph | None = None,
    ) -> None:
        self.auto_threshold = auto_threshold
        self.contextual_threshold = contextual_threshold
        self.alias_graph = alias_graph or AliasGraph()
        self._canonical_by_normalized: dict[str, str] = {}

        for entity in seed_entities:
            norm = normalize_entity_name(entity)
            if norm:
                self._canonical_by_normalized[norm] = entity
                self.alias_graph.add_alias(entity, entity)

        # Pre-seed common tech aliases
        self._seed_default_aliases()

    def _seed_default_aliases(self) -> None:
        aliases = [
            ("OpenAI", "OpenAI Inc."),
            ("OpenAI", "OpenAI, Inc."),
            ("OpenAI", "Open AI"),
            ("OpenAI", "OpenAI Research"),
            ("OpenAI", "openai.com"),
            ("Anthropic", "Anthropic PBC"),
            ("Anthropic", "Anthropic AI"),
            ("Anthropic", "anthropic.com"),
            ("Google", "Google LLC"),
            ("Google", "Google Inc."),
            ("Google", "Google Cloud"),
            ("Google", "google.com"),
            ("Microsoft", "Microsoft Corporation"),
            ("Microsoft", "Microsoft Corp."),
            ("Microsoft", "Microsoft Inc."),
            ("Microsoft", "microsoft.com"),
            ("Meta", "Meta Platforms, Inc."),
            ("Meta", "Meta Platforms Inc."),
            ("Meta", "Meta Platforms"),
            ("Meta", "meta.com"),
            ("Alibaba Cloud", "Alibaba Cloud Computing Ltd."),
            ("Alibaba Cloud", "Alibaba Group"),
            ("Alibaba Cloud", "alibaba.com"),
            ("Stability AI", "Stability AI Ltd."),
            ("Stability AI", "Stability.ai"),
            ("Midjourney", "Midjourney Inc."),
            ("Midjourney", "Midjourney, Inc."),
            ("ElevenLabs", "ElevenLabs Inc."),
            ("ElevenLabs", "ElevenLabs, Inc."),
            ("Runway", "Runway AI, Inc."),
            ("Runway", "Runway ML"),
            ("DeepSeek", "DeepSeek Inc."),
            ("DeepSeek", "DeepSeek AI"),
            ("Pika Labs", "Pika Labs, Inc."),
            ("Pika Labs", "Pika AI"),
            ("Suno AI", "Suno AI Inc."),
            ("Suno AI", "Suno"),
            ("Udio", "Uncharted Labs, Inc. (Udio)"),
            ("Udio", "Uncharted Labs"),
            ("Kuaishou", "Kuaishou Technology Ltd."),
            ("Kuaishou", "Kuaishou Tech"),
            ("Black Forest Labs", "Black Forest Labs GmbH"),
            ("Ideogram", "Ideogram AI Inc."),
            ("Luma AI", "Luma AI Inc."),
            ("Jasper", "Jasper AI Inc."),
            ("Copy.ai", "Copy.ai Inc."),
            ("Descript", "Descript Inc."),
            ("HeyGen", "HeyGen Inc."),
            ("Synthesia", "Synthesia Ltd."),
            ("Anysphere", "Anysphere Inc. (Cursor)"),
            ("Replit", "Replit Inc."),
            ("Vercel", "Vercel Inc."),
            ("StackBlitz", "StackBlitz Inc."),
            ("Cognition", "Cognition AI Inc."),
            ("Harvey", "Harvey AI Inc."),
            ("Pinecone", "Pinecone Systems, Inc."),
            ("Pinecone", "Pinecone Systems"),
            ("Pinecone", "pinecone.io"),
            ("Qdrant", "Qdrant Solutions GmbH"),
            ("Zilliz", "Zilliz Inc."),
            ("Chroma", "Chroma Inc."),
            ("Weaviate", "Weaviate B.V."),
            ("LangChain", "LangChain, Inc."),
            ("LangChain", "LangChain Inc."),
            ("LlamaIndex", "LlamaIndex Inc."),
            ("CrewAI", "CrewAI Inc."),
            ("Ollama", "Ollama Inc."),
            ("Hugging Face", "Hugging Face, Inc."),
            ("Hugging Face", "Hugging Face Inc."),
            ("Baidu", "Baidu Inc."),
            ("ByteDance", "ByteDance Ltd."),
            ("Tencent", "Tencent Holdings Ltd."),
            ("Perplexity", "Perplexity AI Inc."),
            ("Perplexity", "Perplexity AI"),
            ("Perplexity", "perplexity.ai"),
            ("Mistral AI", "Mistral AI SAS"),
            ("Mistral AI", "Mistral"),
            ("Mistral AI", "mistral.ai"),
            ("Otter.ai", "Otter.ai Inc."),
            ("Character.AI", "Character Technologies Inc."),
            ("Langfuse", "Langfuse GmbH"),
            ("Cerebras", "Cerebras Systems Inc."),
            ("Murf", "Murf AI Inc."),
            ("Krea", "Krea AI Inc."),
            ("Phind", "Phind Inc."),
            ("Photoroom", "Photoroom SAS"),
            ("You.com", "SuSea, Inc. (You.com)"),
            ("Zapier", "Zapier Inc."),
            ("Roboflow", "Roboflow, Inc."),
            ("Fireflies", "Fireflies.ai Corp."),
            ("Captions Inc.", "Captions AI Inc."),
            ("Play.ht", "Play.ht Inc."),
            ("Topaz Labs", "Topaz Labs LLC"),
            ("InVideo", "InVideo Inc."),
            ("Superhuman", "Superhuman Corp."),
            ("Labelbox", "Labelbox, Inc."),
            ("OpusPro", "OpusPro Inc."),
            ("Make", "Make Inc."),
            ("Portkey", "Portkey AI Inc."),
            ("Raycast", "Raycast Technologies Ltd."),
            ("Unsloth AI", "Unsloth AI Inc."),
            ("Quora", "Quora, Inc."),
            ("RunPod", "RunPod Inc."),
            ("Significant Gravitas", "Significant Gravitas Ltd."),
            ("Luka Inc.", "Luka, Inc."),
            ("PromptLayer", "PromptLayer Inc."),
            ("Palantir", "Palantir Technologies Inc."),
        ]
        for canon, alias in aliases:
            self.alias_graph.add_alias(canon, alias)
            norm_alias = normalize_entity_name(alias)
            if norm_alias:
                self._canonical_by_normalized[norm_alias] = canon

    def resolve(
        self,
        raw_name: str,
        entity_type: str = "startup",
        context: dict[str, str] | None = None,
        company_domain: str | None = None,
    ) -> ResolutionResult:
        context = context or {}
        signals: list[str] = []
        normalized = normalize_entity_name(raw_name)

        if not normalized and not company_domain:
            return ResolutionResult(
                raw_name=raw_name,
                canonical_name=None,
                canonical_id=None,
                entity_type=entity_type,
                confidence=0.0,
                method="empty_input",
                resolution_tier="unresolved",
                normalized_name="",
                signals_evaluated=["empty_input"],
            )

        # Signal 1: Domain Match
        domain = company_domain or context.get("company_domain") or context.get("domain")
        if domain:
            signals.append(f"signal:domain({domain})")
            canon_from_domain = self.alias_graph.get_canonical(domain)
            if canon_from_domain:
                cid = generate_canonical_id(entity_type, canon_from_domain)
                return ResolutionResult(
                    raw_name=raw_name,
                    canonical_name=canon_from_domain,
                    canonical_id=cid,
                    entity_type=entity_type,
                    confidence=1.0,
                    method="domain_match",
                    resolution_tier="domain",
                    normalized_name=normalized,
                    signals_evaluated=signals,
                )

        # Signal 2: Exact Alias Graph Match
        canon_alias = self.alias_graph.get_canonical(raw_name)
        if canon_alias:
            signals.append(f"signal:alias_graph({raw_name})")
            cid = generate_canonical_id(entity_type, canon_alias)
            return ResolutionResult(
                raw_name=raw_name,
                canonical_name=canon_alias,
                canonical_id=cid,
                entity_type=entity_type,
                confidence=0.98,
                method="exact_alias_graph",
                resolution_tier="alias",
                normalized_name=normalized,
                signals_evaluated=signals,
            )

        # Signal 3: Exact Normalized Name Match
        exact = self._canonical_by_normalized.get(normalized)
        if exact:
            signals.append(f"signal:exact_normalized({normalized})")
            cid = generate_canonical_id(entity_type, exact)
            return ResolutionResult(
                raw_name=raw_name,
                canonical_name=exact,
                canonical_id=cid,
                entity_type=entity_type,
                confidence=0.98,
                method="exact_normalized",
                resolution_tier="alias",
                normalized_name=normalized,
                signals_evaluated=signals,
            )

        # Signal 4: GitHub Org / YC Slug Context Match
        gh_org = context.get("github_org")
        if gh_org:
            signals.append(f"signal:github_org({gh_org})")
            canon_gh = self.alias_graph.get_canonical(gh_org)
            if canon_gh:
                cid = generate_canonical_id(entity_type, canon_gh)
                return ResolutionResult(
                    raw_name=raw_name,
                    canonical_name=canon_gh,
                    canonical_id=cid,
                    entity_type=entity_type,
                    confidence=0.95,
                    method="github_org_match",
                    resolution_tier="github_org",
                    normalized_name=normalized,
                    signals_evaluated=signals,
                )

        yc_slug = context.get("yc_slug")
        if yc_slug:
            signals.append(f"signal:yc_slug({yc_slug})")
            canon_yc = self.alias_graph.get_canonical(yc_slug)
            if canon_yc:
                cid = generate_canonical_id(entity_type, canon_yc)
                return ResolutionResult(
                    raw_name=raw_name,
                    canonical_name=canon_yc,
                    canonical_id=cid,
                    entity_type=entity_type,
                    confidence=0.95,
                    method="yc_slug_match",
                    resolution_tier="yc_slug",
                    normalized_name=normalized,
                    signals_evaluated=signals,
                )

        # Signal 5: Fuzzy Similarity Match
        best_name: str | None = None
        best_score = 0.0
        for canonical_norm, canonical in self._canonical_by_normalized.items():
            score = self._score(normalized, canonical_norm)
            if score > best_score:
                best_score = score
                best_name = canonical

        if best_name and best_score >= self.contextual_threshold:
            signals.append(f"signal:fuzzy_similarity({best_score:.2f})")
            cid = generate_canonical_id(entity_type, best_name)
            return ResolutionResult(
                raw_name=raw_name,
                canonical_name=best_name,
                canonical_id=cid,
                entity_type=entity_type,
                confidence=round(best_score, 2),
                method="fuzzy_similarity",
                resolution_tier="fuzzy",
                normalized_name=normalized,
                signals_evaluated=signals,
            )

        # Signal 6: Unresolved Fallback
        signals.append("signal:unresolved")
        cid = generate_canonical_id(entity_type, raw_name) if raw_name else None
        return ResolutionResult(
            raw_name=raw_name,
            canonical_name=None,
            canonical_id=cid,
            entity_type=entity_type,
            confidence=0.0,
            method="unresolved",
            resolution_tier="unresolved",
            normalized_name=normalized,
            signals_evaluated=signals,
        )

    @staticmethod
    def _score(left: str, right: str) -> float:
        if fuzz is not None:
            return fuzz.ratio(left, right) / 100.0
        return SequenceMatcher(None, left, right).ratio()

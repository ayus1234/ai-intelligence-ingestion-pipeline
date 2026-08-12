"""Entity resolution helpers, Alias Graph, and Canonical ID generator."""

from ai_intel.resolution.alias_graph import AliasGraph
from ai_intel.resolution.canonical_id import generate_canonical_id
from ai_intel.resolution.normalizer import clean_canonical_name, normalize_entity_name
from ai_intel.resolution.resolver import EntityResolver, ResolutionResult
from ai_intel.resolution.seed_entities import SEED_ENTITIES

__all__ = [
    "AliasGraph",
    "EntityResolver",
    "ResolutionResult",
    "SEED_ENTITIES",
    "clean_canonical_name",
    "generate_canonical_id",
    "normalize_entity_name",
]

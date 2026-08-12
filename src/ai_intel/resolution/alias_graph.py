"""Alias Graph for bi-directional entity mapping."""

from __future__ import annotations


class AliasGraph:
    def __init__(self) -> None:
        self._alias_to_canonical: dict[str, str] = {}
        self._canonical_to_aliases: dict[str, set[str]] = {}

    def add_alias(self, canonical_name: str, alias: str) -> None:
        """Add an alias mapping to a canonical entity name."""
        if not canonical_name or not alias:
            return
        canon_key = canonical_name.strip()
        alias_key = alias.lower().strip()

        self._alias_to_canonical[alias_key] = canon_key
        self._alias_to_canonical[canon_key.lower()] = canon_key

        if canon_key not in self._canonical_to_aliases:
            self._canonical_to_aliases[canon_key] = set()
        self._canonical_to_aliases[canon_key].add(alias.strip())

    def get_canonical(self, name_or_alias: str) -> str | None:
        """Resolve a name or alias to its canonical entity name if registered."""
        if not name_or_alias:
            return None
        return self._alias_to_canonical.get(name_or_alias.lower().strip())

    def get_aliases(self, canonical_name: str) -> set[str]:
        """Retrieve all known aliases for a canonical entity."""
        if not canonical_name:
            return set()
        return self._canonical_to_aliases.get(canonical_name.strip(), set())

    def clear(self) -> None:
        """Clear alias graph."""
        self._alias_to_canonical.clear()
        self._canonical_to_aliases.clear()

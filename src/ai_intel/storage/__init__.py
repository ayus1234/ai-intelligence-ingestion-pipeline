"""Storage interface exports."""

from ai_intel.storage.base import StorageRepository
from ai_intel.storage.memory import InMemoryStorageRepository

__all__ = ["InMemoryStorageRepository", "StorageRepository"]


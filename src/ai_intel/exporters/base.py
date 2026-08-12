"""Export abstraction for Google Sheets and other destinations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExportResult:
    destination: str
    row_counts: dict[str, int]
    status: str


class Exporter(ABC):
    @abstractmethod
    async def export(self, run_id: str, destination: str) -> ExportResult:
        raise NotImplementedError


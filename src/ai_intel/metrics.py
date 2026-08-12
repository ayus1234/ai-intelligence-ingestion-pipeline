"""Observability and Prometheus-compatible metrics registry."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


class MetricsCollector:
    _instance: MetricsCollector | None = None

    def __new__(cls) -> MetricsCollector:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_metrics()
        return cls._instance

    def _init_metrics(self) -> None:
        self.queue_depth: dict[str, float] = {}
        self.provider_requests: dict[tuple[str, str], int] = defaultdict(int)  # (provider, status) -> count
        self.entity_resolution_tiers: dict[str, int] = defaultdict(int)  # tier -> count
        self.crawl_latencies: list[float] = []
        self.extraction_latencies: list[float] = []

    def set_queue_depth(self, source: str, depth: float) -> None:
        """Set current queue depth gauge for a given crawler source."""
        self.queue_depth[source] = depth

    def record_provider_status(self, provider: str, status: str) -> None:
        """Record counter for LLM provider invocation status."""
        self.provider_requests[(provider.lower(), status.lower())] += 1

    def record_entity_resolution_tier(self, tier: str) -> None:
        """Record counter for entity resolution tier."""
        self.entity_resolution_tiers[tier.lower()] += 1

    def record_crawl_latency(self, seconds: float) -> None:
        """Record crawl latency sample."""
        self.crawl_latencies.append(seconds)

    def record_extraction_latency(self, seconds: float) -> None:
        """Record LLM extraction latency sample."""
        self.extraction_latencies.append(seconds)

    def export_prometheus_text(self) -> str:
        """Generate Prometheus exposition text format."""
        lines: list[str] = [
            "# HELP queue_depth_total Current queue depth per crawling source.",
            "# TYPE queue_depth_total gauge",
        ]
        for src, depth in self.queue_depth.items():
            lines.append(f'queue_depth_total{{source="{src}"}} {depth}')

        lines.extend([
            "# HELP provider_success_rates_total Total invocations by provider and status.",
            "# TYPE provider_success_rates_total counter",
        ])
        for (provider, status), count in self.provider_requests.items():
            lines.append(f'provider_success_rates_total{{provider="{provider}",status="{status}"}} {count}')

        lines.extend([
            "# HELP entity_resolution_tier_distribution_total Distribution of entity resolution tiers.",
            "# TYPE entity_resolution_tier_distribution_total counter",
        ])
        for tier, count in self.entity_resolution_tiers.items():
            lines.append(f'entity_resolution_tier_distribution_total{{tier="{tier}"}} {count}')

        if self.crawl_latencies:
            avg_crawl = sum(self.crawl_latencies) / len(self.crawl_latencies)
            lines.extend([
                "# HELP crawl_latency_seconds Average crawl latency in seconds.",
                "# TYPE crawl_latency_seconds summary",
                f"crawl_latency_seconds_sum {sum(self.crawl_latencies):.4f}",
                f"crawl_latency_seconds_count {len(self.crawl_latencies)}",
            ])

        if self.extraction_latencies:
            lines.extend([
                "# HELP extraction_latency_seconds Average LLM extraction latency in seconds.",
                "# TYPE extraction_latency_seconds summary",
                f"extraction_latency_seconds_sum {sum(self.extraction_latencies):.4f}",
                f"extraction_latency_seconds_count {len(self.extraction_latencies)}",
            ])

        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """Reset metrics data."""
        self._init_metrics()


metrics_collector = MetricsCollector()

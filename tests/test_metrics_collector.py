"""Tests for MetricsCollector and Prometheus exposition text output."""

from ai_intel.metrics import metrics_collector


def test_metrics_collector() -> None:
    metrics_collector.reset()

    metrics_collector.set_queue_depth("arxiv", 15)
    metrics_collector.record_provider_status("gemini", "success")
    metrics_collector.record_entity_resolution_tier("domain")
    metrics_collector.record_crawl_latency(0.45)
    metrics_collector.record_extraction_latency(1.2)

    text = metrics_collector.export_prometheus_text()

    assert 'queue_depth_total{source="arxiv"} 15' in text
    assert 'provider_success_rates_total{provider="gemini",status="success"} 1' in text
    assert 'entity_resolution_tier_distribution_total{tier="domain"} 1' in text
    assert "crawl_latency_seconds_sum" in text
    assert "extraction_latency_seconds_sum" in text

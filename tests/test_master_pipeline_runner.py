"""Tests for MasterPipelineRunner."""

import tempfile

import pytest

from ai_intel.pipelines.runner import MasterPipelineRunner


@pytest.mark.asyncio
async def test_master_pipeline_runner_run_all() -> None:
    runner = MasterPipelineRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = await runner.run_all(hours=24, limit=10, dry_run=True, export_destination=tmp_dir)

        assert res.status == "COMPLETED"
        assert res.total_records > 0
        assert "papers" in res.vertical_counts
        assert "startups" in res.vertical_counts
        assert "products" in res.vertical_counts
        assert "news" in res.vertical_counts
        assert "jobs" in res.vertical_counts
        assert res.quality_report is not None

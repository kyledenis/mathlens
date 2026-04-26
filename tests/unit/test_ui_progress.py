"""Tests for mathlens.ui.progress pipeline display helpers."""

from mathlens.models import PipelineMode, PipelineStage
from mathlens.ui.progress import PipelineProgress, STAGE_LABELS


class TestPipelineProgress:
    def test_all_stages_have_labels(self):
        for stage in PipelineStage:
            assert stage in STAGE_LABELS

    def test_format_stage_done_contains_duration(self):
        progress = PipelineProgress()
        result = progress.format_stage_done(PipelineStage.visualization, 90.0)
        assert "1m" in result

    def test_format_stage_start_shows_estimate_with_provider(self):
        progress = PipelineProgress(PipelineMode.explore, provider="cli")
        result = progress.format_stage_start(PipelineStage.visualization)
        assert "~" in result

    def test_format_total_estimate(self):
        progress = PipelineProgress(PipelineMode.explore, provider="cli")
        result = progress.format_total_estimate()
        assert "Estimated" in result

    def test_different_providers_have_different_estimates(self):
        api = PipelineProgress(PipelineMode.explore, provider="api")
        local = PipelineProgress(PipelineMode.explore, provider="local")
        assert local.estimate_for(PipelineStage.visualization) > api.estimate_for(PipelineStage.visualization)

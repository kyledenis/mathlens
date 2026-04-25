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

    def test_format_stage_start_shows_estimate(self):
        progress = PipelineProgress(PipelineMode.explore)
        result = progress.format_stage_start(PipelineStage.visualization)
        assert "~" in result  # shows estimated time

    def test_format_total_estimate(self):
        progress = PipelineProgress(PipelineMode.explore)
        result = progress.format_total_estimate()
        assert "Estimated" in result

    def test_deep_mode_has_higher_estimates(self):
        explore = PipelineProgress(PipelineMode.explore)
        deep = PipelineProgress(PipelineMode.deep)
        assert deep.estimate_for(PipelineStage.visualization) > explore.estimate_for(PipelineStage.visualization)

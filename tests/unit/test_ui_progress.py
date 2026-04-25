"""Tests for mathlens.ui.progress pipeline display helpers."""

from mathlens.models import PipelineStage
from mathlens.ui.progress import PipelineProgress, STAGE_LABELS


class TestPipelineProgress:
    def test_all_stages_have_labels(self):
        for stage in PipelineStage:
            assert stage in STAGE_LABELS

    def test_format_stage_done_contains_duration(self):
        progress = PipelineProgress()
        result = progress.format_stage_done(PipelineStage.visualization, 90.0)
        assert "1m" in result

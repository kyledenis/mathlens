"""Tests for mathlens.ui.progress pipeline display helpers."""

import pytest

from mathlens.models import PipelineStage
from mathlens.ui.progress import (
    STAGE_DONE_MARKERS,
    STAGE_LABELS,
    STAGE_MARKERS,
    PipelineProgress,
)


class TestStageMappings:
    def test_all_stages_have_labels(self):
        for stage in PipelineStage:
            assert stage in STAGE_LABELS

    def test_all_stages_have_markers(self):
        for stage in PipelineStage:
            assert stage in STAGE_MARKERS

    def test_all_stages_have_done_markers(self):
        for stage in PipelineStage:
            assert stage in STAGE_DONE_MARKERS

    def test_planning_label(self):
        assert STAGE_LABELS[PipelineStage.planning] == "Planning"

    def test_verification_label(self):
        assert STAGE_LABELS[PipelineStage.verification] == "Verifying"

    def test_visualization_label(self):
        assert STAGE_LABELS[PipelineStage.visualization] == "Visualizing"

    def test_summarization_label(self):
        assert STAGE_LABELS[PipelineStage.summarization] == "Summarizing"

    def test_markers_are_not_emoji(self):
        for marker in STAGE_MARKERS.values():
            assert ">" in marker  # text-based marker


class TestPipelineProgress:
    def setup_method(self):
        self.progress = PipelineProgress()

    def test_label_for_planning(self):
        assert self.progress.label_for(PipelineStage.planning) == "Planning"

    def test_label_for_verification(self):
        assert self.progress.label_for(PipelineStage.verification) == "Verifying"

    def test_format_stage_start_contains_label(self):
        result = self.progress.format_stage_start(PipelineStage.planning)
        assert "Planning" in result

    def test_format_stage_start_ends_with_ellipsis(self):
        result = self.progress.format_stage_start(PipelineStage.verification)
        assert result.endswith("...")

    def test_format_stage_done_contains_label(self):
        result = self.progress.format_stage_done(PipelineStage.verification, 3.5)
        assert "Verifying" in result

    def test_format_stage_done_contains_duration_seconds(self):
        result = self.progress.format_stage_done(PipelineStage.planning, 5.0)
        assert "5.0s" in result

    def test_format_stage_done_contains_duration_minutes(self):
        result = self.progress.format_stage_done(PipelineStage.visualization, 90.0)
        assert "1m" in result

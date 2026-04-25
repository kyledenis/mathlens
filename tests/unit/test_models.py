"""Unit tests for mathlens domain models."""

import pytest
from datetime import datetime

from mathlens.models import (
    VerificationStatus,
    PipelineMode,
    PipelineStage,
    StageStatus,
    Badge,
    VerificationResult,
    ExplorationMeta,
)


# ---------------------------------------------------------------------------
# PipelineStage.next property (actual logic)
# ---------------------------------------------------------------------------

class TestPipelineStageNext:
    def test_next_chain(self):
        assert PipelineStage.planning.next == PipelineStage.verification
        assert PipelineStage.verification.next == PipelineStage.visualization
        assert PipelineStage.visualization.next == PipelineStage.summarization
        assert PipelineStage.summarization.next is None


# ---------------------------------------------------------------------------
# Badge.from_status (mapping logic)
# ---------------------------------------------------------------------------

class TestBadgeFromStatus:
    def test_all_status_mappings(self):
        assert Badge.from_status(VerificationStatus.verified) == Badge.verified
        assert Badge.from_status(VerificationStatus.unverifiable) == Badge.unverified
        assert Badge.from_status(VerificationStatus.refuted) == Badge.refuted
        assert Badge.from_status(VerificationStatus.skipped) == Badge.unchecked


# ---------------------------------------------------------------------------
# VerificationResult.should_halt (computed property logic)
# ---------------------------------------------------------------------------

class TestVerificationResult:
    def test_should_halt_only_for_refuted(self):
        for status, expected in [
            (VerificationStatus.verified, False),
            (VerificationStatus.unverifiable, False),
            (VerificationStatus.skipped, False),
            (VerificationStatus.refuted, True),
        ]:
            result = VerificationResult(
                status=status, lean_output="", duration_seconds=0.0,
            )
            assert result.should_halt is expected, f"should_halt wrong for {status}"


# ---------------------------------------------------------------------------
# ExplorationMeta stage progression and resumability (actual logic)
# ---------------------------------------------------------------------------

class TestExplorationMeta:
    def test_complete_stage_advances_current(self):
        meta = ExplorationMeta(
            topic="Test", slug="test", mode=PipelineMode.explore,
        )
        meta.complete_stage(PipelineStage.planning)
        assert PipelineStage.planning in meta.completed_stages
        assert meta.current_stage == PipelineStage.verification

    def test_complete_final_stage(self):
        meta = ExplorationMeta(
            topic="Test", slug="test", mode=PipelineMode.explore,
            current_stage=PipelineStage.summarization,
        )
        meta.complete_stage(PipelineStage.summarization)
        assert PipelineStage.summarization in meta.completed_stages

    def test_full_stage_progression(self):
        meta = ExplorationMeta(
            topic="Test", slug="test", mode=PipelineMode.deep,
        )
        for stage in [PipelineStage.planning, PipelineStage.verification, PipelineStage.visualization]:
            meta.complete_stage(stage)
        assert len(meta.completed_stages) == 3
        assert meta.current_stage == PipelineStage.summarization

    def test_is_resumable(self):
        for status, expected in [
            (StageStatus.failed, True),
            (StageStatus.running, True),
            (StageStatus.pending, False),
            (StageStatus.completed, False),
        ]:
            meta = ExplorationMeta(
                topic="Test", slug="test", mode=PipelineMode.explore, status=status,
            )
            assert meta.is_resumable is expected, f"is_resumable wrong for {status}"

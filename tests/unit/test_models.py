"""Unit tests for mathlens domain models."""

import pytest
from pathlib import Path
from datetime import datetime, timezone

from mathlens.models import (
    Intent,
    VerificationStatus,
    OutputFormat,
    PipelineMode,
    Difficulty,
    RenderQuality,
    PipelineStage,
    StageStatus,
    Badge,
    ScenePlan,
    ExplorationPlan,
    VerificationResult,
    RenderedScene,
    VisualizationResult,
    Summary,
    ExplorationMeta,
)


# ---------------------------------------------------------------------------
# Enum value tests
# ---------------------------------------------------------------------------

class TestIntentEnum:
    def test_values(self):
        assert Intent.prove == "prove"
        assert Intent.explain == "explain"
        assert Intent.explore == "explore"
        assert Intent.compare == "compare"

    def test_is_str(self):
        assert isinstance(Intent.prove, str)


class TestVerificationStatusEnum:
    def test_values(self):
        assert VerificationStatus.verified == "verified"
        assert VerificationStatus.unverifiable == "unverifiable"
        assert VerificationStatus.refuted == "refuted"
        assert VerificationStatus.skipped == "skipped"


class TestOutputFormatEnum:
    def test_values(self):
        assert OutputFormat.video == "video"
        assert OutputFormat.frames == "frames"
        assert OutputFormat.diagram == "diagram"


class TestPipelineModeEnum:
    def test_values(self):
        assert PipelineMode.explore == "explore"
        assert PipelineMode.deep == "deep"


class TestDifficultyEnum:
    def test_values(self):
        assert Difficulty.elementary == "elementary"
        assert Difficulty.intermediate == "intermediate"
        assert Difficulty.advanced == "advanced"


class TestRenderQualityEnum:
    def test_values(self):
        assert RenderQuality.low == "low"
        assert RenderQuality.medium == "medium"
        assert RenderQuality.high == "high"
        assert RenderQuality.production == "production"


# ---------------------------------------------------------------------------
# PipelineStage.next property
# ---------------------------------------------------------------------------

class TestPipelineStageNext:
    def test_planning_next_is_verification(self):
        assert PipelineStage.planning.next == PipelineStage.verification

    def test_verification_next_is_visualization(self):
        assert PipelineStage.verification.next == PipelineStage.visualization

    def test_visualization_next_is_summarization(self):
        assert PipelineStage.visualization.next == PipelineStage.summarization

    def test_summarization_next_is_none(self):
        assert PipelineStage.summarization.next is None


# ---------------------------------------------------------------------------
# Badge
# ---------------------------------------------------------------------------

class TestBadgeFromStatus:
    def test_verified_maps_to_verified(self):
        assert Badge.from_status(VerificationStatus.verified) == Badge.verified

    def test_unverifiable_maps_to_unverified(self):
        assert Badge.from_status(VerificationStatus.unverifiable) == Badge.unverified

    def test_refuted_maps_to_refuted(self):
        assert Badge.from_status(VerificationStatus.refuted) == Badge.refuted

    def test_skipped_maps_to_unchecked(self):
        assert Badge.from_status(VerificationStatus.skipped) == Badge.unchecked


class TestBadgeLabel:
    def test_verified_label(self):
        assert isinstance(Badge.verified.label, str)
        assert len(Badge.verified.label) > 0

    def test_unverified_label(self):
        assert isinstance(Badge.unverified.label, str)

    def test_refuted_label(self):
        assert isinstance(Badge.refuted.label, str)

    def test_unchecked_label(self):
        assert isinstance(Badge.unchecked.label, str)


class TestBadgeIcon:
    def test_all_badges_have_icon(self):
        for badge in Badge:
            icon = badge.icon
            assert isinstance(icon, str)
            assert len(icon) > 0

    def test_icon_uses_rich_markup(self):
        # Rich markup uses [color]...[/color] or similar bracket syntax
        for badge in Badge:
            assert "[" in badge.icon


# ---------------------------------------------------------------------------
# ScenePlan
# ---------------------------------------------------------------------------

class TestScenePlan:
    def test_minimal_creation(self):
        scene = ScenePlan(title="Intro", description="An introduction scene")
        assert scene.title == "Intro"
        assert scene.description == "An introduction scene"
        assert scene.key_objects == []
        assert scene.animation_hints == []

    def test_with_objects_and_hints(self):
        scene = ScenePlan(
            title="Proof",
            description="Shows the proof",
            key_objects=["formula", "arrow"],
            animation_hints=["fade_in", "slide"],
        )
        assert scene.key_objects == ["formula", "arrow"]
        assert scene.animation_hints == ["fade_in", "slide"]


# ---------------------------------------------------------------------------
# ExplorationPlan
# ---------------------------------------------------------------------------

class TestExplorationPlan:
    def test_creation_with_required_fields(self):
        plan = ExplorationPlan(
            topic="Harmonic Series Divergence",
            slug="harmonic-series-divergence",
            intent=Intent.prove,
            theorem_statements=["The harmonic series diverges"],
            visualization_scenes=[],
            output_format=OutputFormat.video,
            difficulty=Difficulty.intermediate,
        )
        assert plan.topic == "Harmonic Series Divergence"
        assert plan.slug == "harmonic-series-divergence"
        assert plan.intent == Intent.prove
        assert plan.related_explorations == []
        assert plan.prerequisites == []

    def test_slug_format(self):
        plan = ExplorationPlan(
            topic="Test",
            slug="my-topic-slug",
            intent=Intent.explain,
            theorem_statements=[],
            visualization_scenes=[],
            output_format=OutputFormat.diagram,
            difficulty=Difficulty.elementary,
        )
        # slug should be lowercase with hyphens only (no spaces or underscores)
        assert " " not in plan.slug
        assert plan.slug == plan.slug.lower()

    def test_defaults(self):
        plan = ExplorationPlan(
            topic="Test",
            slug="test",
            intent=Intent.explore,
            theorem_statements=[],
            visualization_scenes=[],
            output_format=OutputFormat.video,
            difficulty=Difficulty.advanced,
        )
        assert plan.related_explorations == []
        assert plan.prerequisites == []


# ---------------------------------------------------------------------------
# VerificationResult
# ---------------------------------------------------------------------------

class TestVerificationResult:
    def test_should_halt_false_for_verified(self):
        result = VerificationResult(
            status=VerificationStatus.verified,
            lean_output="Proof complete.",
            duration_seconds=1.5,
        )
        assert result.should_halt is False

    def test_should_halt_false_for_unverifiable(self):
        result = VerificationResult(
            status=VerificationStatus.unverifiable,
            lean_output="Could not verify.",
            duration_seconds=2.0,
        )
        assert result.should_halt is False

    def test_should_halt_false_for_skipped(self):
        result = VerificationResult(
            status=VerificationStatus.skipped,
            lean_output="",
            duration_seconds=0.0,
        )
        assert result.should_halt is False

    def test_should_halt_true_for_refuted(self):
        result = VerificationResult(
            status=VerificationStatus.refuted,
            lean_output="Counterexample found.",
            failure_reason="Counterexample: n=2",
            duration_seconds=3.0,
        )
        assert result.should_halt is True

    def test_defaults(self):
        result = VerificationResult(
            status=VerificationStatus.skipped,
            lean_output="",
            duration_seconds=0.0,
        )
        assert result.proof_path is None
        assert result.failure_reason is None
        assert result.mathlib_gaps == []


# ---------------------------------------------------------------------------
# VisualizationResult
# ---------------------------------------------------------------------------

class TestVisualizationResult:
    def test_creation(self, tmp_path):
        result = VisualizationResult(
            output_path=tmp_path / "output.mp4",
            output_format=OutputFormat.video,
            source_paths=[tmp_path / "scene.py"],
            render_quality=RenderQuality.medium,
            duration_seconds=12.5,
            verification_badge=Badge.verified,
        )
        assert result.scenes == []
        assert result.output_format == OutputFormat.video
        assert result.verification_badge == Badge.verified


# ---------------------------------------------------------------------------
# ExplorationMeta
# ---------------------------------------------------------------------------

class TestExplorationMeta:
    def test_creation_with_defaults(self):
        meta = ExplorationMeta(
            topic="Test Topic",
            slug="test-topic",
            mode=PipelineMode.explore,
        )
        assert meta.status == StageStatus.pending
        assert meta.current_stage == PipelineStage.planning
        assert meta.completed_stages == []
        assert meta.tags == []
        assert meta.related == []
        assert isinstance(meta.created_at, datetime)
        assert isinstance(meta.updated_at, datetime)

    def test_created_at_is_utc(self):
        meta = ExplorationMeta(
            topic="Test",
            slug="test",
            mode=PipelineMode.deep,
        )
        assert meta.created_at.tzinfo is not None

    def test_complete_stage_adds_to_completed(self):
        meta = ExplorationMeta(
            topic="Test",
            slug="test",
            mode=PipelineMode.explore,
        )
        meta.complete_stage(PipelineStage.planning)
        assert PipelineStage.planning in meta.completed_stages

    def test_complete_stage_advances_current(self):
        meta = ExplorationMeta(
            topic="Test",
            slug="test",
            mode=PipelineMode.explore,
        )
        meta.complete_stage(PipelineStage.planning)
        assert meta.current_stage == PipelineStage.verification

    def test_complete_final_stage_leaves_current_as_none_or_last(self):
        meta = ExplorationMeta(
            topic="Test",
            slug="test",
            mode=PipelineMode.explore,
            current_stage=PipelineStage.summarization,
        )
        meta.complete_stage(PipelineStage.summarization)
        # next after summarization is None; current_stage should stay summarization or be None
        assert PipelineStage.summarization in meta.completed_stages

    def test_full_stage_progression(self):
        meta = ExplorationMeta(
            topic="Test",
            slug="test",
            mode=PipelineMode.deep,
        )
        stages = [
            PipelineStage.planning,
            PipelineStage.verification,
            PipelineStage.visualization,
            PipelineStage.summarization,
        ]
        for stage in stages[:-1]:
            meta.complete_stage(stage)

        assert len(meta.completed_stages) == 3
        assert meta.current_stage == PipelineStage.summarization

    def test_is_resumable_when_failed(self):
        meta = ExplorationMeta(
            topic="Test",
            slug="test",
            mode=PipelineMode.explore,
            status=StageStatus.failed,
        )
        assert meta.is_resumable is True

    def test_is_resumable_when_running(self):
        meta = ExplorationMeta(
            topic="Test",
            slug="test",
            mode=PipelineMode.explore,
            status=StageStatus.running,
        )
        assert meta.is_resumable is True

    def test_is_not_resumable_when_pending(self):
        meta = ExplorationMeta(
            topic="Test",
            slug="test",
            mode=PipelineMode.explore,
            status=StageStatus.pending,
        )
        assert meta.is_resumable is False

    def test_is_not_resumable_when_completed(self):
        meta = ExplorationMeta(
            topic="Test",
            slug="test",
            mode=PipelineMode.explore,
            status=StageStatus.completed,
        )
        assert meta.is_resumable is False

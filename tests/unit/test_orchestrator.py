"""Unit tests for the pipeline Orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from mathlens.models import (
    Badge,
    Difficulty,
    ExplorationMeta,
    ExplorationPlan,
    Intent,
    OutputFormat,
    PipelineMode,
    PipelineStage,
    RenderQuality,
    RenderedScene,
    ScenePlan,
    StageStatus,
    Summary,
    VerificationResult,
    VerificationStatus,
    VisualizationResult,
)
from mathlens.pipeline.orchestrator import ExplorationResult, Orchestrator


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_plan() -> ExplorationPlan:
    return ExplorationPlan(
        topic="Pythagorean Theorem",
        slug="pythagorean-theorem",
        intent=Intent.prove,
        theorem_statements=["a² + b² = c² for any right triangle"],
        visualization_scenes=[
            ScenePlan(
                title="Right Triangle",
                description="Show right triangle with squares on each side",
                key_objects=["triangle", "squares"],
                animation_hints=["highlight_hypotenuse"],
            )
        ],
        output_format=OutputFormat.video,
        difficulty=Difficulty.elementary,
    )


def _make_meta(plan: ExplorationPlan) -> ExplorationMeta:
    return ExplorationMeta(
        topic=plan.topic,
        slug=plan.slug,
        mode=PipelineMode.explore,
        status=StageStatus.pending,
    )


def _make_verification(status: VerificationStatus) -> VerificationResult:
    return VerificationResult(
        status=status,
        lean_output="",
        duration_seconds=0.1,
    )


def _make_visualization_result(plan: ExplorationPlan) -> VisualizationResult:
    return VisualizationResult(
        scenes=[
            RenderedScene(
                title="Right Triangle",
                source_path=Path("/tmp/scene_01.py"),
                output_path=Path("/tmp/output.mp4"),
                duration_seconds=0.5,
            )
        ],
        output_path=Path("/tmp/output.mp4"),
        output_format=plan.output_format,
        source_paths=[Path("/tmp/scene_01.py")],
        render_quality=RenderQuality.medium,
        duration_seconds=0.5,
        verification_badge=Badge.verified,
    )


def _make_summary() -> Summary:
    return Summary(
        explanation="The Pythagorean Theorem states that in a right triangle...",
        key_insights=["Proof by area rearrangement", "Generalises to n dimensions"],
    )


@pytest.fixture
def plan() -> ExplorationPlan:
    return _make_plan()


@pytest.fixture
def meta(plan: ExplorationPlan) -> ExplorationMeta:
    return _make_meta(plan)


@pytest.fixture
def mock_planner(plan: ExplorationPlan) -> AsyncMock:
    planner = AsyncMock()
    planner.plan = AsyncMock(return_value=plan)
    return planner


@pytest.fixture
def mock_verifier() -> AsyncMock:
    verifier = AsyncMock()
    verifier.verify = AsyncMock(
        return_value=_make_verification(VerificationStatus.verified)
    )
    return verifier


@pytest.fixture
def mock_visualizer(plan: ExplorationPlan) -> AsyncMock:
    visualizer = AsyncMock()
    visualizer.generate_scene_code = AsyncMock(return_value="from manim import *\n")
    visualizer.render = AsyncMock(return_value=_make_visualization_result(plan))
    return visualizer


@pytest.fixture
def mock_summarizer() -> AsyncMock:
    summarizer = AsyncMock()
    summarizer.summarize = AsyncMock(return_value=_make_summary())
    return summarizer


@pytest.fixture
def mock_store(plan: ExplorationPlan, meta: ExplorationMeta, tmp_path: Path) -> MagicMock:
    store = MagicMock()
    ws_dir = tmp_path / plan.slug
    ws_dir.mkdir(parents=True, exist_ok=True)

    store.create = MagicMock(return_value=meta)
    store.complete_stage = MagicMock(return_value=meta)
    store.set_status = MagicMock(return_value=meta)
    store.save_stage_result = MagicMock()
    store.path_for = MagicMock(return_value=ws_dir)
    return store


@pytest.fixture
def orchestrator(
    mock_planner: AsyncMock,
    mock_verifier: AsyncMock,
    mock_visualizer: AsyncMock,
    mock_summarizer: AsyncMock,
    mock_store: MagicMock,
) -> Orchestrator:
    return Orchestrator(
        planner=mock_planner,
        verifier=mock_verifier,
        visualizer=mock_visualizer,
        summarizer=mock_summarizer,
        store=mock_store,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_success(
    orchestrator: Orchestrator,
    mock_verifier: AsyncMock,
    mock_visualizer: AsyncMock,
    mock_summarizer: AsyncMock,
) -> None:
    result = await orchestrator.run(
        query="Prove the Pythagorean Theorem",
        mode=PipelineMode.explore,
    )

    assert isinstance(result, ExplorationResult)
    assert result.verification.status == VerificationStatus.verified
    assert result.visualization is not None
    assert result.summary is not None
    assert result.duration_seconds >= 0.0


@pytest.mark.asyncio
async def test_pipeline_halts_on_refuted(
    orchestrator: Orchestrator,
    mock_verifier: AsyncMock,
    mock_visualizer: AsyncMock,
    mock_summarizer: AsyncMock,
) -> None:
    """REFUTED verification must halt the pipeline — no visualization or summary."""
    mock_verifier.verify = AsyncMock(
        return_value=_make_verification(VerificationStatus.refuted)
    )

    result = await orchestrator.run(
        query="Prove a false theorem",
        mode=PipelineMode.explore,
    )

    assert result.verification.status == VerificationStatus.refuted
    assert result.visualization is None
    assert result.summary is None
    mock_visualizer.generate_scene_code.assert_not_called()
    mock_visualizer.render.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_continues_on_unverifiable(
    orchestrator: Orchestrator,
    mock_verifier: AsyncMock,
    mock_visualizer: AsyncMock,
) -> None:
    """UNVERIFIABLE should NOT halt the pipeline."""
    mock_verifier.verify = AsyncMock(
        return_value=_make_verification(VerificationStatus.unverifiable)
    )

    result = await orchestrator.run(
        query="Prove something uncertain",
        mode=PipelineMode.explore,
    )

    assert result.verification.status == VerificationStatus.unverifiable
    assert result.visualization is not None
    mock_visualizer.generate_scene_code.assert_called_once()
    mock_visualizer.render.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_stores_checkpoints(
    orchestrator: Orchestrator,
    mock_store: MagicMock,
) -> None:
    """complete_stage must be called at least once per stage that ran."""
    await orchestrator.run(
        query="Prove the Pythagorean Theorem",
        mode=PipelineMode.explore,
    )

    # Planning + Verification + Visualization + Summarization = 4 stages
    assert mock_store.complete_stage.call_count >= 3


@pytest.mark.asyncio
async def test_pipeline_skips_verify_when_requested(
    orchestrator: Orchestrator,
    mock_verifier: AsyncMock,
    mock_visualizer: AsyncMock,
) -> None:
    """skip_verification=True should bypass verifier and produce SKIPPED status."""
    result = await orchestrator.run(
        query="Explore the Pythagorean Theorem",
        mode=PipelineMode.explore,
        skip_verification=True,
    )

    mock_verifier.verify.assert_not_called()
    assert result.verification.status == VerificationStatus.skipped
    # Pipeline should continue to visualization since SKIPPED != REFUTED
    assert result.visualization is not None


@pytest.mark.asyncio
async def test_result_has_plan_and_meta(
    orchestrator: Orchestrator,
    plan: ExplorationPlan,
) -> None:
    result = await orchestrator.run(
        query="Prove the Pythagorean Theorem",
        mode=PipelineMode.explore,
    )

    assert result.plan.topic == plan.topic
    assert result.meta.slug == plan.slug


@pytest.mark.asyncio
async def test_pipeline_sets_completed_status(
    orchestrator: Orchestrator,
    mock_store: MagicMock,
) -> None:
    """Store.set_status(COMPLETED) must be called at end of successful pipeline."""
    await orchestrator.run(
        query="Prove the Pythagorean Theorem",
        mode=PipelineMode.explore,
    )

    status_calls = [c.args[1] for c in mock_store.set_status.call_args_list]
    assert StageStatus.completed in status_calls


@pytest.mark.asyncio
async def test_pipeline_refuted_sets_completed_status(
    orchestrator: Orchestrator,
    mock_verifier: AsyncMock,
    mock_store: MagicMock,
) -> None:
    """Even on REFUTED halt, status must be set to COMPLETED."""
    mock_verifier.verify = AsyncMock(
        return_value=_make_verification(VerificationStatus.refuted)
    )

    await orchestrator.run(
        query="Prove a false claim",
        mode=PipelineMode.explore,
    )

    status_calls = [c.args[1] for c in mock_store.set_status.call_args_list]
    assert StageStatus.completed in status_calls


@pytest.mark.asyncio
async def test_verification_exception_returns_unverifiable(
    orchestrator: Orchestrator,
    mock_verifier: AsyncMock,
    mock_visualizer: AsyncMock,
) -> None:
    """Exceptions during verification should yield UNVERIFIABLE and not halt pipeline."""
    mock_verifier.verify = AsyncMock(side_effect=RuntimeError("Lean crashed"))

    result = await orchestrator.run(
        query="Prove something",
        mode=PipelineMode.explore,
    )

    assert result.verification.status == VerificationStatus.unverifiable
    # Should continue to visualization
    mock_visualizer.generate_scene_code.assert_called_once()


@pytest.mark.asyncio
async def test_summarization_exception_returns_fallback(
    orchestrator: Orchestrator,
    mock_summarizer: AsyncMock,
) -> None:
    """Exceptions during summarization should yield a fallback Summary."""
    mock_summarizer.summarize = AsyncMock(side_effect=RuntimeError("LLM error"))

    result = await orchestrator.run(
        query="Prove the Pythagorean Theorem",
        mode=PipelineMode.explore,
    )

    assert result.summary is not None
    assert isinstance(result.summary, Summary)


@pytest.mark.asyncio
async def test_output_format_passed_to_planner(
    orchestrator: Orchestrator,
    mock_planner: AsyncMock,
) -> None:
    await orchestrator.run(
        query="Prove the Pythagorean Theorem",
        mode=PipelineMode.explore,
        output_format=OutputFormat.frames,
    )

    mock_planner.plan.assert_called_once_with(
        "Prove the Pythagorean Theorem", OutputFormat.frames
    )


# ---------------------------------------------------------------------------
# Search index tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_search_index() -> MagicMock:
    index = MagicMock()
    index.index_exploration = MagicMock()
    return index


@pytest.fixture
def orchestrator_with_index(
    mock_planner: AsyncMock,
    mock_verifier: AsyncMock,
    mock_visualizer: AsyncMock,
    mock_summarizer: AsyncMock,
    mock_store: MagicMock,
    mock_search_index: MagicMock,
) -> Orchestrator:
    return Orchestrator(
        planner=mock_planner,
        verifier=mock_verifier,
        visualizer=mock_visualizer,
        summarizer=mock_summarizer,
        store=mock_store,
        search_index=mock_search_index,
    )


@pytest.mark.asyncio
async def test_index_result_called_on_success(
    orchestrator_with_index: Orchestrator,
    mock_search_index: MagicMock,
    plan: ExplorationPlan,
) -> None:
    """SearchIndex.index_exploration must be called after a successful pipeline run."""
    await orchestrator_with_index.run(
        query="Prove the Pythagorean Theorem",
        mode=PipelineMode.explore,
    )

    mock_search_index.index_exploration.assert_called_once_with(
        plan.slug, mock_search_index.index_exploration.call_args[0][1]
    )


@pytest.mark.asyncio
async def test_index_result_called_on_refuted(
    orchestrator_with_index: Orchestrator,
    mock_verifier: AsyncMock,
    mock_search_index: MagicMock,
    plan: ExplorationPlan,
) -> None:
    """SearchIndex.index_exploration must also be called on the REFUTED early-return path."""
    mock_verifier.verify = AsyncMock(
        return_value=_make_verification(VerificationStatus.refuted)
    )

    await orchestrator_with_index.run(
        query="Prove a false claim",
        mode=PipelineMode.explore,
    )

    mock_search_index.index_exploration.assert_called_once_with(
        plan.slug, mock_search_index.index_exploration.call_args[0][1]
    )

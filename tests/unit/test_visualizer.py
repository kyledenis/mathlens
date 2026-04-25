"""Unit tests for the Visualizer pipeline stage."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mathlens.models import (
    Badge,
    OutputFormat,
    PipelineMode,
    RenderQuality,
    ScenePlan,
    VerificationStatus,
    VisualizationResult,
)
from mathlens.pipeline.visualizer import Visualizer
from mathlens.providers.base import LLMResponse
from tests.fixtures.visualizer_response import SAMPLE_MANIM_SCENE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(content: str = SAMPLE_MANIM_SCENE) -> MagicMock:
    """Build a mock LLMProvider that returns content from complete()."""
    provider = MagicMock()
    provider.complete = AsyncMock(
        return_value=LLMResponse(content=content, model="mock-model")
    )
    return provider


def _make_scene_plan() -> ScenePlan:
    return ScenePlan(
        title="Harmonic Series",
        description="Visualize partial sums of the harmonic series",
        key_objects=["axes", "bar_chart"],
        animation_hints=["animate bars growing", "label each term"],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateSceneCode:
    @pytest.mark.asyncio
    async def test_generate_scene_code(self, tmp_path):
        provider = _make_provider()
        viz = Visualizer(provider=provider, workspace_dir=tmp_path)
        result = await viz.generate_scene_code(
            scenes=[_make_scene_plan()], topic="harmonic-series"
        )
        assert "from manim import" in result
        assert "Scene" in result

    @pytest.mark.asyncio
    async def test_scene_code_saved_to_workspace(self, tmp_path):
        provider = _make_provider()
        viz = Visualizer(provider=provider, workspace_dir=tmp_path)
        await viz.generate_scene_code(
            scenes=[_make_scene_plan()], topic="harmonic-series"
        )
        assert (tmp_path / "scene_01.py").exists()


class TestRender:
    @pytest.mark.asyncio
    async def test_render_success(self, tmp_path):
        provider = _make_provider()
        viz = Visualizer(provider=provider, workspace_dir=tmp_path)

        scene_path = tmp_path / "scene_01.py"
        scene_path.write_text(SAMPLE_MANIM_SCENE)

        output_path = tmp_path / "output.mp4"
        output_path.write_text("fake video data")

        with patch.object(viz, "_run_manim", new=AsyncMock(return_value=(0, "", ""))):
            result = await viz.render(
                scene_path=scene_path,
                output_path=output_path,
                mode=PipelineMode.explore,
                verification_status=VerificationStatus.verified,
                output_format=OutputFormat.video,
            )

        assert isinstance(result, VisualizationResult)
        assert result.output_format == OutputFormat.video
        assert result.verification_badge == Badge.verified

    @pytest.mark.asyncio
    async def test_render_failure_retries_simplified(self, tmp_path):
        provider = _make_provider()
        viz = Visualizer(provider=provider, workspace_dir=tmp_path)

        scene_path = tmp_path / "scene_01.py"
        scene_path.write_text(SAMPLE_MANIM_SCENE)

        simplified_path = tmp_path / "scene_simplified.py"
        simplified_path.write_text(SAMPLE_MANIM_SCENE)

        output_path = tmp_path / "output.mp4"

        run_manim_mock = AsyncMock(
            side_effect=[(1, "", "render error"), (0, "", "")]
        )
        simplified_mock = AsyncMock(return_value=str(simplified_path))

        with (
            patch.object(viz, "_run_manim", new=run_manim_mock),
            patch.object(viz, "_generate_simplified_scene", new=simplified_mock),
        ):
            result = await viz.render(
                scene_path=scene_path,
                output_path=output_path,
                mode=PipelineMode.deep,
                verification_status=VerificationStatus.skipped,
            )

        assert run_manim_mock.call_count == 2
        simplified_mock.assert_awaited_once_with(scene_path)
        assert isinstance(result, VisualizationResult)


class TestQualityHelpers:
    def test_quality_for_mode(self, tmp_path):
        viz = Visualizer(provider=MagicMock(), workspace_dir=tmp_path)
        assert viz._quality_for(PipelineMode.explore) == RenderQuality.medium
        assert viz._quality_for(PipelineMode.deep) == RenderQuality.production

    def test_manim_quality_flag(self, tmp_path):
        viz = Visualizer(provider=MagicMock(), workspace_dir=tmp_path)
        assert viz._manim_quality_flag(RenderQuality.medium) == "-qm"
        assert viz._manim_quality_flag(RenderQuality.production) == "-qh"

"""Tests for mathlens CLI deep command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mathlens.cli.app import app
from mathlens.models import (
    Badge,
    Difficulty,
    ExplorationMeta,
    ExplorationPlan,
    Intent,
    OutputFormat,
    PipelineMode,
    RenderQuality,
    ScenePlan,
    StageStatus,
    VerificationResult,
    VerificationStatus,
    VisualizationResult,
)
from mathlens.pipeline.orchestrator import ExplorationResult
from mathlens.models import Summary


runner = CliRunner()


def _make_exploration_result() -> ExplorationResult:
    """Build a complete ExplorationResult for testing."""
    plan = ExplorationPlan(
        topic="test-topic",
        slug="2026-04-08_test-topic",
        intent=Intent.prove,
        theorem_statements=["Test"],
        visualization_scenes=[ScenePlan(title="s1", description="d1")],
        output_format=OutputFormat.video,
        difficulty=Difficulty.intermediate,
    )
    verification = VerificationResult(
        status=VerificationStatus.verified,
        lean_output="proved",
        duration_seconds=2.0,
    )
    visualization = VisualizationResult(
        output_path=Path("/tmp/out.mp4"),
        output_format=OutputFormat.video,
        source_paths=[Path("/tmp/s.py")],
        render_quality=RenderQuality.production,
        duration_seconds=10.0,
        verification_badge=Badge.verified,
    )
    summary = Summary(
        explanation="Test",
        key_insights=["Insight 1"],
    )
    meta = ExplorationMeta(
        topic="test-topic",
        slug="2026-04-08_test-topic",
        mode=PipelineMode.deep,
        status=StageStatus.completed,
    )
    return ExplorationResult(
        plan=plan,
        verification=verification,
        visualization=visualization,
        summary=summary,
        meta=meta,
        duration_seconds=15.0,
    )


def test_deep_runs() -> None:
    """deep command exits with code 0 on a successful run."""
    mock_result = _make_exploration_result()
    with patch("mathlens.cli.deep.run_deep", return_value=mock_result):
        result = runner.invoke(app, ["deep", "pythagorean theorem"])
    assert result.exit_code == 0


def test_deep_with_no_verify() -> None:
    """deep command accepts --no-verify without error."""
    mock_result = _make_exploration_result()
    with patch("mathlens.cli.deep.run_deep", return_value=mock_result):
        result = runner.invoke(app, ["deep", "triangles", "--no-verify"])
    assert result.exit_code == 0

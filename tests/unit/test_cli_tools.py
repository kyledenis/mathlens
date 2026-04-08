"""Tests for mathlens CLI toolkit commands: prove, viz, vis, summarize."""

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


def _make_verification_result() -> VerificationResult:
    return VerificationResult(
        status=VerificationStatus.verified,
        lean_output="proved",
        duration_seconds=2.0,
    )


def _make_exploration_result() -> ExplorationResult:
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
        status=VerificationStatus.skipped,
        lean_output="",
        failure_reason="Verification skipped by caller",
        duration_seconds=0.0,
    )
    visualization = VisualizationResult(
        output_path=Path("/tmp/out.mp4"),
        output_format=OutputFormat.video,
        source_paths=[Path("/tmp/s.py")],
        render_quality=RenderQuality.medium,
        duration_seconds=10.0,
        verification_badge=Badge.unchecked,
    )
    summary = Summary(
        explanation="Test",
        key_insights=["Insight 1"],
    )
    meta = ExplorationMeta(
        topic="test-topic",
        slug="2026-04-08_test-topic",
        mode=PipelineMode.explore,
        status=StageStatus.completed,
    )
    return ExplorationResult(
        plan=plan,
        verification=verification,
        visualization=visualization,
        summary=summary,
        meta=meta,
        duration_seconds=12.0,
    )


# ---------------------------------------------------------------------------
# TestProveCommand
# ---------------------------------------------------------------------------


class TestProveCommand:
    def test_prove_runs(self) -> None:
        """prove command exits with code 0 on a successful run."""
        mock_result = _make_verification_result()
        with patch("mathlens.cli.tools.run_prove", return_value=mock_result):
            result = runner.invoke(app, ["prove", "1 + 1 = 2"])
        assert result.exit_code == 0

    def test_prove_shows_verified(self) -> None:
        """prove command output contains verification status text."""
        mock_result = _make_verification_result()
        with patch("mathlens.cli.tools.run_prove", return_value=mock_result):
            result = runner.invoke(app, ["prove", "pythagorean theorem"])
        assert result.exit_code == 0
        assert "erified" in result.output

    def test_prove_with_provider_flag(self) -> None:
        """prove command accepts --provider local without error."""
        mock_result = _make_verification_result()
        with patch("mathlens.cli.tools.run_prove", return_value=mock_result):
            result = runner.invoke(app, ["prove", "x > 0", "--provider", "local"])
        assert result.exit_code == 0

    def test_prove_with_local_flag(self) -> None:
        """prove command accepts --local without error."""
        mock_result = _make_verification_result()
        with patch("mathlens.cli.tools.run_prove", return_value=mock_result):
            result = runner.invoke(app, ["prove", "x > 0", "--local"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TestVizCommand
# ---------------------------------------------------------------------------


class TestVizCommand:
    def test_viz_runs(self) -> None:
        """viz command exits with code 0 on a successful run."""
        mock_result = _make_exploration_result()
        with patch("mathlens.cli.tools.run_viz", return_value=mock_result):
            result = runner.invoke(app, ["viz", "circle theorem"])
        assert result.exit_code == 0

    def test_viz_shows_output_path(self) -> None:
        """viz command output contains the output path."""
        mock_result = _make_exploration_result()
        with patch("mathlens.cli.tools.run_viz", return_value=mock_result):
            result = runner.invoke(app, ["viz", "circle theorem"])
        assert result.exit_code == 0
        assert "out.mp4" in result.output

    def test_vis_alias_runs(self) -> None:
        """vis alias runs identically to viz."""
        mock_result = _make_exploration_result()
        with patch("mathlens.cli.tools.run_viz", return_value=mock_result):
            result = runner.invoke(app, ["vis", "circle theorem"])
        assert result.exit_code == 0

    def test_vis_alias_shows_output_path(self) -> None:
        """vis alias output contains the output path."""
        mock_result = _make_exploration_result()
        with patch("mathlens.cli.tools.run_viz", return_value=mock_result):
            result = runner.invoke(app, ["vis", "pythagorean theorem"])
        assert result.exit_code == 0
        assert "out.mp4" in result.output

    def test_viz_with_format_flag(self) -> None:
        """viz command accepts --format diagram without error."""
        mock_result = _make_exploration_result()
        with patch("mathlens.cli.tools.run_viz", return_value=mock_result):
            result = runner.invoke(app, ["viz", "circles", "--format", "diagram"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TestSummarizeCommand
# ---------------------------------------------------------------------------


class TestSummarizeCommand:
    def test_summarize_runs(self) -> None:
        """summarize command exits with code 0 and prints phase 3 message."""
        result = runner.invoke(app, ["summarize", "/tmp/some-workspace"])
        assert result.exit_code == 0
        assert "Phase 3" in result.output

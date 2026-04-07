"""Shared pytest fixtures for MathLens test suite."""

import pytest
from pathlib import Path

from mathlens.models import (
    Difficulty,
    ExplorationPlan,
    Intent,
    OutputFormat,
    ScenePlan,
    VerificationResult,
    VerificationStatus,
)


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Creates a temporary explorations workspace directory."""
    workspace = tmp_path / "explorations"
    workspace.mkdir()
    return workspace


@pytest.fixture
def sample_plan() -> ExplorationPlan:
    """ExplorationPlan for the harmonic series divergence topic."""
    return ExplorationPlan(
        topic="Harmonic Series Divergence",
        slug="harmonic-series-divergence",
        intent=Intent.prove,
        theorem_statements=[
            "The harmonic series ∑(1/n) diverges",
        ],
        visualization_scenes=[
            ScenePlan(
                title="Partial Sums",
                description="Animate the partial sums of the harmonic series growing without bound",
                key_objects=["axes", "sum_tracker", "formula"],
                animation_hints=["step_through_terms", "highlight_divergence"],
            ),
        ],
        output_format=OutputFormat.video,
        difficulty=Difficulty.intermediate,
        prerequisites=["basic_series", "limits"],
        related_explorations=["geometric-series-convergence"],
    )


@pytest.fixture
def sample_verification_verified() -> VerificationResult:
    """VerificationResult with VERIFIED status."""
    return VerificationResult(
        status=VerificationStatus.verified,
        lean_output="Goals accomplished\nProof complete.",
        duration_seconds=4.2,
    )


@pytest.fixture
def sample_verification_refuted() -> VerificationResult:
    """VerificationResult with REFUTED status."""
    return VerificationResult(
        status=VerificationStatus.refuted,
        lean_output="Lean error: counterexample found",
        failure_reason="Counterexample at n=2 disproves the stated bound",
        duration_seconds=1.8,
    )

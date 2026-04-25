"""Unit tests for knowledge CLI commands: history, search, show."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mathlens.cli.app import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_exploration(ws_root: Path, slug: str, topic: str) -> Path:
    """Create a workspace directory with meta.json, summary.md, and plan.json."""
    ws_dir = ws_root / slug
    ws_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "topic": topic,
        "slug": slug,
        "mode": "explore",
        "status": "completed",
        "current_stage": "planning",
        "completed_stages": [],
        "created_at": "2026-04-08T00:00:00+00:00",
        "updated_at": "2026-04-08T00:00:00+00:00",
        "tags": [],
        "related": [],
    }
    (ws_dir / "meta.json").write_text(json.dumps(meta))
    (ws_dir / "summary.md").write_text(f"Summary for {topic}.")
    plan = {
        "topic": topic,
        "slug": slug,
        "intent": "explore",
        "theorem_statements": [f"The topic is {topic}"],
        "visualization_scenes": [],
        "output_format": "video",
        "difficulty": "intermediate",
    }
    (ws_dir / "plan.json").write_text(json.dumps(plan))

    return ws_dir


# ---------------------------------------------------------------------------
# history tests
# ---------------------------------------------------------------------------


def test_history_empty(tmp_path: Path) -> None:
    """history with no explorations shows a 'no explorations' message."""
    with patch("mathlens.cli.knowledge._get_workspace_root", return_value=tmp_path):
        result = runner.invoke(app, ["history"])
    assert result.exit_code == 0
    assert "no explorations" in result.output.lower()


def test_history_shows_explorations(tmp_path: Path) -> None:
    """history with one exploration shows its topic in the output."""
    _create_exploration(tmp_path, "2026-04-08_pythagorean-theorem", "Pythagorean Theorem")
    with patch("mathlens.cli.knowledge._get_workspace_root", return_value=tmp_path):
        result = runner.invoke(app, ["history"])
    assert result.exit_code == 0
    assert "Pythagorean Theorem" in result.output


def test_history_respects_limit(tmp_path: Path) -> None:
    """history --limit 1 shows only one row."""
    _create_exploration(tmp_path, "2026-04-08_topic-a", "Topic A")
    _create_exploration(tmp_path, "2026-04-08_topic-b", "Topic B")
    with patch("mathlens.cli.knowledge._get_workspace_root", return_value=tmp_path):
        result = runner.invoke(app, ["history", "--limit", "1"])
    assert result.exit_code == 0
    # Only one topic should appear (they differ in name)
    assert result.output.count("Topic A") + result.output.count("Topic B") == 1


# ---------------------------------------------------------------------------
# search tests
# ---------------------------------------------------------------------------


def test_search_finds_match(tmp_path: Path) -> None:
    """search returns a result when matching content exists."""
    ws_dir = _create_exploration(tmp_path, "2026-04-08_harmonic-series", "Harmonic Series")
    # Overwrite summary with harmonic-specific content
    (ws_dir / "summary.md").write_text(
        "The harmonic series diverges despite its terms approaching zero."
    )
    with patch("mathlens.cli.knowledge._get_workspace_root", return_value=tmp_path):
        result = runner.invoke(app, ["search", "harmonic"])
    assert result.exit_code == 0
    assert "Harmonic Series" in result.output


def test_search_no_results(tmp_path: Path) -> None:
    """search with no matching content shows a 'no results' message."""
    _create_exploration(tmp_path, "2026-04-08_circles", "Circles")
    with patch("mathlens.cli.knowledge._get_workspace_root", return_value=tmp_path):
        result = runner.invoke(app, ["search", "xyznonexistentterm"])
    assert result.exit_code == 0
    assert "no results" in result.output.lower()


# ---------------------------------------------------------------------------
# show tests
# ---------------------------------------------------------------------------


def test_show_displays_exploration(tmp_path: Path) -> None:
    """show by topic name displays the exploration details."""
    ws_dir = _create_exploration(tmp_path, "2026-04-08_euler-formula", "Euler Formula")
    (ws_dir / "summary.md").write_text("Euler's beautiful formula connects e, i, and pi.")
    with patch("mathlens.cli.knowledge._get_workspace_root", return_value=tmp_path):
        result = runner.invoke(app, ["show", "Euler Formula"])
    assert result.exit_code == 0
    assert "Euler Formula" in result.output
    assert "beautiful formula" in result.output


def test_show_not_found(tmp_path: Path) -> None:
    """show with an unknown topic exits with non-zero code or shows 'not found'."""
    with patch("mathlens.cli.knowledge._get_workspace_root", return_value=tmp_path):
        result = runner.invoke(app, ["show", "Nonexistent Topic XYZ"])
    assert result.exit_code != 0 or "not found" in result.output.lower()


def test_show_substring_match(tmp_path: Path) -> None:
    """show falls back to substring matching when exact topic is not found."""
    _create_exploration(tmp_path, "2026-04-08_calculus-intro", "Introduction to Calculus")
    with patch("mathlens.cli.knowledge._get_workspace_root", return_value=tmp_path):
        result = runner.invoke(app, ["show", "calculus"])
    assert result.exit_code == 0
    assert "Calculus" in result.output or "calculus" in result.output.lower()

"""Unit tests for SearchIndex."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mathlens.workspace.search import SearchIndex, SearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_index(tmp_db: Path) -> SearchIndex:
    return SearchIndex(tmp_db / "search.db")


def make_workspace(tmp_path: Path, slug: str) -> Path:
    ws = tmp_path / slug
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def write_meta(workspace_dir: Path, topic: str, slug: str) -> None:
    meta = {"topic": topic, "slug": slug, "mode": "explore"}
    (workspace_dir / "meta.json").write_text(json.dumps(meta))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)
    assert db_path.exists()
    index.close()


def test_index_exploration_and_search(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    ws = make_workspace(tmp_path, "2026-04-08_test")
    write_meta(ws, "Test Topic", "2026-04-08_test")
    (ws / "summary.md").write_text("This is a summary about quadratic equations")

    index.index_exploration("2026-04-08_test", ws)
    results = index.search("quadratic")

    assert len(results) == 1
    assert results[0].slug == "2026-04-08_test"
    assert results[0].topic == "Test Topic"
    assert "quadratic" in results[0].snippet.lower()

    index.close()


def test_search_no_results(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    ws = make_workspace(tmp_path, "2026-04-08_test")
    write_meta(ws, "Test Topic", "2026-04-08_test")
    (ws / "summary.md").write_text("This is about circles")

    index.index_exploration("2026-04-08_test", ws)
    results = index.search("nonexistent_term")

    assert len(results) == 0

    index.close()


def test_search_empty_query(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    ws = make_workspace(tmp_path, "2026-04-08_test")
    write_meta(ws, "Test Topic", "2026-04-08_test")
    (ws / "summary.md").write_text("This is about circles")

    index.index_exploration("2026-04-08_test", ws)
    results = index.search("")

    assert len(results) == 0

    index.close()


def test_reindex_updates(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    ws = make_workspace(tmp_path, "2026-04-08_test")
    write_meta(ws, "Test Topic", "2026-04-08_test")
    (ws / "summary.md").write_text("This is about calculus")

    index.index_exploration("2026-04-08_test", ws)
    results = index.search("calculus")
    assert len(results) == 1

    # Update with new content
    (ws / "summary.md").write_text("This is about geometry now")
    index.index_exploration("2026-04-08_test", ws)

    # Old term should not find it
    results = index.search("calculus")
    assert len(results) == 0

    # New term should find it
    results = index.search("geometry")
    assert len(results) == 1
    assert results[0].slug == "2026-04-08_test"

    index.close()


def test_remove_exploration(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    ws = make_workspace(tmp_path, "2026-04-08_test")
    write_meta(ws, "Test Topic", "2026-04-08_test")
    (ws / "summary.md").write_text("This is about topology")

    index.index_exploration("2026-04-08_test", ws)
    results = index.search("topology")
    assert len(results) == 1

    index.remove_exploration("2026-04-08_test")
    results = index.search("topology")
    assert len(results) == 0

    index.close()


def test_index_from_plan_json(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    ws = make_workspace(tmp_path, "2026-04-08_plan_test")
    write_meta(ws, "Plan Topic", "2026-04-08_plan_test")
    plan = {
        "topic": "Plan Topic",
        "slug": "2026-04-08_plan_test",
        "theorem_statements": ["The sum of angles in a triangle equals 180 degrees"],
        "intent": "prove",
    }
    (ws / "plan.json").write_text(json.dumps(plan))

    index.index_exploration("2026-04-08_plan_test", ws)
    results = index.search("triangle")

    assert len(results) == 1
    assert "triangle" in results[0].snippet.lower()

    index.close()


def test_index_from_proof_lean(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    ws = make_workspace(tmp_path, "2026-04-08_proof_test")
    write_meta(ws, "Proof Topic", "2026-04-08_proof_test")
    (ws / "proof.lean").write_text("theorem pythagorean : a^2 + b^2 = c^2 := by sorry")

    index.index_exploration("2026-04-08_proof_test", ws)
    results = index.search("pythagorean")

    assert len(results) == 1
    assert "pythagorean" in results[0].snippet.lower()

    index.close()


def test_index_multiple_explorations(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    for i in range(3):
        slug = f"2026-04-08_test_{i}"
        ws = make_workspace(tmp_path, slug)
        write_meta(ws, f"Topic {i}", slug)
        (ws / "summary.md").write_text(f"This is about calculus topic {i}")
        index.index_exploration(slug, ws)

    results = index.search("calculus")
    assert len(results) == 3

    index.close()


def test_search_with_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    for i in range(5):
        slug = f"2026-04-08_test_{i}"
        ws = make_workspace(tmp_path, slug)
        write_meta(ws, f"Topic {i}", slug)
        (ws / "summary.md").write_text("All about algebra")
        index.index_exploration(slug, ws)

    results = index.search("algebra", limit=2)
    assert len(results) == 2

    index.close()


def test_missing_meta_uses_slug_as_topic(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    slug = "2026-04-08_no_meta"
    ws = make_workspace(tmp_path, slug)
    (ws / "summary.md").write_text("About integration")

    index.index_exploration(slug, ws)
    results = index.search("integration")

    assert len(results) == 1
    assert results[0].topic == slug

    index.close()


def test_corrupted_meta_json_uses_slug_as_topic(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    slug = "2026-04-08_bad_json"
    ws = make_workspace(tmp_path, slug)
    (ws / "meta.json").write_text("{invalid json")
    (ws / "summary.md").write_text("About derivatives")

    index.index_exploration(slug, ws)
    results = index.search("derivatives")

    assert len(results) == 1
    assert results[0].topic == slug

    index.close()


def test_corrupted_plan_json_skipped(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    slug = "2026-04-08_bad_plan"
    ws = make_workspace(tmp_path, slug)
    write_meta(ws, "Test Topic", slug)
    (ws / "plan.json").write_text("{bad json")
    (ws / "summary.md").write_text("About limits")

    index.index_exploration(slug, ws)
    results = index.search("limits")

    assert len(results) == 1

    index.close()


def test_search_result_properties(tmp_path: Path) -> None:
    db_path = tmp_path / "search.db"
    index = SearchIndex(db_path)

    slug = "2026-04-08_test"
    ws = make_workspace(tmp_path, slug)
    write_meta(ws, "My Topic", slug)
    (ws / "summary.md").write_text("This content has the word matrices in it")

    index.index_exploration(slug, ws)
    results = index.search("matrices")

    assert len(results) == 1
    result = results[0]
    assert isinstance(result, SearchResult)
    assert result.slug == slug
    assert result.topic == "My Topic"
    assert isinstance(result.snippet, str)
    assert isinstance(result.rank, float)

    index.close()

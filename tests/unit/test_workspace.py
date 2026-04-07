"""Unit tests for WorkspaceStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from mathlens.models import (
    ExplorationPlan,
    PipelineMode,
    PipelineStage,
    StageStatus,
    VerificationResult,
    VerificationStatus,
)
from mathlens.workspace.store import WorkspaceStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_store(tmp_workspace: Path) -> WorkspaceStore:
    return WorkspaceStore(tmp_workspace)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_exploration(tmp_workspace: Path, sample_plan: ExplorationPlan) -> None:
    store = make_store(tmp_workspace)
    meta = store.create(sample_plan, PipelineMode.explore)

    ws = store.path_for(sample_plan.slug)
    assert ws.is_dir()
    assert (ws / "meta.json").exists()
    assert meta.topic == sample_plan.topic
    assert meta.status == StageStatus.pending


def test_create_writes_plan(tmp_workspace: Path, sample_plan: ExplorationPlan) -> None:
    store = make_store(tmp_workspace)
    store.create(sample_plan, PipelineMode.explore)

    plan_path = store.path_for(sample_plan.slug) / "plan.json"
    assert plan_path.exists()

    loaded = ExplorationPlan.model_validate_json(plan_path.read_text())
    assert loaded.topic == sample_plan.topic


def test_save_artifact_atomically(
    tmp_workspace: Path, sample_plan: ExplorationPlan
) -> None:
    store = make_store(tmp_workspace)
    store.create(sample_plan, PipelineMode.explore)

    content = b"hello artifact"
    dest = store.save_artifact(sample_plan.slug, "output.mp4", content)

    assert dest.exists()
    assert dest.read_bytes() == content


def test_save_stage_result(tmp_workspace: Path, sample_plan: ExplorationPlan) -> None:
    store = make_store(tmp_workspace)
    store.create(sample_plan, PipelineMode.explore)

    result = VerificationResult(
        status=VerificationStatus.verified,
        lean_output="Goals accomplished",
        duration_seconds=1.0,
    )
    path = store.save_stage_result(sample_plan.slug, PipelineStage.verification, result)

    assert path.name == "verification_result.json"
    assert path.exists()

    loaded = VerificationResult.model_validate_json(path.read_text())
    assert loaded.status == VerificationStatus.verified


def test_update_meta_stage(tmp_workspace: Path, sample_plan: ExplorationPlan) -> None:
    store = make_store(tmp_workspace)
    store.create(sample_plan, PipelineMode.explore)

    meta = store.complete_stage(sample_plan.slug, PipelineStage.planning)

    reloaded = store.load_meta(sample_plan.slug)
    assert PipelineStage.planning in reloaded.completed_stages
    assert reloaded.status == StageStatus.running
    assert meta.slug == sample_plan.slug


def test_list_explorations(tmp_workspace: Path, sample_plan: ExplorationPlan) -> None:
    store = make_store(tmp_workspace)
    store.create(sample_plan, PipelineMode.explore)

    explorations = store.list_explorations()
    assert len(explorations) == 1
    assert explorations[0].slug == sample_plan.slug


def test_find_by_topic(tmp_workspace: Path, sample_plan: ExplorationPlan) -> None:
    store = make_store(tmp_workspace)
    store.create(sample_plan, PipelineMode.explore)

    found = store.find_by_topic(sample_plan.topic)
    assert found is not None
    assert found.slug == sample_plan.slug


def test_find_by_topic_not_found(
    tmp_workspace: Path, sample_plan: ExplorationPlan
) -> None:
    store = make_store(tmp_workspace)
    store.create(sample_plan, PipelineMode.explore)

    assert store.find_by_topic("Nonexistent Topic") is None


def test_resumable_detection(tmp_workspace: Path, sample_plan: ExplorationPlan) -> None:
    store = make_store(tmp_workspace)
    store.create(sample_plan, PipelineMode.explore)

    meta = store.set_status(sample_plan.slug, StageStatus.failed)
    assert meta.is_resumable

    reloaded = store.load_meta(sample_plan.slug)
    assert reloaded.is_resumable


def test_atomic_write_cleans_stale_tmp(
    tmp_workspace: Path, sample_plan: ExplorationPlan
) -> None:
    store = make_store(tmp_workspace)
    store.create(sample_plan, PipelineMode.explore)

    # Write an initial artifact.
    store.save_artifact(sample_plan.slug, "output.mp4", b"first write")

    # Simulate a stale .tmp left by a previous crash.
    ws = store.path_for(sample_plan.slug)
    stale_tmp = ws / "output.mp4.tmp"
    stale_tmp.write_bytes(b"stale data")
    assert stale_tmp.exists()

    # Second write should clean the stale .tmp and succeed.
    dest = store.save_artifact(sample_plan.slug, "output.mp4", b"second write")

    assert not stale_tmp.exists()
    assert dest.read_bytes() == b"second write"

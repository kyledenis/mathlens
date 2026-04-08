"""Unit tests for workspace repair functionality."""
from __future__ import annotations

from pathlib import Path

import pytest

from mathlens.workspace.repair import WorkspaceIssue, WorkspaceRepair


class TestWorkspaceRepair:
    def test_detect_stale_tmp(self, tmp_workspace: Path) -> None:
        """Detects stale .tmp files in workspace subdirectories."""
        # Setup: create a subdirectory with meta.json and a .tmp file
        sub = tmp_workspace / "test-exploration"
        sub.mkdir()
        (sub / "meta.json").write_text("{}")
        (sub / "data.tmp").write_text("stale")

        repair = WorkspaceRepair(tmp_workspace)
        issues = repair.diagnose()

        assert len(issues) == 1
        assert issues[0].slug == "test-exploration"
        assert "Stale tmp file" in issues[0].description
        assert "data.tmp" in issues[0].description
        assert issues[0].fixable is True

    def test_fix_stale_tmp(self, tmp_workspace: Path) -> None:
        """Removes stale .tmp files from workspace."""
        sub = tmp_workspace / "test-exploration"
        sub.mkdir()
        (sub / "meta.json").write_text("{}")
        tmp_file = sub / "data.tmp"
        tmp_file.write_text("stale")

        repair = WorkspaceRepair(tmp_workspace)
        actions = repair.fix()

        assert len(actions) == 1
        assert "Removed stale tmp" in actions[0]
        assert "test-exploration/data.tmp" in actions[0]
        assert not tmp_file.exists()

    def test_detect_missing_meta(self, tmp_workspace: Path) -> None:
        """Detects subdirectories missing meta.json."""
        sub = tmp_workspace / "test-exploration"
        sub.mkdir()
        # Deliberately do NOT create meta.json

        repair = WorkspaceRepair(tmp_workspace)
        issues = repair.diagnose()

        assert len(issues) == 1
        assert issues[0].slug == "test-exploration"
        assert "Missing meta.json" in issues[0].description
        assert issues[0].fixable is False

    def test_detect_no_issues(self, tmp_workspace: Path) -> None:
        """Returns empty list when workspace is healthy."""
        sub = tmp_workspace / "test-exploration"
        sub.mkdir()
        (sub / "meta.json").write_text("{}")

        repair = WorkspaceRepair(tmp_workspace)
        issues = repair.diagnose()

        assert len(issues) == 0

    def test_detect_stale_lock(self, tmp_workspace: Path) -> None:
        """Detects stale lock files with dead PIDs."""
        sub = tmp_workspace / "test-exploration"
        sub.mkdir()
        (sub / "meta.json").write_text("{}")
        # Use a PID that almost certainly doesn't exist
        (sub / ".lock").write_text("99999999")

        repair = WorkspaceRepair(tmp_workspace)
        issues = repair.diagnose()

        assert len(issues) == 1
        assert issues[0].slug == "test-exploration"
        assert "Stale lock file" in issues[0].description
        assert "99999999" in issues[0].description
        assert issues[0].fixable is True

    def test_fix_stale_lock(self, tmp_workspace: Path) -> None:
        """Removes stale lock files with dead PIDs."""
        sub = tmp_workspace / "test-exploration"
        sub.mkdir()
        (sub / "meta.json").write_text("{}")
        lock_file = sub / ".lock"
        # Use a PID that almost certainly doesn't exist
        lock_file.write_text("99999999")

        repair = WorkspaceRepair(tmp_workspace)
        actions = repair.fix()

        assert len(actions) == 1
        assert "Removed stale lock" in actions[0]
        assert "test-exploration/.lock" in actions[0]
        assert "99999999" in actions[0]
        assert not lock_file.exists()

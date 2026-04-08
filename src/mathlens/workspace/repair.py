"""Workspace health checks and self-healing."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceIssue:
    slug: str
    description: str
    fixable: bool


class WorkspaceRepair:
    def __init__(self, root: Path) -> None:
        self._root = root

    def diagnose(self) -> list[WorkspaceIssue]:
        issues: list[WorkspaceIssue] = []
        if not self._root.exists():
            return issues
        for child in self._root.iterdir():
            if not child.is_dir():
                continue
            slug = child.name
            if not (child / "meta.json").exists():
                issues.append(
                    WorkspaceIssue(
                        slug=slug,
                        description=f"Missing meta.json in {slug}",
                        fixable=False,
                    )
                )
                continue
            for tmp in child.glob("*.tmp"):
                issues.append(
                    WorkspaceIssue(
                        slug=slug,
                        description=f"Stale tmp file: {tmp.name}",
                        fixable=True,
                    )
                )
            lock = child / ".lock"
            if lock.exists():
                pid_str = lock.read_text().strip()
                if not self._pid_alive(pid_str):
                    issues.append(
                        WorkspaceIssue(
                            slug=slug,
                            description=f"Stale lock file (dead PID {pid_str})",
                            fixable=True,
                        )
                    )
        return issues

    def fix(self) -> list[str]:
        actions: list[str] = []
        if not self._root.exists():
            return actions
        for child in self._root.iterdir():
            if not child.is_dir():
                continue
            for tmp in child.glob("*.tmp"):
                tmp.unlink()
                actions.append(f"Removed stale tmp: {child.name}/{tmp.name}")
            lock = child / ".lock"
            if lock.exists():
                pid_str = lock.read_text().strip()
                if not self._pid_alive(pid_str):
                    lock.unlink()
                    actions.append(
                        f"Removed stale lock: {child.name}/.lock (PID {pid_str})"
                    )
        return actions

    @staticmethod
    def _pid_alive(pid_str: str) -> bool:
        try:
            os.kill(int(pid_str), 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            return False

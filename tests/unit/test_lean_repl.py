"""Tests for the LeanREPL."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mathlens.workspace.lean_project import LeanREPL


class TestLeanREPL:
    @pytest.mark.asyncio
    async def test_not_running_initially(self):
        repl = LeanREPL(project_dir=Path("/fake"))
        assert not repl.is_running

    @pytest.mark.asyncio
    async def test_check_delegates_to_oneshot(self):
        repl = LeanREPL(project_dir=Path("/fake"))
        with patch.object(repl, "_run_oneshot", new=AsyncMock(return_value=(0, "ok", ""))):
            rc, out, err = await repl.check("theorem foo : True := trivial", timeout=10)
        assert rc == 0
        assert out == "ok"

    @pytest.mark.asyncio
    async def test_stop_is_safe_when_not_running(self):
        repl = LeanREPL(project_dir=Path("/fake"))
        await repl.stop()  # should not raise

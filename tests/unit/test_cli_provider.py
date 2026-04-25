"""Unit tests for CLISubprocessProvider."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mathlens.providers.cli_sub import CLISubprocessProvider


class TestCLISubprocessProviderInit:
    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            CLISubprocessProvider(backend="gpt-unknown")


class TestCLISubprocessProviderComplete:
    def _make_mock_process(self, stdout: bytes, stderr: bytes, returncode: int):
        process = MagicMock()
        process.returncode = returncode
        process.communicate = AsyncMock(return_value=(stdout, stderr))
        process.kill = MagicMock()
        return process

    @pytest.mark.asyncio
    async def test_complete_success(self):
        mock_process = self._make_mock_process(
            stdout=b"result", stderr=b"", returncode=0
        )
        with patch(
            "asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)
        ):
            provider = CLISubprocessProvider(backend="claude-code")
            response = await provider.complete("solve x+1=2")

        assert response.content == "result"
        assert response.model == "claude-code"

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self):
        mock_process = self._make_mock_process(
            stdout=b"answer", stderr=b"", returncode=0
        )
        captured_cmd: list[str] = []

        async def fake_exec(*args, **kwargs):
            captured_cmd.extend(args)
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            provider = CLISubprocessProvider(backend="claude-code")
            await provider.complete("user prompt", system="be precise")

        # The last positional arg to create_subprocess_exec is the full_prompt
        full_prompt_arg = captured_cmd[-1]
        assert "be precise" in full_prompt_arg
        assert "user prompt" in full_prompt_arg
        # System text must come before user prompt
        assert full_prompt_arg.index("be precise") < full_prompt_arg.index("user prompt")

    @pytest.mark.asyncio
    async def test_complete_timeout(self):
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345

        with patch(
            "asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)
        ):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                provider = CLISubprocessProvider(backend="claude-code", timeout=1)
                with pytest.raises(TimeoutError):
                    await provider.complete("slow prompt")

    @pytest.mark.asyncio
    async def test_complete_nonzero_exit(self):
        mock_process = self._make_mock_process(
            stdout=b"", stderr=b"Error: rate limited", returncode=1
        )
        with patch(
            "asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)
        ):
            provider = CLISubprocessProvider(backend="claude-code")
            with pytest.raises(RuntimeError, match="rate limited"):
                await provider.complete("some prompt")


class TestCLISubprocessProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check(self):
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            provider = CLISubprocessProvider(backend="claude-code")
            assert await provider.health_check() is True

        with patch("shutil.which", return_value=None):
            provider = CLISubprocessProvider(backend="claude-code")
            assert await provider.health_check() is False

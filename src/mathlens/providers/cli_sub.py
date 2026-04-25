"""CLI subprocess provider for claude-code and codex backends."""

from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Optional

from mathlens.lifecycle import register_process, unregister_process
from mathlens.providers.base import (
    LLMResponse,
    ProviderCapabilities,
    Tier,
)

logger = logging.getLogger(__name__)

BACKEND_COMMANDS: dict[str, list[str]] = {
    "claude-code": ["claude", "-p"],
    "codex": ["codex", "-q"],
}

BACKEND_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "claude-code": ProviderCapabilities(
        max_context=200_000,
        supports_json_mode=True,
        supports_streaming=False,
        formalization_quality=Tier.HIGH,
        scene_planning_quality=Tier.HIGH,
        summarization_quality=Tier.HIGH,
    ),
    "codex": ProviderCapabilities(
        max_context=200_000,
        supports_json_mode=True,
        supports_streaming=False,
        formalization_quality=Tier.HIGH,
        scene_planning_quality=Tier.HIGH,
        summarization_quality=Tier.HIGH,
    ),
}

# Default model for mathlens CLI calls — fast and cost-effective.
# This is passed via --model so it doesn't change the user's
# Claude Code default model.
DEFAULT_CLI_MODEL = "sonnet"

# Maximum spend per CLI call in USD — safety cap to prevent runaway usage.
DEFAULT_MAX_BUDGET_USD = 0.50


class CLISubprocessProvider:
    """LLM provider that delegates to a local CLI tool via subprocess.

    Passes --model and --max-budget-usd to claude -p so that:
    1. mathlens always uses a specific model (not the user's default)
    2. Each call has a cost ceiling to prevent runaway token usage
    """

    def __init__(
        self,
        backend: str = "claude-code",
        timeout: int = 300,
        model: str = DEFAULT_CLI_MODEL,
        max_budget_usd: float = DEFAULT_MAX_BUDGET_USD,
    ) -> None:
        if backend not in BACKEND_COMMANDS:
            raise ValueError(
                f"Unknown backend {backend!r}. "
                f"Valid backends: {list(BACKEND_COMMANDS)}"
            )
        self._backend = backend
        self._timeout = timeout
        self._model = model
        self._max_budget_usd = max_budget_usd
        self._cmd_prefix = BACKEND_COMMANDS[backend]

    @property
    def name(self) -> str:
        return f"cli:{self._backend}"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return BACKEND_CAPABILITIES[self._backend]

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: str = "text",
    ) -> LLMResponse:
        full_prompt = prompt
        if system is not None:
            full_prompt = f"{system}\n\n{prompt}"
        if response_format == "json":
            full_prompt = f"{full_prompt}\n\nRespond with valid JSON only."

        cmd = list(self._cmd_prefix)
        # Session-specific flags — don't touch the user's Claude Code config
        if self._backend == "claude-code":
            cmd += ["--model", self._model]
            cmd += ["--max-budget-usd", str(self._max_budget_usd)]
        cmd.append(full_prompt)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        register_process(process)

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            unregister_process(process)
            raise TimeoutError(
                f"CLI backend {self._backend!r} timed out after {self._timeout}s"
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            process.kill()
            await process.wait()
            unregister_process(process)
            raise
        else:
            unregister_process(process)

        if process.returncode != 0:
            error_text = stderr.decode() if stderr else ""
            raise RuntimeError(
                f"CLI backend {self._backend!r} exited with code "
                f"{process.returncode}: {error_text}"
            )

        return LLMResponse(content=stdout.decode().strip(), model=self._model)

    async def health_check(self) -> bool:
        binary = self._cmd_prefix[0]
        return shutil.which(binary) is not None

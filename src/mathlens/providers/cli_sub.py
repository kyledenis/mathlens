"""CLI subprocess provider for claude-code and codex backends."""

from __future__ import annotations

import asyncio
import shutil
from typing import Optional

from mathlens.providers.base import (
    LLMResponse,
    ProviderCapabilities,
    Tier,
)

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


class CLISubprocessProvider:
    """LLM provider that delegates to a local CLI tool via subprocess."""

    def __init__(self, backend: str = "claude-code", timeout: int = 120) -> None:
        if backend not in BACKEND_COMMANDS:
            raise ValueError(
                f"Unknown backend {backend!r}. "
                f"Valid backends: {list(BACKEND_COMMANDS)}"
            )
        self._backend = backend
        self._timeout = timeout
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

        cmd = [*self._cmd_prefix, full_prompt]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            raise TimeoutError(
                f"CLI backend {self._backend!r} timed out after {self._timeout}s"
            )

        if process.returncode != 0:
            error_text = stderr.decode() if stderr else ""
            raise RuntimeError(
                f"CLI backend {self._backend!r} exited with code "
                f"{process.returncode}: {error_text}"
            )

        return LLMResponse(content=stdout.decode().strip(), model=self._backend)

    async def health_check(self) -> bool:
        binary = self._cmd_prefix[0]
        return shutil.which(binary) is not None

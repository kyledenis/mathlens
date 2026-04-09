"""Visualizer pipeline stage for MathLens."""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Optional

from mathlens.lifecycle import register_process, unregister_process
from mathlens.models import (
    Badge,
    OutputFormat,
    PipelineMode,
    RenderQuality,
    RenderedScene,
    ScenePlan,
    VerificationStatus,
    VisualizationResult,
)
from mathlens.providers.base import LLMProvider


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCENE_GEN_SYSTEM = """\
You are a Manim Community Edition expert. Given a list of scene descriptions for a
mathematical topic, generate a single Python file containing one or more Manim Scene
subclasses that animate the described content.

Requirements:
- Use only Manim CE (Community Edition) APIs.
- Each scene class must subclass Scene and implement construct(self).
- Include `from manim import *` at the top of the file.
- Produce clean, runnable code with no placeholder comments.
- Do not include any explanation or markdown fences — output Python code only.\
"""

QUALITY_MAP: dict[PipelineMode, RenderQuality] = {
    PipelineMode.explore: RenderQuality.medium,
    PipelineMode.deep: RenderQuality.production,
}

MANIM_QUALITY_FLAGS: dict[RenderQuality, str] = {
    RenderQuality.low: "-ql",
    RenderQuality.medium: "-qm",
    RenderQuality.high: "-qh",
    RenderQuality.production: "-qh",
}

RENDER_TIMEOUTS: dict[PipelineMode, int] = {
    PipelineMode.explore: 600,   # 10 min — catches hung manim, not normal renders
    PipelineMode.deep: 1800,     # 30 min — production 4K renders can be slow
}


# ---------------------------------------------------------------------------
# Visualizer class
# ---------------------------------------------------------------------------


class Visualizer:
    """LLM-backed visualization stage that generates and renders Manim scenes."""

    def __init__(self, provider: LLMProvider, workspace_dir: Path) -> None:
        self._provider = provider
        self._workspace_dir = workspace_dir

    # ------------------------------------------------------------------
    # Quality helpers
    # ------------------------------------------------------------------

    def _quality_for(self, mode: PipelineMode) -> RenderQuality:
        """Return the appropriate RenderQuality for the given pipeline mode."""
        return QUALITY_MAP[mode]

    def _manim_quality_flag(self, quality: RenderQuality) -> str:
        """Return the manim CLI quality flag for the given RenderQuality."""
        return MANIM_QUALITY_FLAGS[quality]

    # ------------------------------------------------------------------
    # Scene generation
    # ------------------------------------------------------------------

    async def generate_scene_code(
        self, scenes: list[ScenePlan], topic: str
    ) -> str:
        """Generate Manim scene source code from a list of ScenePlans.

        The generated code is saved to workspace_dir/scene_01.py and returned.
        """
        scene_descriptions = "\n\n".join(
            f"Scene {i + 1}: {scene.title}\n"
            f"Description: {scene.description}\n"
            f"Key objects: {', '.join(scene.key_objects)}\n"
            f"Animation hints: {', '.join(scene.animation_hints)}"
            for i, scene in enumerate(scenes)
        )
        prompt = (
            f"Generate Manim CE Python code for the following scenes about '{topic}':\n\n"
            f"{scene_descriptions}"
        )
        response = await self._provider.complete(
            prompt,
            system=SCENE_GEN_SYSTEM,
            temperature=0.2,
        )
        code = self._extract_code(response.content)

        scene_path = self._workspace_dir / "scene_01.py"
        scene_path.write_text(code)

        return code

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    async def render(
        self,
        scene_path: Path,
        output_path: Path,
        mode: PipelineMode,
        verification_status: VerificationStatus,
        output_format: OutputFormat = OutputFormat.video,
    ) -> VisualizationResult:
        """Render the Manim scene at scene_path.

        If rendering fails, a simplified scene is generated and retried once.
        Returns a VisualizationResult with a Badge derived from verification_status.
        """
        start = time.monotonic()
        quality = self._quality_for(mode)
        timeout = RENDER_TIMEOUTS[mode]

        returncode, stdout, stderr = await self._run_manim(
            scene_path, quality, timeout
        )

        if returncode != 0:
            # Fallback: generate a simplified scene and retry
            simplified_path = await self._generate_simplified_scene(scene_path)
            simplified = Path(simplified_path)
            returncode, stdout, stderr = await self._run_manim(
                simplified, quality, timeout
            )
            scene_path = simplified

        duration = time.monotonic() - start
        badge = Badge.from_status(verification_status)

        rendered_scene = RenderedScene(
            title=scene_path.stem,
            source_path=scene_path,
            output_path=output_path,
            duration_seconds=duration,
        )

        return VisualizationResult(
            scenes=[rendered_scene],
            output_path=output_path,
            output_format=output_format,
            source_paths=[scene_path],
            render_quality=quality,
            duration_seconds=duration,
            verification_badge=badge,
        )

    # ------------------------------------------------------------------
    # Subprocess helper
    # ------------------------------------------------------------------

    async def _run_manim(
        self, scene_path: Path, quality: RenderQuality, timeout: int
    ) -> tuple[int, str, str]:
        """Run manim render as a subprocess and return (returncode, stdout, stderr)."""
        quality_flag = self._manim_quality_flag(quality)
        cmd = ["manim", "render", quality_flag, str(scene_path)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        register_process(proc)
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            unregister_process(proc)
            return 1, "", f"Manim render timed out after {timeout}s"
        except (asyncio.CancelledError, KeyboardInterrupt):
            proc.kill()
            await proc.wait()
            unregister_process(proc)
            raise
        else:
            unregister_process(proc)

        return (
            proc.returncode or 0,
            stdout_bytes.decode(),
            stderr_bytes.decode(),
        )

    # ------------------------------------------------------------------
    # Simplified scene fallback
    # ------------------------------------------------------------------

    async def _generate_simplified_scene(self, original_path: Path) -> str:
        """Ask the LLM to produce a simpler version of the scene at original_path.

        Saves to workspace_dir/scene_simplified.py and returns the path as a string.
        """
        original_code = original_path.read_text()
        prompt = (
            "The following Manim CE scene failed to render. "
            "Produce a simplified version that uses only basic Manim primitives "
            "(Text, MathTex, Dot, Line, Arrow) and minimal animations. "
            "Output only valid Python code, no markdown fences.\n\n"
            f"{original_code}"
        )
        response = await self._provider.complete(
            prompt,
            system=SCENE_GEN_SYSTEM,
            temperature=0.1,
        )
        code = self._extract_code(response.content)
        simplified_path = self._workspace_dir / "scene_simplified.py"
        simplified_path.write_text(code)
        return str(simplified_path)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _extract_code(self, content: str) -> str:
        """Strip markdown code fences from LLM output, if present."""
        stripped = content.strip()
        stripped = re.sub(r"^```(?:python)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
        return stripped.strip()

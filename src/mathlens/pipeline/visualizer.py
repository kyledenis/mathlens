"""Visualizer pipeline stage for MathLens."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from mathlens.lifecycle import register_process, unregister_process
from mathlens.pipeline.response_cleaner import clean_code_response
from mathlens.pipeline.validation import validate_python
from mathlens.workspace.atomic import atomic_write_text
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
Write Manim CE Python code. Output ONLY valid Python — nothing else.
Start with `from manim import *`. One Scene subclass.

You will be given a numbered shot list. Implement each step as one \
self.play() call (or small group). Do NOT add extra animations beyond \
the shot list — it defines the exact scope of the video.

For each step, add a caption (Text, font_size=24, .to_edge(DOWN)) \
that explains what the viewer is seeing and why it matters.

Quality rules:
- One caption at a time — FadeOut the previous before showing the next
- FadeOut all objects between major sections to prevent clutter
- Label all axes with Text(font_size=18)
- Labels on shapes: font_size=20, buff=0.3
- self.wait(1) between steps, self.wait(2) after key moments
- Use colour with meaning: BLUE primary, YELLOW highlights, RED results\
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
    PipelineMode.explore: 45,    # 45s — simple scenes render fast
    PipelineMode.deep: 300,      # 5 min — production renders can be slow
}


# ---------------------------------------------------------------------------
# Visualizer class
# ---------------------------------------------------------------------------


class Visualizer:
    """LLM-backed visualization stage that generates and renders Manim scenes."""

    def __init__(self, provider: LLMProvider, workspace_dir: Path) -> None:
        self._provider = provider
        self._workspace_dir = workspace_dir
        self._last_reasoning: str = ""

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
        self,
        scenes: list[ScenePlan],
        topic: str,
        workspace_dir: Optional[Path] = None,
    ) -> str:
        """Generate Manim scene source code from a list of ScenePlans.

        The generated code is saved to workspace_dir/scene_01.py and returned.
        """
        target_dir = workspace_dir or self._workspace_dir
        self._last_reasoning = ""

        # Build prompt from the scene plan's shot list
        scene = scenes[0] if scenes else ScenePlan(
            title="Overview", description=f"Visual overview of {topic}",
        )

        if scene.steps:
            step_list = "\n".join(f"{i+1}. {s}" for i, s in enumerate(scene.steps))
            prompt = (
                f"Topic: {topic}\n\n"
                f"Implement this shot list as Manim code — one animation per step:\n"
                f"{step_list}"
            )
        else:
            # Fallback for plans without steps (backward compat)
            prompt = (
                f"Write a Manim scene about: {topic}\n"
                f"Focus: {scene.title} — {scene.description}"
            )
        code = await self._generate_single_scene(prompt)

        scene_path = target_dir / "scene_01.py"
        atomic_write_text(scene_path, code)

        return code

    async def _generate_single_scene(self, prompt: str) -> str:
        """Generate code for a single scene with validation and one retry."""
        response = await self._provider.complete(
            prompt,
            system=SCENE_GEN_SYSTEM,
            temperature=0.2,
            max_tokens=2048,
        )
        cleaned = clean_code_response(response.content, "python")
        code = cleaned.code
        if cleaned.reasoning:
            self._last_reasoning += cleaned.reasoning

        valid, error = validate_python(code)
        if not valid:
            retry_prompt = (
                f"Your response was not valid Python. Error: {error}\n"
                f"Output ONLY valid Python code.\n\n{prompt}"
            )
            response = await self._provider.complete(
                retry_prompt,
                system=SCENE_GEN_SYSTEM,
                temperature=0.1,
                max_tokens=2048,
            )
            cleaned = clean_code_response(response.content, "python")
            code = cleaned.code

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
            scene_path, quality, timeout, output_dir=output_path,
        )

        if returncode != 0 and mode == PipelineMode.deep:
            # Fallback: generate a simplified scene and retry (deep mode only)
            simplified_path = await self._generate_simplified_scene(scene_path)
            simplified = Path(simplified_path)
            returncode, stdout, stderr = await self._run_manim(
                simplified, quality, timeout, output_dir=output_path,
            )
            scene_path = simplified

        duration = time.monotonic() - start
        badge = Badge.from_status(verification_status)

        # Validate that Manim actually produced output files
        if output_path.is_dir():
            output_files = (
                list(output_path.glob("**/*.mp4"))
                + list(output_path.glob("**/*.gif"))
                + list(output_path.glob("**/*.png"))
            )
            if not output_files:
                logger.warning(
                    "Manim returned %d but produced no output files in %s",
                    returncode, output_path,
                )

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
        self, scene_path: Path, quality: RenderQuality, timeout: int,
        output_dir: Path | None = None,
    ) -> tuple[int, str, str]:
        """Run manim render as a subprocess and return (returncode, stdout, stderr)."""
        quality_flag = self._manim_quality_flag(quality)
        cmd = ["manim", "render", quality_flag]
        if output_dir is not None:
            cmd += ["--media_dir", str(output_dir)]
        cmd.append(str(scene_path))
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
        cleaned = clean_code_response(response.content, "python")
        simplified_path = original_path.parent / "scene_simplified.py"
        atomic_write_text(simplified_path, cleaned.code)
        return str(simplified_path)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _extract_code(self, content: str) -> str:
        """Extract clean Python code from LLM output."""
        return clean_code_response(content, "python").code

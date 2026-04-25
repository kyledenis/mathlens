"""Pipeline orchestrator for MathLens — coordinates all pipeline stages."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Optional

logger = logging.getLogger(__name__)

from mathlens.models import (
    Badge,
    ExplorationMeta,
    ExplorationPlan,
    OutputFormat,
    PipelineMode,
    PipelineStage,
    StageStatus,
    Summary,
    VerificationResult,
    VerificationStatus,
    VisualizationResult,
)
from mathlens.pipeline.planner import Planner
from mathlens.pipeline.summarizer import Summarizer
from mathlens.pipeline.verifier import Verifier
from mathlens.pipeline.visualizer import Visualizer
from mathlens.workspace.search import SearchIndex
from mathlens.workspace.store import WorkspaceStore


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExplorationResult:
    """Full result of a single pipeline run."""

    plan: ExplorationPlan
    verification: VerificationResult
    visualization: Optional[VisualizationResult]
    summary: Optional[Summary]
    meta: ExplorationMeta
    duration_seconds: float


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Orchestrator:
    """Coordinates the MathLens verify-then-visualize pipeline."""

    def __init__(
        self,
        planner: Planner,
        verifier: Verifier,
        visualizer: Visualizer,
        summarizer: Summarizer,
        store: WorkspaceStore,
        search_index: Optional[SearchIndex] = None,
    ) -> None:
        self._planner = planner
        self._verifier = verifier
        self._visualizer = visualizer
        self._summarizer = summarizer
        self._store = store
        self._search_index = search_index

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(
        self,
        query: str,
        mode: PipelineMode,
        output_format: Optional[OutputFormat] = None,
        skip_verification: bool = False,
        on_stage: Callable[[PipelineStage, str], None] | None = None,
    ) -> ExplorationResult:
        """Run the full pipeline for *query* and return an ExplorationResult.

        *on_stage* is called with ``(stage, event)`` where *event* is
        ``"start"`` or ``"done"``.  The CLI uses this to drive a spinner.
        """

        def _emit(stage: PipelineStage, event: str) -> None:
            if on_stage is not None:
                try:
                    on_stage(stage, event)
                except Exception:
                    pass  # never let a UI callback break the pipeline

        start = monotonic()

        # ------------------------------------------------------------------
        # Stage 1: Planning
        # ------------------------------------------------------------------
        _emit(PipelineStage.planning, "start")
        plan = await self._planner.plan(
            query, output_format, deep=(mode == PipelineMode.deep),
        )
        meta = self._store.create(plan, mode)
        self._store.complete_stage(plan.slug, PipelineStage.planning)
        self._store.set_status(plan.slug, StageStatus.running)
        _emit(PipelineStage.planning, "done")

        workspace_dir = self._store.path_for(plan.slug)

        # ------------------------------------------------------------------
        # Deep mode: run verification and visualization in parallel
        # ------------------------------------------------------------------
        if mode == PipelineMode.deep and not skip_verification:
            verification, visualization = await self._run_parallel(
                plan, meta, mode, workspace_dir, _emit,
            )
        else:
            # Explore mode (or explicit --no-verify): sequential
            # Stage 2: Verification
            _emit(PipelineStage.verification, "start")
            if skip_verification:
                verification = VerificationResult(
                    status=VerificationStatus.skipped,
                    lean_output="",
                    failure_reason="Verification skipped by caller",
                    duration_seconds=0.0,
                )
            else:
                verification = await self._run_verification(plan, mode, workspace_dir)

            self._store.save_stage_result(plan.slug, PipelineStage.verification, verification)
            self._store.complete_stage(plan.slug, PipelineStage.verification)
            _emit(PipelineStage.verification, "done")

            # CRITICAL INVARIANT: REFUTED → halt immediately
            if verification.should_halt:
                self._store.set_status(plan.slug, StageStatus.completed)
                self._index_result(meta)
                return ExplorationResult(
                    plan=plan,
                    verification=verification,
                    visualization=None,
                    summary=None,
                    meta=meta,
                    duration_seconds=monotonic() - start,
                )

            # Stage 3: Visualization
            _emit(PipelineStage.visualization, "start")
            visualization = await self._run_visualization(plan, meta, mode, verification)
            self._store.save_stage_result(plan.slug, PipelineStage.visualization, visualization)
            self._store.complete_stage(plan.slug, PipelineStage.visualization)
            _emit(PipelineStage.visualization, "done")

        # ------------------------------------------------------------------
        # Stage 4: Summarization
        # ------------------------------------------------------------------
        _emit(PipelineStage.summarization, "start")

        # Collect reasoning from upstream stages for richer summaries
        reasoning_parts: list[str] = []
        for stage in (self._verifier, self._visualizer):
            val = getattr(stage, "_last_reasoning", None)
            if isinstance(val, str) and val:
                reasoning_parts.append(val)
        reasoning_context = "\n\n".join(reasoning_parts) if reasoning_parts else None

        summary = await self._run_summarization(
            plan, verification, workspace_dir, reasoning_context=reasoning_context,
        )
        self._store.complete_stage(plan.slug, PipelineStage.summarization)
        _emit(PipelineStage.summarization, "done")
        self._store.set_status(plan.slug, StageStatus.completed)
        self._index_result(meta)

        return ExplorationResult(
            plan=plan,
            verification=verification,
            visualization=visualization,
            summary=summary,
            meta=meta,
            duration_seconds=monotonic() - start,
        )

    # ------------------------------------------------------------------
    # Search index
    # ------------------------------------------------------------------

    def _index_result(self, meta: ExplorationMeta) -> None:
        if self._search_index is None:
            return
        try:
            ws_dir = self._store.path_for(meta.slug)
            self._search_index.index_exploration(meta.slug, ws_dir)
        except Exception:
            logger.warning("Failed to index exploration %s", meta.slug, exc_info=True)

    # ------------------------------------------------------------------
    # Internal stage runners with error isolation
    # ------------------------------------------------------------------

    async def _run_parallel(
        self,
        plan: ExplorationPlan,
        meta: ExplorationMeta,
        mode: PipelineMode,
        workspace_dir: Path,
        _emit: Callable[[PipelineStage, str], None],
    ) -> tuple[VerificationResult, VisualizationResult | None]:
        """Run verification and visualization concurrently (deep mode).

        If verification returns REFUTED, visualization is cancelled.
        """
        _emit(PipelineStage.verification, "start")
        _emit(PipelineStage.visualization, "start")

        # Use a placeholder verification status for visualization badge
        placeholder = VerificationResult(
            status=VerificationStatus.skipped,
            lean_output="",
            duration_seconds=0.0,
        )

        verify_task = asyncio.create_task(
            self._run_verification(plan, mode, workspace_dir)
        )
        viz_task = asyncio.create_task(
            self._run_visualization(plan, meta, mode, placeholder)
        )

        # Wait for verification first to check for REFUTED
        verification = await verify_task
        self._store.save_stage_result(plan.slug, PipelineStage.verification, verification)
        self._store.complete_stage(plan.slug, PipelineStage.verification)
        _emit(PipelineStage.verification, "done")

        if verification.should_halt:
            viz_task.cancel()
            try:
                await viz_task
            except asyncio.CancelledError:
                pass
            _emit(PipelineStage.visualization, "done")
            self._store.set_status(plan.slug, StageStatus.completed)
            self._index_result(meta)
            return verification, None

        visualization = await viz_task
        # Patch the badge with the actual verification status
        visualization.verification_badge = Badge.from_status(verification.status)
        self._store.save_stage_result(plan.slug, PipelineStage.visualization, visualization)
        self._store.complete_stage(plan.slug, PipelineStage.visualization)
        _emit(PipelineStage.visualization, "done")

        return verification, visualization

    async def _run_verification(
        self, plan: ExplorationPlan, mode: PipelineMode, workspace_dir: Path
    ) -> VerificationResult:
        """Run verifier; return UNVERIFIABLE on any exception."""
        try:
            return await self._verifier.verify(plan.theorem_statements, mode, workspace_dir=workspace_dir)
        except Exception:
            return VerificationResult(
                status=VerificationStatus.unverifiable,
                lean_output="",
                failure_reason="Verification raised an unexpected exception",
                duration_seconds=0.0,
            )

    async def _run_visualization(
        self,
        plan: ExplorationPlan,
        meta: ExplorationMeta,
        mode: PipelineMode,
        verification: VerificationResult,
    ) -> VisualizationResult:
        """Generate scene code and render it."""
        workspace_dir = self._store.path_for(plan.slug)
        await self._visualizer.generate_scene_code(plan.visualization_scenes, plan.topic, workspace_dir=workspace_dir)
        scene_path = workspace_dir / "scene_01.py"
        output_path = workspace_dir / "output"
        return await self._visualizer.render(
            scene_path=scene_path,
            output_path=output_path,
            mode=mode,
            verification_status=verification.status,
            output_format=plan.output_format,
        )

    async def _run_summarization(
        self,
        plan: ExplorationPlan,
        verification: VerificationResult,
        workspace_dir: Path,
        reasoning_context: str | None = None,
    ) -> Summary:
        """Summarize the exploration; return a fallback Summary on any exception."""
        try:
            return await self._summarizer.summarize(
                plan, verification,
                workspace_dir=workspace_dir,
                reasoning_context=reasoning_context,
            )
        except Exception:
            return Summary(
                explanation=f"Summary unavailable for '{plan.topic}'.",
                key_insights=[],
            )

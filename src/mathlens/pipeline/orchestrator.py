"""Pipeline orchestrator for MathLens — coordinates all pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Optional

from mathlens.models import (
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
    ) -> ExplorationResult:
        """Run the full pipeline for *query* and return an ExplorationResult."""
        start = monotonic()

        # ------------------------------------------------------------------
        # Stage 1: Planning
        # ------------------------------------------------------------------
        plan = await self._planner.plan(query, output_format)
        meta = self._store.create(plan, mode)
        self._store.complete_stage(plan.slug, PipelineStage.planning)
        self._store.set_status(plan.slug, StageStatus.running)

        # ------------------------------------------------------------------
        # Stage 2: Verification
        # ------------------------------------------------------------------
        if skip_verification:
            verification = VerificationResult(
                status=VerificationStatus.skipped,
                lean_output="",
                failure_reason="Verification skipped by caller",
                duration_seconds=0.0,
            )
        else:
            verification = await self._run_verification(plan, mode)

        self._store.save_stage_result(plan.slug, PipelineStage.verification, verification)
        self._store.complete_stage(plan.slug, PipelineStage.verification)

        # ------------------------------------------------------------------
        # CRITICAL INVARIANT: REFUTED → halt immediately
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # Stage 3: Visualization
        # ------------------------------------------------------------------
        visualization = await self._run_visualization(plan, meta, mode, verification)
        self._store.save_stage_result(plan.slug, PipelineStage.visualization, visualization)
        self._store.complete_stage(plan.slug, PipelineStage.visualization)

        # ------------------------------------------------------------------
        # Stage 4: Summarization
        # ------------------------------------------------------------------
        summary = await self._run_summarization(plan, verification)
        self._store.complete_stage(plan.slug, PipelineStage.summarization)
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

    async def _run_verification(
        self, plan: ExplorationPlan, mode: PipelineMode
    ) -> VerificationResult:
        """Run verifier; return UNVERIFIABLE on any exception."""
        try:
            return await self._verifier.verify(plan.theorem_statements, mode)
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
        await self._visualizer.generate_scene_code(plan.visualization_scenes, plan.topic)
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
        self, plan: ExplorationPlan, verification: VerificationResult
    ) -> Summary:
        """Summarize the exploration; return a fallback Summary on any exception."""
        try:
            return await self._summarizer.summarize(plan, verification)
        except Exception:
            return Summary(
                explanation=f"Summary unavailable for '{plan.topic}'.",
                key_insights=[],
            )

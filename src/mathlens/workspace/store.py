"""File-based workspace store with atomic writes and checkpointing."""

from __future__ import annotations

import json
import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from mathlens.models import (
    ExplorationMeta,
    ExplorationPlan,
    PipelineMode,
    PipelineStage,
    StageStatus,
)

logger = logging.getLogger(__name__)


class WorkspaceStore:
    """Manages on-disk workspaces for exploration runs."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, slug: str) -> Path:
        """Return the workspace directory for *slug*."""
        return self._root / slug

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create(self, plan: ExplorationPlan, mode: PipelineMode) -> ExplorationMeta:
        """Create a workspace directory, write meta.json and plan.json, return meta."""
        ws = self.path_for(plan.slug)
        ws.mkdir(parents=True, exist_ok=True)

        meta = ExplorationMeta(
            topic=plan.topic,
            slug=plan.slug,
            mode=mode,
        )

        self._write_json(ws / "meta.json", meta)
        self._write_json(ws / "plan.json", plan)

        return meta

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def save_artifact(self, slug: str, filename: str, content: bytes) -> Path:
        """Write *content* atomically to *filename* inside the slug workspace.

        Cleans up any stale .tmp files for the same target before writing.
        """
        dest = self.path_for(slug) / filename
        tmp = dest.with_suffix(dest.suffix + ".tmp")

        # Clean up stale tmp from a previous crash.
        if tmp.exists():
            tmp.unlink()

        tmp.write_bytes(content)
        tmp.rename(dest)
        return dest

    def save_stage_result(
        self, slug: str, stage: PipelineStage, result: BaseModel
    ) -> Path:
        """Serialize *result* to JSON and save as ``{stage.value}_result.json``."""
        filename = f"{stage.value}_result.json"
        content = result.model_dump_json(indent=2).encode()
        return self.save_artifact(slug, filename, content)

    # ------------------------------------------------------------------
    # Meta management
    # ------------------------------------------------------------------

    def complete_stage(self, slug: str, stage: PipelineStage) -> ExplorationMeta:
        """Mark *stage* complete, advance current_stage, set status to RUNNING, persist."""
        meta = self.load_meta(slug)
        meta.complete_stage(stage)
        meta.status = StageStatus.running
        meta.updated_at = datetime.now(tz=timezone.utc)
        self._write_json(self.path_for(slug) / "meta.json", meta)
        return meta

    def set_status(self, slug: str, status: StageStatus) -> ExplorationMeta:
        """Update exploration status and persist."""
        meta = self.load_meta(slug)
        meta.status = status
        meta.updated_at = datetime.now(tz=timezone.utc)
        self._write_json(self.path_for(slug) / "meta.json", meta)
        return meta

    def load_meta(self, slug: str) -> ExplorationMeta:
        """Read and parse meta.json for *slug*."""
        path = self.path_for(slug) / "meta.json"
        return ExplorationMeta.model_validate_json(path.read_text())

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def list_explorations(self) -> list[ExplorationMeta]:
        """Return all explorations sorted by directory name (reverse), skipping corrupt ones."""
        results: list[ExplorationMeta] = []
        dirs = sorted(
            (d for d in self._root.iterdir() if d.is_dir()),
            key=lambda d: d.name,
            reverse=True,
        )
        for d in dirs:
            meta_path = d / "meta.json"
            if not meta_path.exists():
                continue
            try:
                results.append(ExplorationMeta.model_validate_json(meta_path.read_text()))
            except Exception as exc:  # noqa: BLE001
                warnings.warn(
                    f"Skipping corrupt workspace {d.name}: {exc}",
                    stacklevel=2,
                )
        return results

    def find_by_topic(self, topic: str) -> ExplorationMeta | None:
        """Return the first exploration whose topic matches *topic*, or None."""
        for meta in self.list_explorations():
            if meta.topic == topic:
                return meta
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_json(self, path: Path, model: BaseModel) -> None:
        """Atomically write *model* as JSON to *path*."""
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(model.model_dump_json(indent=2))
        tmp.rename(path)

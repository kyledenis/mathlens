"""Domain models for MathLens."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Intent(str, Enum):
    prove = "prove"
    explain = "explain"
    explore = "explore"
    compare = "compare"


class VerificationStatus(str, Enum):
    verified = "verified"
    unverifiable = "unverifiable"
    refuted = "refuted"
    skipped = "skipped"


class OutputFormat(str, Enum):
    video = "video"
    frames = "frames"
    diagram = "diagram"


class PipelineMode(str, Enum):
    explore = "explore"
    deep = "deep"


class Difficulty(str, Enum):
    elementary = "elementary"
    intermediate = "intermediate"
    advanced = "advanced"


class RenderQuality(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    production = "production"


class PipelineStage(str, Enum):
    planning = "planning"
    verification = "verification"
    visualization = "visualization"
    summarization = "summarization"

    @property
    def next(self) -> Optional["PipelineStage"]:
        order = [
            PipelineStage.planning,
            PipelineStage.verification,
            PipelineStage.visualization,
            PipelineStage.summarization,
        ]
        idx = order.index(self)
        if idx + 1 < len(order):
            return order[idx + 1]
        return None


class StageStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class Badge(str, Enum):
    verified = "verified"
    unverified = "unverified"
    refuted = "refuted"
    unchecked = "unchecked"

    @classmethod
    def from_status(cls, status: VerificationStatus) -> "Badge":
        mapping = {
            VerificationStatus.verified: cls.verified,
            VerificationStatus.unverifiable: cls.unverified,
            VerificationStatus.refuted: cls.refuted,
            VerificationStatus.skipped: cls.unchecked,
        }
        return mapping[status]

    @property
    def label(self) -> str:
        labels = {
            Badge.verified: "Verified",
            Badge.unverified: "Unverified",
            Badge.refuted: "Refuted",
            Badge.unchecked: "Unchecked",
        }
        return labels[self]

    @property
    def icon(self) -> str:
        icons = {
            Badge.verified: "[green]✓ Verified[/green]",
            Badge.unverified: "[yellow]~ Unverified[/yellow]",
            Badge.refuted: "[red]✗ Refuted[/red]",
            Badge.unchecked: "[dim]? Unchecked[/dim]",
        }
        return icons[self]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ScenePlan(BaseModel):
    title: str
    description: str
    key_objects: list[str] = Field(default_factory=list)
    animation_hints: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    """Ordered shot list — each step becomes one animation or group.
    E.g. ["Title: 'Can any signal be built from sine waves?'",
          "Draw axes (Time vs Amplitude), label both",
          "Plot sin(t) in blue, caption: 'A pure frequency'"]"""


class ExplorationPlan(BaseModel):
    topic: str
    slug: str
    intent: Intent
    theorem_statements: list[str]
    visualization_scenes: list[ScenePlan]
    output_format: OutputFormat
    difficulty: Difficulty
    related_explorations: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    status: VerificationStatus
    proof_path: Optional[Path] = None
    lean_output: str
    failure_reason: Optional[str] = None
    mathlib_gaps: list[str] = Field(default_factory=list)
    duration_seconds: float

    @property
    def should_halt(self) -> bool:
        return self.status == VerificationStatus.refuted


class RenderedScene(BaseModel):
    title: str
    source_path: Path
    output_path: Path
    duration_seconds: float


class VisualizationResult(BaseModel):
    scenes: list[RenderedScene] = Field(default_factory=list)
    output_path: Path
    output_format: OutputFormat
    source_paths: list[Path]
    render_quality: RenderQuality
    duration_seconds: float
    verification_badge: Badge


class Summary(BaseModel):
    explanation: str
    key_insights: list[str]
    prerequisites: list[str] = Field(default_factory=list)
    further_reading: list[str] = Field(default_factory=list)
    path: Optional[Path] = None


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


class ExplorationMeta(BaseModel):
    topic: str
    slug: str
    mode: PipelineMode
    status: StageStatus = StageStatus.pending
    current_stage: PipelineStage = PipelineStage.planning
    completed_stages: list[PipelineStage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    tags: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)

    def complete_stage(self, stage: PipelineStage) -> None:
        if stage not in self.completed_stages:
            self.completed_stages.append(stage)
        next_stage = stage.next
        if next_stage is not None:
            self.current_stage = next_stage
        self.updated_at = _utc_now()

    @property
    def is_resumable(self) -> bool:
        return self.status in (StageStatus.failed, StageStatus.running)

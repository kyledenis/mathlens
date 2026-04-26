"""Pipeline progress display with adaptive time estimates."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mathlens.models import PipelineMode, PipelineStage
from mathlens.ui.console import format_duration

logger = logging.getLogger(__name__)

STAGE_LABELS = {
    PipelineStage.planning: "Planning",
    PipelineStage.verification: "Verifying",
    PipelineStage.visualization: "Visualizing",
    PipelineStage.summarization: "Summarizing",
}

# Fallback estimates when no historical data exists (seconds).
# Keyed by (stage, mode, provider). Provider "" is the final fallback.
_DEFAULT_ESTIMATES: dict[tuple[PipelineStage, PipelineMode, str], int] = {
    # API — direct Anthropic calls, fastest
    (PipelineStage.planning, PipelineMode.explore, "api"): 15,
    (PipelineStage.visualization, PipelineMode.explore, "api"): 45,
    (PipelineStage.summarization, PipelineMode.explore, "api"): 12,
    (PipelineStage.planning, PipelineMode.deep, "api"): 20,
    (PipelineStage.verification, PipelineMode.deep, "api"): 60,
    (PipelineStage.visualization, PipelineMode.deep, "api"): 90,
    (PipelineStage.summarization, PipelineMode.deep, "api"): 15,
    # CLI — claude -p, session bootstrap overhead
    (PipelineStage.planning, PipelineMode.explore, "cli"): 25,
    (PipelineStage.visualization, PipelineMode.explore, "cli"): 120,
    (PipelineStage.summarization, PipelineMode.explore, "cli"): 20,
    (PipelineStage.planning, PipelineMode.deep, "cli"): 30,
    (PipelineStage.verification, PipelineMode.deep, "cli"): 120,
    (PipelineStage.visualization, PipelineMode.deep, "cli"): 240,
    (PipelineStage.summarization, PipelineMode.deep, "cli"): 25,
    # Local — LM Studio / Ollama, depends heavily on hardware
    (PipelineStage.planning, PipelineMode.explore, "local"): 40,
    (PipelineStage.visualization, PipelineMode.explore, "local"): 180,
    (PipelineStage.summarization, PipelineMode.explore, "local"): 30,
    (PipelineStage.planning, PipelineMode.deep, "local"): 50,
    (PipelineStage.verification, PipelineMode.deep, "local"): 180,
    (PipelineStage.visualization, PipelineMode.deep, "local"): 300,
    (PipelineStage.summarization, PipelineMode.deep, "local"): 40,
}

# How many recent durations to keep per (stage, mode) key.
_MAX_HISTORY = 10


class DurationTracker:
    """Tracks actual stage durations and provides rolling averages.

    Stored as a simple JSON file in the workspace:
    ``{"planning:explore": [18.2, 21.5, ...], ...}``
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, list[float]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2))
        except OSError:
            logger.debug("Failed to save duration history to %s", self._path)

    @staticmethod
    def _key(stage: PipelineStage, mode: PipelineMode, provider: str = "") -> str:
        parts = [stage.value, mode.value]
        if provider:
            parts.append(provider)
        return ":".join(parts)

    def record(
        self, stage: PipelineStage, mode: PipelineMode, duration: float,
        provider: str = "",
    ) -> None:
        """Record an actual duration for a stage.

        *provider* should be the provider name (e.g. "cli", "api", "local")
        so estimates are accurate when switching between providers.
        """
        if duration <= 0:
            return
        key = self._key(stage, mode, provider)
        history = self._data.setdefault(key, [])
        history.append(round(duration, 1))
        # Keep only recent entries
        if len(history) > _MAX_HISTORY:
            self._data[key] = history[-_MAX_HISTORY:]
        self._save()

    def average(
        self, stage: PipelineStage, mode: PipelineMode, provider: str = "",
    ) -> float | None:
        """Return the rolling average duration, or None if no data.

        Tries provider-specific history first, falls back to
        provider-agnostic history for backward compatibility.
        """
        if provider:
            key = self._key(stage, mode, provider)
            history = self._data.get(key, [])
            if history:
                return sum(history) / len(history)
        # Fallback to provider-agnostic key
        key = self._key(stage, mode)
        history = self._data.get(key, [])
        if not history:
            return None
        return sum(history) / len(history)


class PipelineProgress:
    def __init__(
        self,
        mode: PipelineMode = PipelineMode.explore,
        tracker: DurationTracker | None = None,
        provider: str = "",
    ) -> None:
        self._mode = mode
        self._tracker = tracker
        self._provider = provider

    def label_for(self, stage: PipelineStage) -> str:
        return STAGE_LABELS[stage]

    def estimate_for(self, stage: PipelineStage) -> int:
        """Return the best estimate in seconds — historical average or fallback."""
        if self._tracker is not None:
            avg = self._tracker.average(stage, self._mode, self._provider)
            if avg is not None:
                # Add 10% buffer — better to overestimate
                return int(avg * 1.1)
        # Provider-specific default, then 0 if unknown
        return _DEFAULT_ESTIMATES.get((stage, self._mode, self._provider), 0)

    def format_stage_start(self, stage: PipelineStage) -> str:
        est = self.estimate_for(stage)
        label = self.label_for(stage)
        if est > 0:
            return f"  [dim]>[/dim] {label} [dim](~{format_duration(est)})[/dim]..."
        return f"  [dim]>[/dim] {label}..."

    def format_stage_done(self, stage: PipelineStage, duration: float) -> str:
        return f"  [green]>[/green] {self.label_for(stage)} [dim]({format_duration(duration)})[/dim]"

    def format_total_estimate(self) -> str:
        total = sum(
            self.estimate_for(s) for s in [
                PipelineStage.planning,
                PipelineStage.verification,
                PipelineStage.visualization,
                PipelineStage.summarization,
            ]
        )
        return f"[dim]Estimated total: ~{format_duration(total)}[/dim]"

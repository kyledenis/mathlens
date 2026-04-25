"""Pipeline progress display with time estimates."""

from mathlens.models import PipelineMode, PipelineStage
from mathlens.ui.console import format_duration

STAGE_LABELS = {
    PipelineStage.planning: "Planning",
    PipelineStage.verification: "Verifying",
    PipelineStage.visualization: "Visualizing",
    PipelineStage.summarization: "Summarizing",
}

# Estimated durations in seconds per (stage, mode).
# These are conservative averages — better to overestimate than underestimate.
STAGE_ESTIMATES: dict[tuple[PipelineStage, PipelineMode], int] = {
    (PipelineStage.planning, PipelineMode.explore): 20,
    (PipelineStage.planning, PipelineMode.deep): 25,
    (PipelineStage.verification, PipelineMode.explore): 0,  # skipped by default
    (PipelineStage.verification, PipelineMode.deep): 90,
    (PipelineStage.visualization, PipelineMode.explore): 90,
    (PipelineStage.visualization, PipelineMode.deep): 180,
    (PipelineStage.summarization, PipelineMode.explore): 20,
    (PipelineStage.summarization, PipelineMode.deep): 25,
}


class PipelineProgress:
    def __init__(self, mode: PipelineMode = PipelineMode.explore) -> None:
        self._mode = mode

    def label_for(self, stage: PipelineStage) -> str:
        return STAGE_LABELS[stage]

    def estimate_for(self, stage: PipelineStage) -> int:
        return STAGE_ESTIMATES.get((stage, self._mode), 0)

    def format_stage_start(self, stage: PipelineStage) -> str:
        est = self.estimate_for(stage)
        label = self.label_for(stage)
        if est > 0:
            return f"  [dim]>[/dim] {label} [dim](~{format_duration(est)})[/dim]..."
        return f"  [dim]>[/dim] {label}..."

    def format_stage_done(self, stage: PipelineStage, duration: float) -> str:
        return f"  [green]>[/green] {self.label_for(stage)} [dim]({format_duration(duration)})[/dim]"

    def format_total_estimate(self) -> str:
        """Return a summary line with the estimated total time."""
        total = sum(
            self.estimate_for(s) for s in [
                PipelineStage.planning,
                PipelineStage.verification,
                PipelineStage.visualization,
                PipelineStage.summarization,
            ]
        )
        return f"[dim]Estimated total: ~{format_duration(total)}[/dim]"

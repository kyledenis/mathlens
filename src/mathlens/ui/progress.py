"""Pipeline progress display."""

from mathlens.models import PipelineStage
from mathlens.ui.console import format_duration

STAGE_LABELS = {
    PipelineStage.planning: "Planning",
    PipelineStage.verification: "Verifying",
    PipelineStage.visualization: "Visualizing",
    PipelineStage.summarization: "Summarizing",
}

# Intentionally text-based, no emojis. Clean and rewarding.
STAGE_MARKERS = {
    PipelineStage.planning: "[dim]>[/dim]",
    PipelineStage.verification: "[dim]>[/dim]",
    PipelineStage.visualization: "[dim]>[/dim]",
    PipelineStage.summarization: "[dim]>[/dim]",
}

STAGE_DONE_MARKERS = {
    PipelineStage.planning: "[green]>[/green]",
    PipelineStage.verification: "[green]>[/green]",
    PipelineStage.visualization: "[green]>[/green]",
    PipelineStage.summarization: "[green]>[/green]",
}


class PipelineProgress:
    def label_for(self, stage: PipelineStage) -> str:
        return STAGE_LABELS[stage]

    def icon_for(self, stage: PipelineStage) -> str:
        return STAGE_MARKERS[stage]

    def format_stage_start(self, stage: PipelineStage) -> str:
        return f"  {self.icon_for(stage)} {self.label_for(stage)}..."

    def format_stage_done(self, stage: PipelineStage, duration: float) -> str:
        done = STAGE_DONE_MARKERS[stage]
        return f"  {done} {self.label_for(stage)} [dim]({format_duration(duration)})[/dim]"

"""Pipeline progress display."""

from mathlens.models import PipelineStage
from mathlens.ui.console import format_duration

STAGE_LABELS = {
    PipelineStage.planning: "Planning",
    PipelineStage.verification: "Verifying",
    PipelineStage.visualization: "Visualizing",
    PipelineStage.summarization: "Summarizing",
}


class PipelineProgress:
    def label_for(self, stage: PipelineStage) -> str:
        return STAGE_LABELS[stage]

    def format_stage_start(self, stage: PipelineStage) -> str:
        return f"  [dim]>[/dim] {self.label_for(stage)}..."

    def format_stage_done(self, stage: PipelineStage, duration: float) -> str:
        return f"  [green]>[/green] {self.label_for(stage)} [dim]({format_duration(duration)})[/dim]"

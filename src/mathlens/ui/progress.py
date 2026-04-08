"""Pipeline progress display."""

from mathlens.models import PipelineStage
from mathlens.ui.console import format_duration

STAGE_LABELS = {
    PipelineStage.planning: "Planning",
    PipelineStage.verification: "Verifying",
    PipelineStage.visualization: "Visualizing",
    PipelineStage.summarization: "Summarizing",
}

STAGE_ICONS = {
    PipelineStage.planning: "📋",
    PipelineStage.verification: "🔍",
    PipelineStage.visualization: "🎬",
    PipelineStage.summarization: "📝",
}


class PipelineProgress:
    def label_for(self, stage: PipelineStage) -> str:
        return STAGE_LABELS[stage]

    def icon_for(self, stage: PipelineStage) -> str:
        return STAGE_ICONS[stage]

    def format_stage_start(self, stage: PipelineStage) -> str:
        return f"{self.icon_for(stage)} {self.label_for(stage)}..."

    def format_stage_done(self, stage: PipelineStage, duration: float) -> str:
        return f"  ✓ {self.label_for(stage)} ({format_duration(duration)})"

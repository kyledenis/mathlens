"""Planner pipeline stage for MathLens."""

from __future__ import annotations

import json
from datetime import date
from typing import Optional

from mathlens.pipeline.response_cleaner import clean_json_response
from mathlens.pipeline.validation import validate_json
from mathlens.models import (
    Difficulty,
    ExplorationPlan,
    Intent,
    OutputFormat,
    ScenePlan,
)
from mathlens.providers.base import LLMProvider


PLANNER_SYSTEM_EXPLORE = """\
You are a mathematics education planner. Given a user query, produce a concise JSON plan.

IMPORTANT: Keep it focused. Generate at most 2 visualization scenes using only simple \
Manim primitives (Text, MathTex, Circle, Line, Arrow, Axes). Avoid complex objects \
like ComplexPlane, TracedPath, or TransformMatchingTex.

Fields:
- topic (str): slug identifier (e.g. "harmonic-series-divergence")
- intent (str): one of "prove", "explain", "explore", "compare"
- theorem_statements (list[str]): 1-3 precise statements
- visualization_scenes (list[object]): 1-2 scenes, each with title, description, \
key_objects (list[str]), animation_hints (list[str])
- output_format (str): one of "video", "frames", "diagram"
- difficulty (str): one of "elementary", "intermediate", "advanced"
- prerequisites (list[str]): topic slugs

Respond with only valid JSON. No explanation, no markdown fences.\
"""

PLANNER_SYSTEM_DEEP = """\
You are a mathematics education planner. Given a user query about a mathematical topic,
produce a structured JSON plan with the following fields:

- topic (str): slug identifier (e.g. "harmonic-series-divergence")
- intent (str): one of "prove", "explain", "explore", "compare"
- theorem_statements (list[str]): precise mathematical statements to address
- visualization_scenes (list[object]): 3-5 scenes, each with title, description, \
key_objects (list[str]), animation_hints (list[str])
- output_format (str): one of "video", "frames", "diagram"
- difficulty (str): one of "elementary", "intermediate", "advanced"
- prerequisites (list[str]): prerequisite topic slugs

Respond with only valid JSON. No explanation, no markdown fences.\
"""


class Planner:
    """LLM-backed planning stage that produces a structured ExplorationPlan."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def plan(
        self,
        query: str,
        output_format: Optional[OutputFormat] = None,
        deep: bool = False,
    ) -> ExplorationPlan:
        """Call the LLM provider to produce an ExplorationPlan from a user query."""
        system = PLANNER_SYSTEM_DEEP if deep else PLANNER_SYSTEM_EXPLORE
        prompt = f"Plan a mathematical exploration for the following query:\n\n{query}"
        response = await self._provider.complete(
            prompt,
            system=system,
            temperature=0.2,
            response_format="json",
        )
        data = self._parse_response(response.content)

        # Override output_format if provided
        if output_format is not None:
            data["output_format"] = output_format.value

        # Generate slug
        topic = data["topic"]
        data["slug"] = f"{date.today().isoformat()}_{topic}"

        # Construct ScenePlan objects
        raw_scenes = data.get("visualization_scenes", [])
        data["visualization_scenes"] = [
            ScenePlan(**scene) if isinstance(scene, dict) else scene
            for scene in raw_scenes
        ]

        # Ensure related_explorations is present (optional field with default)
        data.setdefault("related_explorations", [])

        return ExplorationPlan.model_validate(data)

    def _parse_response(self, content: str) -> dict:
        """Extract and parse JSON from LLM response, handling thinking traces and artifacts."""
        cleaned = clean_json_response(content)
        try:
            return json.loads(cleaned.code)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse planner JSON response: {exc}") from exc

"""Planner pipeline stage for MathLens."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Optional

from mathlens.models import (
    Difficulty,
    ExplorationPlan,
    Intent,
    OutputFormat,
    ScenePlan,
)
from mathlens.providers.base import LLMProvider


PLANNER_SYSTEM = """\
You are a mathematics education planner. Given a user query about a mathematical topic,
produce a structured JSON plan with the following fields:

- topic (str): a slug-style identifier for the topic (e.g. "harmonic-series-divergence")
- intent (str): one of "prove", "explain", "explore", "compare"
- theorem_statements (list[str]): precise mathematical statements to address
- visualization_scenes (list[object]): each with:
    - title (str)
    - description (str)
    - key_objects (list[str])
    - animation_hints (list[str])
- output_format (str): one of "video", "frames", "diagram"
- difficulty (str): one of "elementary", "intermediate", "advanced"
- prerequisites (list[str]): prerequisite topic slugs

Respond with only valid JSON. Do not include any explanation or markdown fences.\
"""


class Planner:
    """LLM-backed planning stage that produces a structured ExplorationPlan."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def plan(
        self,
        query: str,
        output_format: Optional[OutputFormat] = None,
    ) -> ExplorationPlan:
        """Call the LLM provider to produce an ExplorationPlan from a user query."""
        prompt = f"Plan a mathematical exploration for the following query:\n\n{query}"
        response = await self._provider.complete(
            prompt,
            system=PLANNER_SYSTEM,
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
        """Strip markdown code fences if present and parse JSON."""
        stripped = content.strip()
        # Remove markdown code fences (```json ... ``` or ``` ... ```)
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
        stripped = stripped.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse planner JSON response: {exc}") from exc

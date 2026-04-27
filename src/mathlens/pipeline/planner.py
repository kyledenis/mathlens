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
You are a mathematics education planner. Given a user query, produce a JSON plan.

The most important field is visualization_scenes[0].steps — this is the shot list \
that directly controls the animation. Each step becomes one animation. Write 6-8 \
steps that teach the concept visually:
- Start with a hook question
- Introduce prerequisite concepts the viewer needs
- Build visual intuition step by step — show geometry and movement BEFORE equations
- Each step is one sentence: what to show and a caption explaining WHY
- End with a takeaway that answers the hook

Example steps:
["Title: 'What does multiplication by i actually do?'",
 "Draw complex plane with labelled Re and Im axes",
 "Plot the point 1 on the real axis, caption: 'Start at 1'",
 "Rotate 1 by 90° to i, caption: 'Multiplying by i rotates 90° counterclockwise'",
 "Rotate i to -1, then to -i, then back to 1, caption: 'Four rotations = full circle'",
 "Show equation i² = -1, caption: 'Two 90° rotations = 180° flip = multiplying by -1'",
 "Takeaway: 'i is not imaginary — it is a 90° rotation'"]

Fields:
- topic (str): slug identifier
- intent (str): one of "prove", "explain", "explore", "compare"
- theorem_statements (list[str]): 1-3 precise statements
- visualization_scenes (list[object]): exactly 1 scene with:
    - title (str), description (str)
    - key_objects (list[str]): Manim objects to use
    - steps (list[str]): 8-12 ordered animation steps (THE SHOT LIST)
- output_format (str): one of "video", "frames", "diagram"
- difficulty (str): one of "elementary", "intermediate", "advanced"
- prerequisites (list[str]): topic slugs

Respond with only valid JSON.\
"""

PLANNER_SYSTEM_DEEP = """\
You are a mathematics education planner. Given a user query, produce a JSON plan.

The most important field is visualization_scenes[0].steps — this is the shot list \
that directly controls the animation. Write 12-18 steps for a thorough visual proof \
or explanation. Include rigorous detail and formal notation where appropriate.

Fields:
- topic (str): slug identifier
- intent (str): one of "prove", "explain", "explore", "compare"
- theorem_statements (list[str]): precise mathematical statements
- visualization_scenes (list[object]): 1-2 scenes, each with:
    - title (str), description (str)
    - key_objects (list[str]): Manim objects to use
    - steps (list[str]): 12-18 ordered animation steps (THE SHOT LIST)
- output_format (str): one of "video", "frames", "diagram"
- difficulty (str): one of "elementary", "intermediate", "advanced"
- prerequisites (list[str]): topic slugs

Respond with only valid JSON.\
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

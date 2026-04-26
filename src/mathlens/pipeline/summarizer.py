"""Summarizer pipeline stage for MathLens."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from mathlens.models import ExplorationPlan, Summary, VerificationResult, VerificationStatus
from mathlens.pipeline.response_cleaner import clean_json_response
from mathlens.workspace.atomic import atomic_write_text
from mathlens.providers.base import LLMProvider


SUMMARY_SYSTEM_EXPLORE = """\
Summarize this math topic for someone who is curious but NOT an expert. \
Assume they know basic algebra and geometry but nothing advanced.

Rules:
- Explain like a great teacher, not a textbook. Use analogies and plain language.
- If a concept requires prior knowledge, briefly explain that concept first.
- Never use jargon without defining it in the same sentence.
- key_insights should each be one clear sentence a non-expert can understand.

Produce JSON with:
- explanation (str): 2-3 sentence plain-language explanation
- key_insights (list[str]): 3-5 accessible insights
- prerequisites (list[str]): topic slugs
- further_reading (list[str]): topic slugs

Respond with only valid JSON.\
"""

SUMMARY_SYSTEM_DEEP = """\
Summarize this math topic with mathematical rigor. The reader has undergraduate-level \
math knowledge.

Produce JSON with:
- explanation (str): precise mathematical explanation with key definitions
- key_insights (list[str]): 4-6 insights including proof techniques and connections
- prerequisites (list[str]): topic slugs
- further_reading (list[str]): topic slugs

Respond with only valid JSON.\
"""


class Summarizer:
    """LLM-backed summarization stage that produces an artifact-anchored Summary."""

    def __init__(self, provider: LLMProvider, workspace_dir: Path) -> None:
        self._provider = provider
        self._workspace_dir = workspace_dir

    async def summarize(
        self,
        plan: ExplorationPlan,
        verification: VerificationResult,
        workspace_dir: Optional[Path] = None,
        reasoning_context: Optional[str] = None,
        deep: bool = False,
    ) -> Summary:
        """Build a summary from the plan and verification result."""
        target_dir = workspace_dir or self._workspace_dir
        system = SUMMARY_SYSTEM_DEEP if deep else SUMMARY_SYSTEM_EXPLORE
        verification_context = self._build_verification_context(verification)
        prompt = self._build_prompt(plan, verification_context)
        if reasoning_context:
            prompt += (
                f"\n\nAdditional mathematical reasoning from upstream stages "
                f"(use this to enrich your summary):\n{reasoning_context}"
            )

        response = await self._provider.complete(
            prompt,
            system=system,
            temperature=0.3,
            response_format="json",
        )

        data = self._parse_response(response.content)

        markdown = self._format_markdown(data, plan)
        summary_path = target_dir / "summary.md"
        atomic_write_text(summary_path, markdown)

        return Summary(
            explanation=data.get("explanation", ""),
            key_insights=data.get("key_insights", []),
            prerequisites=data.get("prerequisites", []),
            further_reading=data.get("further_reading", []),
            path=summary_path,
        )

    def _build_verification_context(self, verification: VerificationResult) -> str:
        """Build a human-readable verification context string."""
        lines = [f"Verification status: {verification.status.value}"]
        if verification.failure_reason:
            lines.append(f"Failure reason: {verification.failure_reason}")
        if verification.lean_output:
            excerpt = verification.lean_output[:500]
            lines.append(f"Lean output (excerpt):\n{excerpt}")
        return "\n".join(lines)

    def _build_prompt(self, plan: ExplorationPlan, verification_context: str) -> str:
        """Compose the user prompt from plan and verification context."""
        theorems = "\n".join(f"- {t}" for t in plan.theorem_statements)
        return (
            f"Topic: {plan.topic}\n"
            f"Intent: {plan.intent.value}\n"
            f"Difficulty: {plan.difficulty.value}\n"
            f"Theorem statements:\n{theorems}\n\n"
            f"Verification context:\n{verification_context}\n\n"
            "Produce a JSON summary of this topic."
        )

    def _parse_response(self, content: str) -> dict:
        """Extract and parse JSON from LLM response; fall back to raw content as explanation."""
        cleaned = clean_json_response(content)
        try:
            return json.loads(cleaned.code)
        except json.JSONDecodeError:
            return {"explanation": content, "key_insights": [], "prerequisites": [], "further_reading": []}

    def _format_markdown(self, data: dict, plan: ExplorationPlan) -> str:
        """Format summary data as a markdown document."""
        lines = [f"# {plan.topic}", ""]

        explanation = data.get("explanation", "")
        if explanation:
            lines += [explanation, ""]

        key_insights = data.get("key_insights", [])
        if key_insights:
            lines.append("## Key Insights")
            lines.append("")
            for insight in key_insights:
                lines.append(f"- {insight}")
            lines.append("")

        prerequisites = data.get("prerequisites", [])
        if prerequisites:
            lines.append("## Prerequisites")
            lines.append("")
            for prereq in prerequisites:
                lines.append(f"- {prereq}")
            lines.append("")

        further_reading = data.get("further_reading", [])
        if further_reading:
            lines.append("## Further Reading")
            lines.append("")
            for item in further_reading:
                lines.append(f"- {item}")
            lines.append("")

        return "\n".join(lines)

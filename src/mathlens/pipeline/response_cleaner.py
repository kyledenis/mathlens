"""Universal LLM response cleaner for MathLens.

Handles output quirks from any model/provider combination:
- Thinking traces (<think>, <reasoning>, etc.) from DeepSeek, Qwen, etc.
- Session artifacts (★ Insight blocks) from Claude Code hooks
- Conversational preamble before code
- Markdown code fences

Thinking traces are preserved (not discarded) so downstream stages
like the summarizer can use the model's mathematical reasoning.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CleanedResponse:
    """Result of cleaning an LLM response."""

    code: str = ""
    """Clean code or JSON for the compiler/renderer."""

    reasoning: str = ""
    """Extracted thinking traces (may be empty)."""


# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Thinking / reasoning block patterns (various model formats)
_THINKING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<think>(.*?)</think>", re.DOTALL),
    re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL),
    re.compile(r"<reasoning>(.*?)</reasoning>", re.DOTALL),
    re.compile(r"<reflection>(.*?)</reflection>", re.DOTALL),
    re.compile(r"<\|thinking\|>(.*?)<\|/thinking\|>", re.DOTALL),
]

# ★ Insight block: backtick-delimited header + content + backtick-delimited footer
_INSIGHT_BLOCK = re.compile(
    r"`★[^`]*`\s*\n"  # header line: `★ Insight ───...`
    r"(?:.*?\n)*?"     # content lines (non-greedy)
    r"`─+`\s*",        # footer line: `─────...`
    re.DOTALL,
)

# Conversational preamble lines (before code)
_PREAMBLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(?:Here(?:'s| is) .*?[:.])\s*$", re.MULTILINE),
    re.compile(r"^(?:I'll |I will |Let me |Sure|Certainly|Of course).*$", re.MULTILINE),
    re.compile(r"^(?:It seems |The following |Below is |This is ).*$", re.MULTILINE),
    re.compile(r"^(?:Would you like ).*$", re.MULTILINE),
]

# Language-specific fence patterns — capture content inside the fence
_FENCE_PATTERNS: dict[str, re.Pattern[str]] = {
    "python": re.compile(r"```(?:python|py)\s*\n(.*?)```", re.DOTALL),
    "lean": re.compile(r"```(?:lean|lean4)\s*\n(.*?)```", re.DOTALL),
    "json": re.compile(r"```(?:json)\s*\n(.*?)```", re.DOTALL),
}
_GENERIC_FENCE = re.compile(r"```\w*\s*\n(.*?)```", re.DOTALL)

# Language-specific code anchors (first line that signals real code)
_CODE_ANCHORS: dict[str, re.Pattern[str]] = {
    "python": re.compile(
        r"^(?:from\s+\w|import\s+\w|class\s+\w|def\s+\w|#!)", re.MULTILINE
    ),
    "lean": re.compile(
        r"^(?:import\s|theorem\s|lemma\s|def\s|open\s|namespace\s|section\s|#)",
        re.MULTILINE,
    ),
}


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def extract_thinking(raw: str) -> tuple[str, str]:
    """Separate thinking/reasoning traces from the rest of the response.

    Returns ``(reasoning_text, remaining_text)``.  If no traces are found,
    *reasoning_text* is empty and *remaining_text* is the original string.
    """
    reasoning_parts: list[str] = []
    text = raw

    for pattern in _THINKING_PATTERNS:
        while True:
            match = pattern.search(text)
            if match is None:
                break
            reasoning_parts.append(match.group(1).strip())
            text = text[: match.start()] + text[match.end() :]

    reasoning = "\n\n".join(reasoning_parts)
    return reasoning, text


def strip_artifacts(text: str) -> str:
    """Remove non-code artifacts (★ Insight blocks, conversational preamble)."""
    # Remove ★ Insight blocks
    text = _INSIGHT_BLOCK.sub("", text)

    # Remove conversational preamble lines
    for pattern in _PREAMBLE_PATTERNS:
        text = pattern.sub("", text)

    # Collapse runs of blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_fenced_code(text: str, language: str | None = None) -> str | None:
    """Extract content from the first matching fenced code block.

    Tries the language-specific fence first, then falls back to a generic
    fence.  Returns ``None`` if no fence is found.
    """
    if language and language in _FENCE_PATTERNS:
        match = _FENCE_PATTERNS[language].search(text)
        if match:
            return match.group(1).strip()

    # Fallback: any fenced block
    match = _GENERIC_FENCE.search(text)
    if match:
        return match.group(1).strip()

    return None


def find_code_anchor(text: str, language: str) -> int | None:
    """Return the character index of the first code-anchor line, or ``None``."""
    pattern = _CODE_ANCHORS.get(language)
    if pattern is None:
        return None
    match = pattern.search(text)
    return match.start() if match else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clean_code_response(raw: str, language: str) -> CleanedResponse:
    """Extract clean code from any LLM response, preserving reasoning.

    Pipeline:
    1. Extract and preserve thinking traces
    2. Strip conversational artifacts
    3. Try fenced code extraction (language-specific, then generic)
    4. Fallback: find first code-anchor line, take everything from there
    5. Last resort: return stripped text as-is
    """
    if not raw or not raw.strip():
        return CleanedResponse()

    reasoning, text = extract_thinking(raw)
    text = strip_artifacts(text)

    # Try fenced extraction
    code = extract_fenced_code(text, language)
    if code:
        return CleanedResponse(code=code, reasoning=reasoning)

    # Try anchor-based extraction
    anchor = find_code_anchor(text, language)
    if anchor is not None:
        code = text[anchor:].strip()
        return CleanedResponse(code=code, reasoning=reasoning)

    # Last resort: return whatever is left
    return CleanedResponse(code=text.strip(), reasoning=reasoning)


def clean_json_response(raw: str) -> CleanedResponse:
    """Extract clean JSON from any LLM response, preserving reasoning.

    Pipeline:
    1. Extract and preserve thinking traces
    2. Strip conversational artifacts
    3. Try fenced JSON extraction
    4. Fallback: find first ``{`` or ``[`` and attempt ``json.loads()``
    5. Last resort: return stripped text as-is
    """
    if not raw or not raw.strip():
        return CleanedResponse()

    reasoning, text = extract_thinking(raw)
    text = strip_artifacts(text)

    # Try fenced extraction
    code = extract_fenced_code(text, "json")
    if code:
        return CleanedResponse(code=code, reasoning=reasoning)

    # Try to find JSON start
    for i, ch in enumerate(text):
        if ch in "{[":
            candidate = text[i:]
            # Find the matching closing bracket
            try:
                json.loads(candidate)
                return CleanedResponse(code=candidate.strip(), reasoning=reasoning)
            except json.JSONDecodeError:
                # Try to find the end of the JSON object/array
                # by scanning for balanced braces
                pass
            # Even if full parse fails, return from the bracket onward
            # and let the caller's validation handle it
            return CleanedResponse(code=candidate.strip(), reasoning=reasoning)

    # Last resort
    return CleanedResponse(code=text.strip(), reasoning=reasoning)

"""Syntax validation utilities for LLM-generated code."""

from __future__ import annotations

import ast
import json


def validate_python(code: str) -> tuple[bool, str | None]:
    """Check that *code* is syntactically valid Python.

    Returns ``(True, None)`` on success or ``(False, error_message)`` on failure.
    """
    try:
        ast.parse(code)
    except SyntaxError as exc:
        location = f"line {exc.lineno}" if exc.lineno else "unknown location"
        return False, f"{location}: {exc.msg}"
    return True, None


# Keywords that must appear in valid Lean 4 source
_LEAN_KEYWORDS = frozenset(
    {
        "import",
        "theorem",
        "lemma",
        "def",
        "open",
        "namespace",
        "section",
        "variable",
        "noncomputable",
        "instance",
        "structure",
        "class",
        "inductive",
        "example",
        "sorry",
    }
)

# Prose indicators — if the first non-blank line starts with these,
# the LLM returned natural language instead of code.
_PROSE_STARTERS = (
    "`",
    '"',
    "Here",
    "I ",
    "The ",
    "This ",
    "Let ",
    "Sure",
    "Certainly",
    "Of course",
    "It ",
    "We ",
    "Note",
    "Would",
)


def validate_lean(code: str) -> tuple[bool, str | None]:
    """Basic sanity check that *code* looks like Lean 4, not prose.

    This is intentionally lightweight — Lean itself does the real validation.
    We just want to catch obvious cases where the LLM returned conversation
    instead of code.
    """
    stripped = code.strip()
    if not stripped:
        return False, "Empty code"

    # Check first non-blank line isn't prose
    first_line = ""
    for line in stripped.splitlines():
        if line.strip():
            first_line = line.strip()
            break

    if first_line and first_line.startswith(_PROSE_STARTERS):
        return False, f"First line looks like prose, not Lean: {first_line[:80]}"

    # Check that at least one Lean keyword exists
    words = set(stripped.split())
    if not words & _LEAN_KEYWORDS:
        return False, "No Lean keywords found (import, theorem, lemma, def, etc.)"

    return True, None


def validate_json(text: str) -> tuple[bool, str | None]:
    """Check that *text* is valid JSON.

    Returns ``(True, None)`` on success or ``(False, error_message)`` on failure.
    """
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        return False, str(exc)
    return True, None

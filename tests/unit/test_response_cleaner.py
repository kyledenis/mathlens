"""Tests for the universal LLM response cleaner."""

import pytest

from mathlens.pipeline.response_cleaner import (
    clean_code_response,
    clean_json_response,
    extract_fenced_code,
    extract_thinking,
    find_code_anchor,
    strip_artifacts,
)


# ---------------------------------------------------------------------------
# extract_thinking
# ---------------------------------------------------------------------------


class TestExtractThinking:
    def test_all_tag_formats(self):
        for tag_open, tag_close in [
            ("<think>", "</think>"),
            ("<thinking>", "</thinking>"),
            ("<reasoning>", "</reasoning>"),
            ("<reflection>", "</reflection>"),
            ("<|thinking|>", "<|/thinking|>"),
        ]:
            raw = f"{tag_open}Some reasoning{tag_close}\nfrom manim import *"
            reasoning, remaining = extract_thinking(raw)
            assert "Some reasoning" in reasoning, f"Failed for {tag_open}"
            assert "from manim import *" in remaining

    def test_multiple_thinking_blocks(self):
        raw = (
            "<think>First thought</think>\n"
            "some code\n"
            "<think>Second thought</think>\n"
            "more code"
        )
        reasoning, remaining = extract_thinking(raw)
        assert "First thought" in reasoning
        assert "Second thought" in reasoning
        assert "some code" in remaining

    def test_no_thinking_traces(self):
        raw = "from manim import *\nclass Foo(Scene): pass"
        reasoning, remaining = extract_thinking(raw)
        assert reasoning == ""
        assert remaining == raw


# ---------------------------------------------------------------------------
# strip_artifacts
# ---------------------------------------------------------------------------


class TestStripArtifacts:
    def test_insight_block(self):
        raw = (
            "`★ Insight ─────────────────────────────────────`\n"
            "Some educational content here\n"
            "`─────────────────────────────────────────────────`\n"
            "from manim import *"
        )
        result = strip_artifacts(raw)
        assert "★" not in result
        assert "from manim import *" in result

    def test_conversational_preamble_stripped(self):
        for preamble in [
            "Here's the code:\n\n",
            "I'll generate the Manim code now.\n\n",
            "Certainly! Let me create that for you.\n\n",
        ]:
            raw = preamble + "from manim import *"
            result = strip_artifacts(raw)
            assert preamble.strip() not in result, f"Failed for: {preamble.strip()}"

    def test_no_artifacts(self):
        raw = "from manim import *\nclass Foo(Scene): pass"
        result = strip_artifacts(raw)
        assert result == raw


# ---------------------------------------------------------------------------
# extract_fenced_code
# ---------------------------------------------------------------------------


class TestExtractFencedCode:
    def test_language_fences(self):
        for lang_tag, lang_hint, code in [
            ("python", "python", "from manim import *"),
            ("py", "python", "print('hello')"),
            ("lean", "lean", "import Mathlib"),
            ("lean4", "lean", "import Mathlib"),
            ("json", "json", '{"key": "value"}'),
        ]:
            text = f"```{lang_tag}\n{code}\n```"
            assert extract_fenced_code(text, lang_hint) == code, f"Failed for {lang_tag}"

    def test_generic_fence_fallback(self):
        assert extract_fenced_code("```\ncode\n```", "python") == "code"

    def test_no_fence_returns_none(self):
        assert extract_fenced_code("from manim import *", "python") is None

    def test_multiple_fences_takes_first(self):
        text = "```python\nfirst_code\n```\ntext\n```python\nsecond_code\n```"
        assert extract_fenced_code(text, "python") == "first_code"


# ---------------------------------------------------------------------------
# find_code_anchor
# ---------------------------------------------------------------------------


class TestFindCodeAnchor:
    def test_finds_anchors(self):
        for lang, snippet, expected_start in [
            ("python", "Some text\nfrom manim import *", "from manim"),
            ("python", "Some text\nclass MyScene(Scene):", "class MyScene"),
            ("lean", "Some text\nimport Mathlib", "import Mathlib"),
            ("lean", "Some text\ntheorem euler : True := trivial", "theorem euler"),
        ]:
            idx = find_code_anchor(snippet, lang)
            assert idx is not None, f"No anchor for {lang}: {snippet}"
            assert snippet[idx:].startswith(expected_start)

    def test_no_anchor(self):
        assert find_code_anchor("Just some plain text", "python") is None
        assert find_code_anchor("anything", "rust") is None


# ---------------------------------------------------------------------------
# clean_code_response (integration)
# ---------------------------------------------------------------------------


class TestCleanCodeResponse:
    def test_thinking_plus_fenced_python(self):
        raw = (
            "<think>\nI should use ComplexPlane for this.\n</think>\n\n"
            "```python\n"
            "from manim import *\n\n"
            "class EulerScene(Scene):\n"
            "    def construct(self):\n"
            "        pass\n"
            "```"
        )
        result = clean_code_response(raw, "python")
        assert result.code.startswith("from manim import *")
        assert "EulerScene" in result.code
        assert "ComplexPlane" in result.reasoning
        assert "<think>" not in result.code
        assert "```" not in result.code

    def test_unfenced_with_anchor(self):
        raw = (
            "Here is the Lean proof:\n\n"
            "import Mathlib\n\n"
            "theorem foo : True := trivial"
        )
        result = clean_code_response(raw, "lean")
        assert result.code.startswith("import Mathlib")

    def test_empty_input(self):
        result = clean_code_response("", "python")
        assert result.code == ""

    def test_real_contaminated_scene(self):
        """Simulates the actual failure from the user's Euler identity exploration."""
        raw = (
            "It seems the write permission is being blocked. "
            "Let me try an alternative approach.\n\n"
            "`★ Insight ─────────────────────────────────────`\n"
            "ValueTracker + always_redraw is the standard pattern.\n"
            "`─────────────────────────────────────────────────`\n\n"
            "```python\n"
            "from manim import *\n"
            "import numpy as np\n\n"
            "class Scene1ComplexPlane(Scene):\n"
            "    def construct(self):\n"
            "        plane = ComplexPlane()\n"
            "        self.play(Create(plane))\n"
            "```\n\n"
            "Would you like me to try writing the file again?"
        )
        result = clean_code_response(raw, "python")
        assert result.code.startswith("from manim import *")
        assert "Scene1ComplexPlane" in result.code
        assert "write permission" not in result.code
        assert "★" not in result.code
        assert "Would you like" not in result.code

    def test_real_contaminated_proof(self):
        """Simulates the actual failure from the user's Euler identity proof."""
        raw = (
            "`★ Insight ─────────────────────────────────────`\n"
            "Mathlib already provides the heavy lifting here.\n"
            "`─────────────────────────────────────────────────`\n\n"
            "import Mathlib\n\n"
            "open Complex Real\n\n"
            "theorem euler_formula (θ : ℝ) :\n"
            "    exp (↑θ * I) = ↑(cos θ) + ↑(sin θ) * I :=\n"
            "  exp_mul_I θ"
        )
        result = clean_code_response(raw, "lean")
        assert result.code.startswith("import Mathlib")
        assert "euler_formula" in result.code
        assert "★" not in result.code


# ---------------------------------------------------------------------------
# clean_json_response (integration)
# ---------------------------------------------------------------------------


class TestCleanJsonResponse:
    def test_fenced_json(self):
        raw = '```json\n{"topic": "euler"}\n```'
        result = clean_json_response(raw)
        assert result.code == '{"topic": "euler"}'

    def test_thinking_plus_json(self):
        raw = (
            "<think>I need to structure this as a plan</think>\n\n"
            '{"topic": "euler", "intent": "prove"}'
        )
        result = clean_json_response(raw)
        assert '"euler"' in result.code
        assert "structure this" in result.reasoning

    def test_empty_input(self):
        result = clean_json_response("")
        assert result.code == ""

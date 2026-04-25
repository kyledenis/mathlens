"""Tests for syntax validation utilities."""

import pytest

from mathlens.pipeline.validation import validate_json, validate_lean, validate_python


class TestValidatePython:
    def test_valid_manim_code(self):
        code = (
            "from manim import *\n\n"
            "class MyScene(Scene):\n"
            "    def construct(self):\n"
            "        circle = Circle()\n"
            "        self.play(Create(circle))\n"
        )
        valid, error = validate_python(code)
        assert valid is True
        assert error is None

    def test_syntax_error(self):
        valid, error = validate_python("def foo(\n")
        assert valid is False
        assert error is not None
        assert "line" in error.lower()


class TestValidateLean:
    def test_valid_lean_with_import(self):
        code = "import Mathlib\n\ntheorem foo : True := trivial"
        valid, error = validate_lean(code)
        assert valid is True
        assert error is None

    def test_prose_rejected(self):
        for code in [
            "The theorem states that for any real number x...",
            "`★ Insight\nSome text",
            "Here is the Lean proof:\nimport Mathlib",
        ]:
            valid, error = validate_lean(code)
            assert valid is False, f"Should reject: {code[:40]}"

    def test_empty_rejected(self):
        valid, error = validate_lean("")
        assert valid is False


class TestValidateJson:
    def test_valid_json(self):
        valid, error = validate_json('{"key": "value"}')
        assert valid is True
        assert error is None

    def test_invalid_json(self):
        for bad_input in ["{key: value}", "", "This is not JSON"]:
            valid, error = validate_json(bad_input)
            assert valid is False, f"Should reject: {bad_input}"

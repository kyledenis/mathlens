"""Tests for mathlens.ui.errors human-readable error formatting."""

import pytest

from mathlens.ui.errors import format_error, format_refuted_error


class TestFormatError:
    def test_error_without_hint(self):
        result = format_error("Something went wrong")
        assert "Something went wrong" in result
        assert "Hint" not in result

    def test_error_with_hint(self):
        result = format_error("Something went wrong", hint="Try again later")
        assert "Try again later" in result
        assert "Hint" in result


class TestFormatRefutedError:
    def test_refuted_error_content(self):
        result = format_refuted_error("The sum is wrong", "lean error details")
        assert "refuted" in result.lower()
        assert "The sum is wrong" in result
        assert "lean error details" in result

    def test_lean_output_truncated_at_300(self):
        long_output = "x" * 500
        result = format_refuted_error("Bad proof", long_output)
        assert "x" * 300 in result
        assert "x" * 301 not in result

    def test_empty_lean_output_skips_section(self):
        result = format_refuted_error("Bad proof", "")
        assert "Lean output" not in result

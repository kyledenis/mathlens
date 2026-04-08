"""Tests for mathlens.ui.errors human-readable error formatting."""

import pytest

from mathlens.ui.errors import format_error, format_refuted_error


class TestFormatError:
    def test_basic_error_message(self):
        result = format_error("Something went wrong")
        assert "Something went wrong" in result

    def test_error_markup_present(self):
        result = format_error("Something went wrong")
        assert "Error:" in result
        assert "red" in result

    def test_no_hint_when_omitted(self):
        result = format_error("Something went wrong")
        assert "Hint" not in result

    def test_hint_included_when_provided(self):
        result = format_error("Something went wrong", hint="Try again later")
        assert "Try again later" in result
        assert "Hint" in result

    def test_hint_markup_dim(self):
        result = format_error("Something went wrong", hint="Try again later")
        assert "dim" in result

    def test_hint_none_explicit(self):
        result = format_error("An error occurred", hint=None)
        assert "Hint" not in result

    def test_message_and_hint_separated_by_newline(self):
        result = format_error("msg", hint="h")
        assert "\n" in result


class TestFormatRefutedError:
    def test_contains_refuted(self):
        result = format_refuted_error("The sum is wrong", "lean error details")
        assert "refuted" in result.lower()

    def test_contains_failure_reason(self):
        result = format_refuted_error("The sum is wrong", "lean error details")
        assert "The sum is wrong" in result

    def test_contains_mathematically_incorrect(self):
        result = format_refuted_error("Bad proof", "lean output here")
        assert "mathematically incorrect" in result

    def test_lean_output_included(self):
        result = format_refuted_error("Bad proof", "lean says no")
        assert "lean says no" in result

    def test_lean_output_truncated_at_300(self):
        long_output = "x" * 500
        result = format_refuted_error("Bad proof", long_output)
        assert "x" * 300 in result
        assert "x" * 301 not in result

    def test_empty_lean_output_skips_section(self):
        result = format_refuted_error("Bad proof", "")
        assert "Lean output" not in result

    def test_contains_halt_message(self):
        result = format_refuted_error("Bad proof", "lean output")
        assert "halted" in result

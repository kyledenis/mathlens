"""Tests for mathlens.ui.console helpers."""

import pytest

from mathlens.ui.console import format_duration


class TestFormatDuration:
    def test_format_duration(self):
        assert format_duration(0.5) == "0.5s"
        assert format_duration(5.0) == "5.0s"
        assert format_duration(60.0) == "1m 0s"
        assert format_duration(90.0) == "1m 30s"
        assert format_duration(125.0) == "2m 5s"

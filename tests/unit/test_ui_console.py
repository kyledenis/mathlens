"""Tests for mathlens.ui.console helpers."""

import pytest

from mathlens.models import Badge
from mathlens.ui.console import format_badge, format_duration, format_topic_header


class TestFormatBadge:
    def test_verified_badge(self):
        result = format_badge(Badge.verified)
        assert "Verified" in result
        assert "green" in result

    def test_unverified_badge(self):
        result = format_badge(Badge.unverified)
        assert "Unverified" in result
        assert "yellow" in result

    def test_refuted_badge(self):
        result = format_badge(Badge.refuted)
        assert "Refuted" in result
        assert "red" in result

    def test_unchecked_badge(self):
        result = format_badge(Badge.unchecked)
        assert "Unchecked" in result
        assert "dim" in result

    def test_returns_icon_property(self):
        for badge in Badge:
            assert format_badge(badge) == badge.icon


class TestFormatDuration:
    def test_seconds_only(self):
        assert format_duration(5.0) == "5.0s"

    def test_sub_second(self):
        assert format_duration(0.5) == "0.5s"

    def test_just_under_minute(self):
        assert format_duration(59.9) == "59.9s"

    def test_exactly_one_minute(self):
        result = format_duration(60.0)
        assert result == "1m 0s"

    def test_minutes_and_seconds(self):
        result = format_duration(90.0)
        assert result == "1m 30s"

    def test_multiple_minutes(self):
        result = format_duration(125.0)
        assert result == "2m 5s"


class TestFormatTopicHeader:
    def test_slug_to_title(self):
        result = format_topic_header("pythagorean-theorem")
        assert "Pythagorean Theorem" in result

    def test_bold_markup(self):
        result = format_topic_header("pythagorean-theorem")
        assert "[bold]" in result
        assert "[/bold]" in result

    def test_single_word(self):
        result = format_topic_header("calculus")
        assert "Calculus" in result

    def test_multiple_hyphens(self):
        result = format_topic_header("fourier-series-convergence")
        assert "Fourier Series Convergence" in result

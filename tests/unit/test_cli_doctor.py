"""Unit tests for the mathlens doctor command."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mathlens.cli.app import app

runner = CliRunner()


class TestDoctorCommand:
    def test_doctor_runs(self):
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0

    def test_doctor_accepts_fix_flag(self):
        result = runner.invoke(app, ["doctor", "--fix"])
        assert result.exit_code == 0

    def test_doctor_shows_summary_all_ok(self):
        """When all checks pass the summary says so."""
        with patch("mathlens.cli.doctor._check_python") as mp, \
             patch("mathlens.cli.doctor._check_lean") as ml, \
             patch("mathlens.cli.doctor._check_manim") as mm, \
             patch("mathlens.cli.doctor._check_ffmpeg") as mf, \
             patch("mathlens.cli.doctor._check_latex") as mlt, \
             patch("mathlens.cli.doctor._check_mathlib") as mmlib, \
             patch("mathlens.cli.doctor._check_claude") as mc, \
             patch("mathlens.cli.doctor._check_ollama") as mo:
            from mathlens.cli.doctor import _Check
            for mock, name in [
                (mp, "Python"), (ml, "Lean 4"), (mm, "Manim CE"),
                (mf, "ffmpeg"), (mlt, "LaTeX"), (mmlib, "Mathlib"),
                (mc, "claude (CLI)"), (mo, "ollama"),
            ]:
                mock.return_value = _Check(name, True, "/usr/bin/" + name.lower())
            result = runner.invoke(app, ["doctor"])
        assert "All checks passed" in result.output

    def test_doctor_shows_summary_some_missing(self):
        """When a check fails the summary mentions missing dependencies."""
        with patch("mathlens.cli.doctor._check_lean") as ml:
            from mathlens.cli.doctor import _Check
            ml.return_value = _Check("Lean 4", False, "not found")
            result = runner.invoke(app, ["doctor"])
        assert "missing" in result.output.lower()

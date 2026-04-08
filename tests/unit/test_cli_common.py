"""Unit tests for mathlens.cli.common — flag overrides and pipeline builder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mathlens.cli.common import apply_flag_overrides, build_pipeline
from mathlens.config.settings import MathLensSettings
from mathlens.pipeline.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# apply_flag_overrides
# ---------------------------------------------------------------------------


class TestApplyFlagOverrides:
    def test_no_overrides_leaves_defaults(self):
        settings = MathLensSettings()
        defaults = MathLensSettings()
        apply_flag_overrides(settings)
        assert settings.provider.default == defaults.provider.default
        assert settings.provider.api.model == defaults.provider.api.model
        assert settings.render.default_format == defaults.render.default_format
        assert settings.render.default_quality == defaults.render.default_quality
        assert settings.verification.always_attempt == defaults.verification.always_attempt
        assert settings.ui.open_video_on_complete == defaults.ui.open_video_on_complete
        assert settings.ui.show_proof_excerpt == defaults.ui.show_proof_excerpt

    def test_provider_override(self):
        settings = MathLensSettings()
        apply_flag_overrides(settings, provider="cli")
        assert settings.provider.default == "cli"

    def test_local_shorthand(self):
        settings = MathLensSettings()
        apply_flag_overrides(settings, local=True)
        assert settings.provider.default == "local"

    def test_provider_overrides_local(self):
        """Explicit provider wins when both local and provider are given."""
        settings = MathLensSettings()
        apply_flag_overrides(settings, local=True, provider="cli")
        assert settings.provider.default == "cli"

    def test_model_override(self):
        settings = MathLensSettings()
        apply_flag_overrides(settings, model="claude-opus-4")
        assert settings.provider.api.model == "claude-opus-4"

    def test_format_override(self):
        settings = MathLensSettings()
        apply_flag_overrides(settings, format="frames")
        assert settings.render.default_format == "frames"

    def test_quality_override(self):
        settings = MathLensSettings()
        apply_flag_overrides(settings, quality="high")
        assert settings.render.default_quality == "high"

    def test_verify_timeout_sets_both(self):
        settings = MathLensSettings()
        apply_flag_overrides(settings, verify_timeout=120)
        assert settings.verification.explore_timeout == 120
        assert settings.verification.deep_timeout == 120

    def test_no_verify(self):
        settings = MathLensSettings()
        assert settings.verification.always_attempt is True
        apply_flag_overrides(settings, no_verify=True)
        assert settings.verification.always_attempt is False

    def test_no_open(self):
        settings = MathLensSettings()
        assert settings.ui.open_video_on_complete is True
        apply_flag_overrides(settings, no_open=True)
        assert settings.ui.open_video_on_complete is False

    def test_quiet(self):
        settings = MathLensSettings()
        assert settings.ui.show_proof_excerpt is True
        apply_flag_overrides(settings, quiet=True)
        assert settings.ui.show_proof_excerpt is False

    def test_mutates_in_place(self):
        settings = MathLensSettings()
        result = apply_flag_overrides(settings, provider="local")
        assert result is None
        assert settings.provider.default == "local"


# ---------------------------------------------------------------------------
# build_pipeline
# ---------------------------------------------------------------------------


class TestBuildPipeline:
    def _make_mock_provider(self):
        return AsyncMock()

    def test_returns_orchestrator(self, tmp_path):
        settings = MathLensSettings()
        settings.workspace.path = str(tmp_path)

        mock_provider = self._make_mock_provider()
        mock_providers = {"local": mock_provider}
        mock_router = MagicMock()

        with patch(
            "mathlens.cli.common.build_providers", return_value=mock_providers
        ) as mock_build_providers, patch(
            "mathlens.cli.common.build_router", return_value=mock_router
        ) as mock_build_router:
            result = build_pipeline(settings)

        assert isinstance(result, Orchestrator)
        mock_build_providers.assert_called_once_with(settings)
        mock_build_router.assert_called_once_with(settings, mock_providers)

    def test_falls_back_to_first_provider_when_default_missing(self, tmp_path):
        settings = MathLensSettings()
        settings.workspace.path = str(tmp_path)
        settings.provider.default = "api"  # not in providers dict

        mock_provider = self._make_mock_provider()
        mock_providers = {"local": mock_provider}
        mock_router = MagicMock()

        with patch("mathlens.cli.common.build_providers", return_value=mock_providers), patch(
            "mathlens.cli.common.build_router", return_value=mock_router
        ):
            result = build_pipeline(settings)

        assert isinstance(result, Orchestrator)

    def test_uses_named_default_provider(self, tmp_path):
        settings = MathLensSettings()
        settings.workspace.path = str(tmp_path)
        settings.provider.default = "local"

        mock_local = self._make_mock_provider()
        mock_api = self._make_mock_provider()
        mock_providers = {"local": mock_local, "api": mock_api}
        mock_router = MagicMock()

        with patch("mathlens.cli.common.build_providers", return_value=mock_providers), patch(
            "mathlens.cli.common.build_router", return_value=mock_router
        ):
            result = build_pipeline(settings)

        assert isinstance(result, Orchestrator)

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

    def test_verify_timeout_sets_both(self):
        settings = MathLensSettings()
        apply_flag_overrides(settings, verify_timeout=120)
        assert settings.verification.explore_timeout == 120
        assert settings.verification.deep_timeout == 120

    def test_boolean_flags(self):
        settings = MathLensSettings()
        apply_flag_overrides(settings, no_verify=True, no_open=True, quiet=True)
        assert settings.verification.always_attempt is False
        assert settings.ui.open_video_on_complete is False
        assert settings.ui.show_proof_excerpt is False


# ---------------------------------------------------------------------------
# build_pipeline
# ---------------------------------------------------------------------------


class TestBuildPipeline:
    def _make_mock_provider(self):
        return AsyncMock()

    def test_returns_orchestrator_and_provider_name(self, tmp_path):
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
            # Default is "api" but only "local" is available — should fallback
            result, provider_name = build_pipeline(settings)

        assert isinstance(result, Orchestrator)
        assert provider_name == "local"
        mock_build_providers.assert_called_once_with(settings)
        mock_build_router.assert_called_once_with(settings, mock_providers)

    def test_uses_configured_default_when_available(self, tmp_path):
        settings = MathLensSettings()
        settings.workspace.path = str(tmp_path)
        settings.provider.default = "cli"

        mock_provider = self._make_mock_provider()
        mock_providers = {"cli": mock_provider, "local": mock_provider}
        mock_router = MagicMock()

        with patch("mathlens.cli.common.build_providers", return_value=mock_providers), patch(
            "mathlens.cli.common.build_router", return_value=mock_router
        ):
            result, provider_name = build_pipeline(settings)

        assert isinstance(result, Orchestrator)
        assert provider_name == "cli"

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
            result, provider_name = build_pipeline(settings)

        assert isinstance(result, Orchestrator)
        assert provider_name == "local"

    def test_raises_when_no_providers(self, tmp_path):
        settings = MathLensSettings()
        settings.workspace.path = str(tmp_path)

        mock_router = MagicMock()

        with patch("mathlens.cli.common.build_providers", return_value={}), patch(
            "mathlens.cli.common.build_router", return_value=mock_router
        ):
            with pytest.raises(RuntimeError, match="No LLM provider available"):
                build_pipeline(settings)


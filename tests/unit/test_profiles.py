"""Unit tests for ProfileManager."""

import pytest
from pathlib import Path

from mathlens.config import MathLensSettings
from mathlens.config.profiles import ProfileManager


class TestPersonalProfile:
    def test_sets_provider_default_to_cli(self, tmp_path):
        pm = ProfileManager(tmp_path / "config.toml")
        s = MathLensSettings()
        pm.apply("personal", s)
        assert s.provider.default == "cli"

    def test_sets_cli_backend(self, tmp_path):
        pm = ProfileManager(tmp_path / "config.toml")
        s = MathLensSettings()
        pm.apply("personal", s)
        assert s.provider.cli.backend == "claude-code"

    def test_sets_fallback_chain(self, tmp_path):
        pm = ProfileManager(tmp_path / "config.toml")
        s = MathLensSettings()
        pm.apply("personal", s)
        assert s.provider.fallback_chain == ["cli", "api", "local"]


class TestPublishProfile:
    def test_sets_provider_default_to_api(self, tmp_path):
        pm = ProfileManager(tmp_path / "config.toml")
        s = MathLensSettings()
        pm.apply("publish", s)
        assert s.provider.default == "api"

    def test_sets_fallback_chain(self, tmp_path):
        pm = ProfileManager(tmp_path / "config.toml")
        s = MathLensSettings()
        pm.apply("publish", s)
        assert s.provider.fallback_chain == ["api", "cli", "local"]


class TestUnknownProfile:
    def test_raises_key_error(self, tmp_path):
        pm = ProfileManager(tmp_path / "config.toml")
        s = MathLensSettings()
        with pytest.raises(KeyError, match="Unknown profile"):
            pm.apply("nonexistent", s)


class TestListProfiles:
    def test_returns_both_profiles(self, tmp_path):
        pm = ProfileManager(tmp_path / "config.toml")
        profiles = pm.list_profiles()
        assert "personal" in profiles
        assert "publish" in profiles

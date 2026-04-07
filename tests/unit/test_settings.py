"""Unit tests for MathLensSettings configuration."""

import pytest
import tempfile
import tomli_w
from pathlib import Path

from mathlens.config import MathLensSettings


# ---------------------------------------------------------------------------
# TestDefaults
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_provider_default_is_api(self):
        s = MathLensSettings()
        assert s.provider.default == "api"

    def test_fallback_chain(self):
        s = MathLensSettings()
        assert s.provider.fallback_chain == ["api", "cli", "local"]

    def test_render_quality_defaults(self):
        s = MathLensSettings()
        assert s.render.default_quality == "medium"
        assert s.render.deep_quality == "production"
        assert s.render.default_format == "video"

    def test_workspace_path_contains_mathlens(self):
        s = MathLensSettings()
        assert "mathlens" in s.workspace.path

    def test_verification_defaults(self):
        s = MathLensSettings()
        assert s.verification.always_attempt is True
        assert s.verification.allow_unverified_viz is True
        assert s.verification.explore_timeout == 60
        assert s.verification.deep_timeout == 300

    def test_cli_provider_defaults(self):
        s = MathLensSettings()
        assert s.provider.cli.backend == "claude-code"
        assert s.provider.cli.timeout == 120

    def test_api_provider_defaults(self):
        s = MathLensSettings()
        assert s.provider.api.model == "claude-sonnet-4-6"

    def test_local_provider_defaults(self):
        s = MathLensSettings()
        assert s.provider.local.backend == "ollama"
        assert s.provider.local.model == "qwen3:32b"
        assert s.provider.local.endpoint == "http://localhost:11434"

    def test_ui_defaults(self):
        s = MathLensSettings()
        assert s.ui.theme == "auto"
        assert s.ui.open_video_on_complete is True
        assert s.ui.show_proof_excerpt is True


# ---------------------------------------------------------------------------
# TestLoadFromToml
# ---------------------------------------------------------------------------

class TestLoadFromToml:
    def test_load_with_overrides(self, tmp_path):
        toml_file = tmp_path / "config.toml"
        data = {"provider": {"default": "cli"}}
        with toml_file.open("wb") as f:
            tomli_w.dump(data, f)
        s = MathLensSettings.from_toml(toml_file)
        assert s.provider.default == "cli"
        # Non-overridden value keeps default
        assert s.render.default_quality == "medium"

    def test_load_missing_file_returns_defaults(self, tmp_path):
        missing = tmp_path / "nonexistent.toml"
        s = MathLensSettings.from_toml(missing)
        assert s.provider.default == "api"

    def test_load_deeply_nested_override(self, tmp_path):
        toml_file = tmp_path / "config.toml"
        data = {"provider": {"cli": {"backend": "custom-backend"}}}
        with toml_file.open("wb") as f:
            tomli_w.dump(data, f)
        s = MathLensSettings.from_toml(toml_file)
        assert s.provider.cli.backend == "custom-backend"
        # Other cli defaults preserved
        assert s.provider.cli.timeout == 120


# ---------------------------------------------------------------------------
# TestSaveToToml
# ---------------------------------------------------------------------------

class TestSaveToToml:
    def test_roundtrip(self, tmp_path):
        s = MathLensSettings()
        s.provider.default = "cli"
        toml_file = tmp_path / "config.toml"
        s.save_toml(toml_file)
        s2 = MathLensSettings.from_toml(toml_file)
        assert s2.provider.default == "cli"
        assert s2.render.default_quality == "medium"

    def test_save_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "config.toml"
        s = MathLensSettings()
        s.save_toml(nested)
        assert nested.exists()


# ---------------------------------------------------------------------------
# TestSetByDotPath
# ---------------------------------------------------------------------------

class TestSetByDotPath:
    def test_set_top_level_nested(self):
        s = MathLensSettings()
        s.set("provider.default", "local")
        assert s.provider.default == "local"

    def test_set_deeply_nested(self):
        s = MathLensSettings()
        s.set("provider.cli.timeout", 60)
        assert s.provider.cli.timeout == 60

    def test_set_invalid_path_raises_key_error(self):
        s = MathLensSettings()
        with pytest.raises(KeyError):
            s.set("provider.nonexistent_field", "value")

    def test_set_invalid_top_level_raises_key_error(self):
        s = MathLensSettings()
        with pytest.raises(KeyError):
            s.set("nonexistent.field", "value")


# ---------------------------------------------------------------------------
# TestGet
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_nested(self):
        s = MathLensSettings()
        assert s.get("provider.default") == "api"

    def test_get_deeply_nested(self):
        s = MathLensSettings()
        assert s.get("provider.cli.backend") == "claude-code"


# ---------------------------------------------------------------------------
# TestDiff
# ---------------------------------------------------------------------------

class TestDiff:
    def test_no_diff_on_fresh_defaults(self):
        s = MathLensSettings()
        assert s.diff() == {}

    def test_diff_shows_changes(self):
        s = MathLensSettings()
        s.set("provider.default", "cli")
        d = s.diff()
        assert "provider.default" in d
        assert d["provider.default"]["default"] == "api"
        assert d["provider.default"]["current"] == "cli"

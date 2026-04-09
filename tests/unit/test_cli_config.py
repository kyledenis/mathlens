"""Tests for mathlens config CLI subcommands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mathlens.cli.app import app
from mathlens.config.settings import MathLensSettings

runner = CliRunner()


# ---------------------------------------------------------------------------
# config show
# ---------------------------------------------------------------------------

def test_config_show_contains_provider(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    result = runner.invoke(app, ["config", "show", "--config-path", str(cfg)])
    assert result.exit_code == 0, result.output
    assert "Provider" in result.output


# ---------------------------------------------------------------------------
# config set
# ---------------------------------------------------------------------------

def test_config_set_exits_zero(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    result = runner.invoke(app, ["config", "set", "provider.default", "cli", "--config-path", str(cfg)])
    assert result.exit_code == 0, result.output

    # Verify persisted
    settings = MathLensSettings.from_toml(cfg)
    assert settings.provider.default == "cli"


def test_config_set_invalid_key_exits_nonzero(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    result = runner.invoke(app, ["config", "set", "does.not.exist", "value", "--config-path", str(cfg)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# config diff
# ---------------------------------------------------------------------------

def test_config_diff_no_changes(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    # Save defaults explicitly
    MathLensSettings().save_toml(cfg)
    result = runner.invoke(app, ["config", "diff", "--config-path", str(cfg)])
    assert result.exit_code == 0, result.output
    assert "No changes from defaults" in result.output


def test_config_diff_shows_change(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    settings = MathLensSettings()
    settings.provider.default = "local"
    settings.save_toml(cfg)
    result = runner.invoke(app, ["config", "diff", "--config-path", str(cfg)])
    assert result.exit_code == 0, result.output
    assert "provider.default" in result.output


# ---------------------------------------------------------------------------
# config reset
# ---------------------------------------------------------------------------

def test_config_reset_with_yes(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    # Write a non-default value first
    settings = MathLensSettings()
    settings.provider.default = "local"
    settings.save_toml(cfg)

    result = runner.invoke(app, ["config", "reset", "--yes", "--config-path", str(cfg)])
    assert result.exit_code == 0, result.output

    # Confirm restored to defaults
    restored = MathLensSettings.from_toml(cfg)
    assert restored.provider.default == MathLensSettings().provider.default


# ---------------------------------------------------------------------------
# config profile
# ---------------------------------------------------------------------------

def test_config_profile_personal(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    result = runner.invoke(app, ["config", "profile", "personal", "--config-path", str(cfg)])
    assert result.exit_code == 0, result.output

    settings = MathLensSettings.from_toml(cfg)
    assert settings.provider.default == "cli"


def test_config_profile_nonexistent_exits_nonzero(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    result = runner.invoke(app, ["config", "profile", "nonexistent", "--config-path", str(cfg)])
    assert result.exit_code != 0

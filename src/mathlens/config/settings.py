"""MathLens configuration settings with TOML persistence and dot-path access."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import tomli_w
from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Nested settings models
# ---------------------------------------------------------------------------

class CLIProviderSettings(BaseModel):
    backend: str = "claude-code"
    timeout: int = 1800  # 30 min — only catches runaway processes, never normal use


class APIProviderSettings(BaseModel):
    model: str = "claude-sonnet-4-6"


class LocalProviderSettings(BaseModel):
    backend: str = "ollama"
    model: str = "qwen3:32b"
    endpoint: str = "http://localhost:11434"


class ProviderSettings(BaseModel):
    default: str = "api"
    fallback_chain: list[str] = Field(default_factory=lambda: ["api", "cli", "local"])
    cli: CLIProviderSettings = Field(default_factory=CLIProviderSettings)
    api: APIProviderSettings = Field(default_factory=APIProviderSettings)
    local: LocalProviderSettings = Field(default_factory=LocalProviderSettings)


class RenderSettings(BaseModel):
    default_quality: str = "medium"
    deep_quality: str = "production"
    default_format: str = "video"


class VerificationSettings(BaseModel):
    always_attempt: bool = True
    allow_unverified_viz: bool = True
    explore_timeout: int = 60    # 1 min — explore is for quick understanding
    deep_timeout: int = 300     # 5 min — complex proofs with full rigour


class WorkspaceSettings(BaseModel):
    path: str = str(Path.home() / ".local" / "share" / "mathlens" / "explorations")


class UISettings(BaseModel):
    theme: str = "auto"
    open_video_on_complete: bool = True
    show_proof_excerpt: bool = True


# ---------------------------------------------------------------------------
# Root settings model
# ---------------------------------------------------------------------------

class MathLensSettings(BaseModel):
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    render: RenderSettings = Field(default_factory=RenderSettings)
    verification: VerificationSettings = Field(default_factory=VerificationSettings)
    workspace: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    ui: UISettings = Field(default_factory=UISettings)

    model_config = {"arbitrary_types_allowed": True}

    # ------------------------------------------------------------------
    # TOML persistence
    # ------------------------------------------------------------------

    @classmethod
    def from_toml(cls, path: Path | str) -> "MathLensSettings":
        """Load settings from a TOML file. Returns defaults if file is missing."""
        path = Path(path)
        if not path.exists():
            return cls()
        with path.open("rb") as f:
            data = tomllib.load(f)
        return cls.model_validate(data)

    def save_toml(self, path: Path | str) -> None:
        """Save settings atomically — write to .tmp then rename."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".toml.tmp")
        data = self.model_dump()
        with tmp.open("wb") as f:
            tomli_w.dump(data, f)
        tmp.rename(path)

    # ------------------------------------------------------------------
    # Dot-path access
    # ------------------------------------------------------------------

    def _resolve_path(self, dot_path: str) -> tuple[Any, str]:
        """Walk dot_path and return (parent_object, final_key).

        Raises KeyError if any segment is invalid.
        """
        parts = dot_path.split(".")
        obj: Any = self
        for part in parts[:-1]:
            if not hasattr(obj, part):
                raise KeyError(f"Invalid settings path: {dot_path!r} (unknown segment {part!r})")
            obj = getattr(obj, part)
        final = parts[-1]
        # Validate the final key exists on the parent
        if not hasattr(obj, final):
            raise KeyError(f"Invalid settings path: {dot_path!r} (unknown segment {final!r})")
        return obj, final

    def set(self, dot_path: str, value: Any) -> None:
        """Set a nested value by dot-separated path.

        Raises KeyError for invalid paths.
        """
        obj, key = self._resolve_path(dot_path)
        setattr(obj, key, value)

    def get(self, dot_path: str) -> Any:
        """Get a nested value by dot-separated path."""
        obj, key = self._resolve_path(dot_path)
        return getattr(obj, key)

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff(self) -> dict[str, dict[str, Any]]:
        """Return dict of values that differ from defaults.

        Format: {"provider.default": {"default": "api", "current": "cli"}}
        """
        defaults = MathLensSettings()
        result: dict[str, dict[str, Any]] = {}
        self._collect_diff(self, defaults, [], result)
        return result

    @staticmethod
    def _collect_diff(
        current: Any,
        default: Any,
        path: list[str],
        result: dict[str, dict[str, Any]],
    ) -> None:
        """Recursively collect differing leaf values."""
        if isinstance(current, BaseModel):
            for field_name in type(current).model_fields:
                MathLensSettings._collect_diff(
                    getattr(current, field_name),
                    getattr(default, field_name),
                    path + [field_name],
                    result,
                )
        else:
            if current != default:
                dot_path = ".".join(path)
                result[dot_path] = {"default": default, "current": current}

"""Named configuration profiles for MathLens."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mathlens.config.settings import MathLensSettings

# Built-in profile definitions: mapping of dot-path -> value
_BUILTIN_PROFILES: dict[str, dict[str, object]] = {
    "personal": {
        "provider.default": "cli",
        "provider.cli.backend": "claude-code",
        "provider.fallback_chain": ["cli", "api", "local"],
    },
    "publish": {
        "provider.default": "api",
        "provider.fallback_chain": ["api", "cli", "local"],
    },
}


class ProfileManager:
    """Manages named configuration profiles."""

    def __init__(self, config_path: Path | str) -> None:
        self._config_path = Path(config_path)

    def apply(self, name: str, settings: "MathLensSettings") -> None:
        """Apply named profile overrides to settings.

        Raises KeyError (with 'Unknown profile' in message) for unknown profiles.
        """
        if name not in _BUILTIN_PROFILES:
            raise KeyError(f"Unknown profile: {name!r}")
        for dot_path, value in _BUILTIN_PROFILES[name].items():
            settings.set(dot_path, value)

    def list_profiles(self) -> list[str]:
        """Return list of available profile names."""
        return list(_BUILTIN_PROFILES.keys())

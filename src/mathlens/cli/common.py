"""Shared CLI flag overrides and pipeline builder for MathLens."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from mathlens.config.settings import MathLensSettings
from mathlens.pipeline.orchestrator import Orchestrator
from mathlens.pipeline.planner import Planner
from mathlens.pipeline.verifier import Verifier
from mathlens.pipeline.visualizer import Visualizer
from mathlens.pipeline.summarizer import Summarizer
from mathlens.providers import build_providers, build_router
from mathlens.workspace.search import SearchIndex
from mathlens.workspace.store import WorkspaceStore


def apply_flag_overrides(
    settings: MathLensSettings,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    local: bool = False,
    format: Optional[str] = None,
    quality: Optional[str] = None,
    verify_timeout: Optional[int] = None,
    no_verify: bool = False,
    no_open: bool = False,
    quiet: bool = False,
) -> None:
    """Mutate *settings* in-place based on CLI flag values."""
    if local:
        settings.provider.default = "local"
    if provider is not None:
        settings.provider.default = provider
    if model is not None:
        settings.provider.api.model = model
    if format is not None:
        settings.render.default_format = format
    if quality is not None:
        settings.render.default_quality = quality
    if verify_timeout is not None:
        settings.verification.explore_timeout = verify_timeout
        settings.verification.deep_timeout = verify_timeout
    if no_verify:
        settings.verification.always_attempt = False
    if no_open:
        settings.ui.open_video_on_complete = False
    if quiet:
        settings.ui.show_proof_excerpt = False


def build_pipeline(settings: MathLensSettings) -> tuple[Orchestrator, str]:
    """Construct a fully-wired Orchestrator from *settings*.

    Returns (orchestrator, provider_name) — provider_name is the detected/selected provider.
    """
    providers = build_providers(settings)
    router = build_router(settings, providers)

    workspace_root = Path(settings.workspace.path).expanduser()
    store = WorkspaceStore(root=workspace_root)
    search_index = SearchIndex(workspace_root / "index.db")

    # Auto-detect: try configured default, then fallback
    default_name = settings.provider.default
    provider = None
    selected_name = default_name

    if default_name in providers:
        provider = providers[default_name]

    if provider is None:
        # Fallback to first available
        for name in ["api", "cli", "local"]:
            if name in providers:
                provider = providers[name]
                selected_name = name
                break

    if provider is None:
        raise RuntimeError("No LLM provider available. Run `mathlens doctor` to check.")

    planner = Planner(provider=provider)
    verifier = Verifier(
        provider=provider,
        workspace_dir=workspace_root,
        explore_timeout=settings.verification.explore_timeout,
        deep_timeout=settings.verification.deep_timeout,
    )
    visualizer = Visualizer(provider=provider, workspace_dir=workspace_root)
    summarizer = Summarizer(provider=provider, workspace_dir=workspace_root)

    return Orchestrator(
        planner=planner,
        verifier=verifier,
        visualizer=visualizer,
        summarizer=summarizer,
        store=store,
        search_index=search_index,
    ), selected_name

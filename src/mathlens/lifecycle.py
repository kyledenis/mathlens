"""Process lifecycle management — graceful shutdown on Ctrl+C.

Tracks active subprocesses and async clients so they can be cleaned up
when the user interrupts with SIGINT (Ctrl+C).
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Any

logger = logging.getLogger(__name__)

# Active subprocesses to kill on shutdown
_active_processes: list[asyncio.subprocess.Process] = []

# Async clients to close on shutdown
_active_clients: list[Any] = []  # httpx.AsyncClient instances


def register_process(proc: asyncio.subprocess.Process) -> None:
    """Track a subprocess so it gets killed on shutdown."""
    _active_processes.append(proc)


def unregister_process(proc: asyncio.subprocess.Process) -> None:
    """Stop tracking a subprocess after it exits normally."""
    try:
        _active_processes.remove(proc)
    except ValueError:
        pass


def register_client(client: Any) -> None:
    """Track an httpx client for cleanup."""
    _active_clients.append(client)


def cleanup() -> None:
    """Kill all tracked subprocesses and close clients.

    Called on SIGINT or at exit. Safe to call multiple times.
    """
    for proc in list(_active_processes):
        try:
            if proc.returncode is None:  # still running
                logger.debug("Killing subprocess PID %s", proc.pid)
                proc.kill()
        except (ProcessLookupError, OSError):
            pass
    _active_processes.clear()

    for client in list(_active_clients):
        try:
            # httpx.AsyncClient — can't await in sync context,
            # but we can close the underlying transport
            if hasattr(client, "_transport"):
                client._transport.close()
        except Exception:
            pass
    _active_clients.clear()


def install_signal_handlers() -> None:
    """Install SIGINT/SIGTERM handlers that call cleanup() then exit."""

    def _handler(signum: int, frame: Any) -> None:
        logger.debug("Received signal %s, cleaning up...", signum)
        cleanup()
        # Re-raise as KeyboardInterrupt so the CLI layer can catch it
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

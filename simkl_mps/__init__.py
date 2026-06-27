"""
Media Player Scrobbler for SIMKL package.
"""

__version__ = "2.7.2"
__author__ = "kavin"

# Apply compatibility patches first, before any other imports
import simkl_mps.compatibility_patches
simkl_mps.compatibility_patches.apply_patches()

from simkl_mps.main import SimklScrobbler, run_as_background_service, main
__all__ = [
    'SimklScrobbler',
    'run_as_background_service',
    'main',
    'run_tray_app',
    # 'run_service' # Removed as it's not defined/imported here
]


def __getattr__(name):
    """Resolve ``run_tray_app`` lazily on first access (PEP 562).

    Importing a tray module pulls in GUI backends (pystray/tkinter/PIL) that
    open a display at import time and fail on headless systems. Deferring the
    import until the runner is actually used keeps ``import simkl_mps`` free of
    GUI dependencies, and routes through the platform dispatcher in
    ``main.get_tray_app`` so the correct per-OS runner is returned.
    """
    if name == "run_tray_app":
        from simkl_mps.main import get_tray_app
        _, run_tray_app = get_tray_app()
        return run_tray_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
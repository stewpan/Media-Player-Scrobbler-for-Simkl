"""
Entry point for launching the correct tray application for the current platform.
"""
import logging
import sys

from simkl_mps.main import get_tray_app
from simkl_mps.process_manager import acquire_instance_lock

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if not acquire_instance_lock():
        print(
            "Another simkl-mps instance is already running. "
            "Use 'simkl-mps exit' to stop it, or 'simkl-mps start' to restart.",
            file=sys.stderr,
        )
        sys.exit(1)
    _, run_tray_app = get_tray_app()
    sys.exit(run_tray_app())

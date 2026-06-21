"""
User Directory Migration Utility

Moves user data into the canonical ``~/.simkl-mps`` directory, migrating from the
older developer-named locations (``~/kavin/simkl-mps`` and the legacy
``~/kavinthangavel/simkl-mps``) automatically and silently on first run.
"""

import logging
import os
import pathlib
import shutil
import platform
from typing import List

logger = logging.getLogger(__name__)

APP_NAME = "simkl-mps"

# Canonical data directory: a single hidden folder in the user's home.
NEW_DIR_NAME = ".simkl-mps"

# Legacy developer-named home subdirectories, newest first. Each held the data
# under an ``APP_NAME`` subfolder (e.g. ``~/kavin/simkl-mps``).
LEGACY_SUBDIRS = ["kavin", "kavinthangavel"]


def get_new_data_dir() -> pathlib.Path:
    """Return the canonical data directory path (``~/.simkl-mps``)."""
    return pathlib.Path.home() / NEW_DIR_NAME


def get_legacy_data_dirs() -> List[pathlib.Path]:
    """Return the legacy data directories to migrate from, newest first."""
    home = pathlib.Path.home()
    return [home / sub / APP_NAME for sub in LEGACY_SUBDIRS]


def migrate_user_directory() -> bool:
    """
    Move user data from a legacy location to ``~/.simkl-mps`` if needed.

    Returns:
        bool: True if migration was performed or not needed, False on failure.
    """
    try:
        new_path = get_new_data_dir()

        # Already migrated.
        if new_path.exists():
            return True

        for old_path in get_legacy_data_dirs():
            if old_path.exists():
                logger.info(f"Migrating user data from {old_path} to {new_path}")
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_path), str(new_path))
                # Remove the now-empty legacy parent (e.g. ``~/kavin``) if possible.
                try:
                    old_path.parent.rmdir()
                except OSError:
                    pass
                logger.info(f"Successfully migrated user data to {new_path}")
                return True

        # Nothing to migrate.
        return True

    except Exception as e:
        logger.error(f"Failed to migrate user directory: {e}")
        return False


def get_app_data_dir() -> pathlib.Path:
    """
    Get the application data directory, performing migration first.

    Returns:
        pathlib.Path: Path to ``~/.simkl-mps`` (created if missing).
    """
    migrate_user_directory()
    app_data_dir = get_new_data_dir()
    app_data_dir.mkdir(parents=True, exist_ok=True)
    return app_data_dir


def migrate_registry_entries():
    """Migrate Windows registry entries from legacy keys to ``Software\\simkl-mps``."""
    if platform.system().lower() != 'windows':
        return

    try:
        import winreg

        new_key_path = r"Software\simkl-mps\Media Player Scrobbler for SIMKL"
        legacy_key_paths = [
            r"Software\kavin\Media Player Scrobbler for SIMKL",
            r"Software\kavinthangavel\Media Player Scrobbler for SIMKL",
        ]

        # If the new key already exists, assume migration done.
        try:
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, new_key_path).Close()
            return
        except FileNotFoundError:
            pass

        for old_key_path in legacy_key_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, old_key_path) as old_key:
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, new_key_path) as new_key:
                        i = 0
                        while True:
                            try:
                                name, value, type_ = winreg.EnumValue(old_key, i)
                                winreg.SetValueEx(new_key, name, 0, type_, value)
                                i += 1
                            except OSError:
                                break
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, old_key_path)
                    logger.info("Migrated Windows registry entries")
                    return
            except FileNotFoundError:
                continue

    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Failed to migrate registry entries: {e}")


def migrate_macos_launch_agents():
    """Migrate macOS Launch Agents from legacy plist names to ``com.simkl-mps``."""
    if platform.system().lower() != 'darwin':
        return

    try:
        launch_agents_dir = pathlib.Path.home() / "Library" / "LaunchAgents"
        new_plist = launch_agents_dir / "com.simkl-mps.updater.plist"
        legacy_plists = [
            launch_agents_dir / "com.kavin.simkl-mps.updater.plist",
            launch_agents_dir / "com.kavinthangavel.simkl-mps.updater.plist",
        ]

        if new_plist.exists():
            return

        for old_plist in legacy_plists:
            if old_plist.exists():
                content = old_plist.read_text()
                content = content.replace("com.kavinthangavel.simkl-mps", "com.simkl-mps")
                content = content.replace("com.kavin.simkl-mps", "com.simkl-mps")
                new_plist.write_text(content)
                old_plist.unlink()
                logger.info("Migrated macOS Launch Agent")
                return

    except Exception as e:
        logger.error(f"Failed to migrate macOS Launch Agent: {e}")


def perform_full_migration():
    """Perform complete migration: data directory and OS-specific settings."""
    migrate_user_directory()
    migrate_registry_entries()
    migrate_macos_launch_agents()

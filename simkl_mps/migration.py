"""
User Directory Migration Utility
Migrates user data from 'kavinthangavel' to 'kavin' automatically.
"""

import logging
import os
import pathlib
import shutil
import platform
from typing import Optional

logger = logging.getLogger(__name__)

# Migration constants
OLD_USER_SUBDIR = "kavinthangavel"
NEW_USER_SUBDIR = "kavin"
APP_NAME = "simkl-mps"

def get_user_data_paths():
    """Get old and new user data directory paths for current OS."""
    home = pathlib.Path.home()
    
    # Standard paths for all OS
    old_path = home / OLD_USER_SUBDIR / APP_NAME
    new_path = home / NEW_USER_SUBDIR / APP_NAME
    
    return old_path, new_path

def migrate_user_directory() -> bool:
    """
    Migrate user directory from old to new name silently.
    
    Returns:
        bool: True if migration was performed or not needed, False if failed
    """
    try:
        old_path, new_path = get_user_data_paths()
        
        # If new directory already exists, no migration needed
        if new_path.exists():
            logger.debug(f"New directory already exists: {new_path}")
            return True
        
        # If old directory doesn't exist, no migration needed
        if not old_path.exists():
            logger.debug(f"Old directory doesn't exist: {old_path}")
            return True
        
        logger.info(f"Migrating user directory from {old_path} to {new_path}")
        
        # Create parent directory if needed
        new_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move entire directory
        shutil.move(str(old_path), str(new_path))
        
        logger.info(f"Successfully migrated user directory to {new_path}")
        
        # Try to remove old parent directory if empty
        try:
            old_path.parent.rmdir()
            logger.debug(f"Removed empty old parent directory: {old_path.parent}")
        except OSError:
            # Directory not empty or other issue, ignore
            pass
            
        return True
        
    except Exception as e:
        logger.error(f"Failed to migrate user directory: {e}")
        return False

def get_user_subdir() -> str:
    """
    Get the correct user subdirectory, handling migration automatically.
    
    Returns:
        str: The user subdirectory name to use
    """
    # Attempt migration first
    migrate_user_directory()
    
    # Always return the new subdirectory name
    return NEW_USER_SUBDIR

def get_app_data_dir() -> pathlib.Path:
    """
    Get the application data directory, with automatic migration.
    
    Returns:
        pathlib.Path: Path to the app data directory
    """
    home = pathlib.Path.home()
    user_subdir = get_user_subdir()  # This handles migration
    app_data_dir = home / user_subdir / APP_NAME
    
    # Ensure directory exists
    app_data_dir.mkdir(parents=True, exist_ok=True)
    
    return app_data_dir

def migrate_registry_entries():
    """Migrate Windows registry entries if needed."""
    if platform.system().lower() != 'windows':
        return
        
    try:
        import winreg
        
        old_key_path = r"Software\kavinthangavel\Media Player Scrobbler for SIMKL"
        new_key_path = r"Software\kavin\Media Player Scrobbler for SIMKL"
        
        try:
            # Try to open old key
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, old_key_path) as old_key:
                # Create new key
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, new_key_path) as new_key:
                    # Copy all values
                    i = 0
                    while True:
                        try:
                            name, value, type_ = winreg.EnumValue(old_key, i)
                            winreg.SetValueEx(new_key, name, 0, type_, value)
                            i += 1
                        except WindowsError:
                            break
                
                # Delete old key
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, old_key_path)
                logger.info("Migrated Windows registry entries")
                
        except FileNotFoundError:
            # Old key doesn't exist, nothing to migrate
            pass
            
    except ImportError:
        # winreg not available, skip
        pass
    except Exception as e:
        logger.error(f"Failed to migrate registry entries: {e}")

def migrate_macos_launch_agents():
    """Migrate macOS Launch Agents if needed."""
    if platform.system().lower() != 'darwin':
        return
        
    try:
        home = pathlib.Path.home()
        launch_agents_dir = home / "Library" / "LaunchAgents"
        
        old_plist = launch_agents_dir / "com.kavinthangavel.simkl-mps.updater.plist"
        new_plist = launch_agents_dir / "com.kavin.simkl-mps.updater.plist"
        
        if old_plist.exists() and not new_plist.exists():
            # Read old plist and update content
            content = old_plist.read_text()
            content = content.replace("kavinthangavel", "kavin")
            
            # Write new plist
            new_plist.write_text(content)
            
            # Remove old plist
            old_plist.unlink()
            
            logger.info("Migrated macOS Launch Agent")
            
    except Exception as e:
        logger.error(f"Failed to migrate macOS Launch Agent: {e}")

def perform_full_migration():
    """Perform complete migration including directories and OS-specific settings."""
    logger.info("Starting user directory migration")
    
    # Migrate main directory
    migrate_user_directory()
    
    # Migrate OS-specific settings
    migrate_registry_entries()
    migrate_macos_launch_agents()
    
    logger.info("Migration completed")

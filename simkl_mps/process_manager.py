"""
Process management for simkl-mps: single-instance control and PID locking.
"""
import atexit
import logging
import os
import signal
import subprocess
import sys

from simkl_mps.config_manager import get_app_data_dir

logger = logging.getLogger(__name__)

PID_LOCK_FILENAME = "simkl_mps.pid"


def get_pid_lock_path():
    """Return the path to the PID lock file."""
    return get_app_data_dir() / PID_LOCK_FILENAME


def is_process_alive(pid):
    """Return True if a process with the given PID is running."""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_pid_lock():
    """Read PID from lock file, or None if missing/invalid."""
    lock_path = get_pid_lock_path()
    if not lock_path.exists():
        return None
    try:
        content = lock_path.read_text(encoding="utf-8").strip()
        if content.isdigit():
            return int(content)
    except OSError as e:
        logger.warning("Could not read PID lock file %s: %s", lock_path, e)
    return None


def write_pid_lock(pid):
    """Write the current process PID to the lock file."""
    lock_path = get_pid_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(str(pid), encoding="utf-8")
    logger.debug("Wrote PID lock: %s", lock_path)


def remove_pid_lock():
    """Remove the PID lock file if it exists."""
    lock_path = get_pid_lock_path()
    try:
        if lock_path.exists():
            lock_path.unlink()
            logger.debug("Removed PID lock: %s", lock_path)
    except OSError as e:
        logger.warning("Could not remove PID lock file %s: %s", lock_path, e)


def find_running_pids(exclude_pid=None):
    """
    Find PIDs of running simkl-mps instances.

    Args:
        exclude_pid: PID to exclude from results (defaults to current process).

    Returns:
        list[int]: Running instance PIDs.
    """
    if exclude_pid is None:
        exclude_pid = os.getpid()

    pids = set()

    if sys.platform == "win32":
        try:
            import win32com.client

            wmi = win32com.client.GetObject("winmgmts:")
            process_names = [
                "MPS for SIMKL.exe",
                "MPSS.exe",
                "simkl-mps.exe",
                "python.exe",
            ]
            for process_name in process_names:
                if process_name == "python.exe":
                    processes = wmi.ExecQuery(
                        "SELECT ProcessId, CommandLine FROM Win32_Process "
                        "WHERE Name = 'python.exe' AND CommandLine LIKE '%simkl_mps%'"
                    )
                else:
                    processes = wmi.ExecQuery(
                        f"SELECT ProcessId FROM Win32_Process WHERE Name = '{process_name}'"
                    )
                for process in processes:
                    pid = process.ProcessId
                    if pid == exclude_pid:
                        continue
                    if process_name == "python.exe":
                        cmd_line = getattr(process, "CommandLine", None) or ""
                        if "simkl_mps" not in cmd_line.lower():
                            continue
                    pids.add(pid)
        except Exception as e:
            logger.error("Error finding Windows processes: %s", e)
    else:
        try:
            result = subprocess.run(
                ["pgrep", "-f", "simkl-mps|simkl_mps|MPS for SIMKL"],
                capture_output=True,
                text=True,
            )
            for pid_str in result.stdout.strip().split():
                pid_str = pid_str.strip()
                if pid_str.isdigit():
                    pid = int(pid_str)
                    if pid != exclude_pid:
                        pids.add(pid)
        except Exception as e:
            logger.error("Error finding processes via pgrep: %s", e)

    return sorted(pids)


def terminate_running_instances(exclude_pid=None, verbose=True):
    """
    Terminate all running simkl-mps instances.

    Args:
        exclude_pid: PID to leave running (defaults to current process).
        verbose: Print status messages to stdout.

    Returns:
        int: Number of processes terminated.
    """
    if exclude_pid is None:
        exclude_pid = os.getpid()

    terminated = 0

    if sys.platform == "win32":
        try:
            import win32com.client
            import win32con
            import win32gui
            import win32process

            if verbose:
                print("[*] Looking for running SIMKL-MPS instances...")

            def enum_windows_callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    window_text = win32gui.GetWindowText(hwnd)
                    class_name = win32gui.GetClassName(hwnd)
                    if "MPS for SIMKL" in window_text or "simkl-mps" in window_text.lower():
                        results.append(hwnd)
                    if class_name == "pystray" or "simkl-mps" in class_name.lower():
                        results.append(hwnd)
                return True

            window_handles = []
            win32gui.EnumWindows(enum_windows_callback, window_handles)
            for hwnd in window_handles:
                try:
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    terminated += 1
                except Exception as e:
                    logger.error("Failed to close window: %s", e)

            wmi = win32com.client.GetObject("winmgmts:")
            process_names = [
                "MPS for SIMKL.exe",
                "MPSS.exe",
                "simkl-mps.exe",
                "python.exe",
            ]
            for process_name in process_names:
                if process_name == "python.exe":
                    processes = wmi.ExecQuery(
                        "SELECT * FROM Win32_Process WHERE Name = 'python.exe' "
                        "AND CommandLine LIKE '%simkl_mps%'"
                    )
                else:
                    processes = wmi.ExecQuery(
                        f"SELECT * FROM Win32_Process WHERE Name = '{process_name}'"
                    )
                for process in processes:
                    try:
                        pid = process.ProcessId
                        if pid == exclude_pid:
                            continue
                        cmd_line = process.CommandLine or ""
                        if process_name == "python.exe" and "simkl_mps" not in cmd_line.lower():
                            continue
                        if verbose:
                            print(f"[*] Terminating process: {process_name} (PID: {pid})")
                        process.Terminate()
                        terminated += 1
                    except Exception as e:
                        logger.error("Failed to terminate %s: %s", process_name, e)
        except Exception as e:
            logger.error("Error during Windows process termination: %s", e, exc_info=True)
            if verbose:
                print(f"ERROR: Could not terminate processes: {e}", file=sys.stderr)
            raise
    else:
        if verbose:
            print("[*] Looking for running SIMKL-MPS instances...")
        for pid in find_running_pids(exclude_pid=exclude_pid):
            if verbose:
                print(f"[*] Terminating process with PID: {pid}")
            try:
                subprocess.run(["kill", str(pid)], check=False)
                terminated += 1
            except Exception as e:
                logger.error("Failed to terminate process %s: %s", pid, e)

    remove_pid_lock()
    return terminated


def acquire_instance_lock():
    """
    Acquire single-instance lock for the tray process.

    If another live instance holds the lock, log a warning and return False.
    Otherwise write the current PID and register cleanup handlers.

    Returns:
        bool: True if lock acquired, False if another instance is running.
    """
    current_pid = os.getpid()
    existing_pid = read_pid_lock()

    if existing_pid and existing_pid != current_pid and is_process_alive(existing_pid):
        logger.warning(
            "Another simkl-mps instance is already running (PID %s). Exiting.",
            existing_pid,
        )
        return False

    if existing_pid and not is_process_alive(existing_pid):
        remove_pid_lock()

    write_pid_lock(current_pid)

    def _cleanup(*_args):
        if read_pid_lock() == current_pid:
            remove_pid_lock()

    atexit.register(_cleanup)

    def _signal_handler(signum, frame):
        _cleanup()
        sys.exit(0)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _signal_handler)
        except (ValueError, OSError):
            pass

    return True

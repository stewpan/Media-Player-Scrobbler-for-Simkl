"""Background device-code authentication for the web dashboard.

Wraps the non-blocking PIN-flow steps in ``simkl_api`` (``request_pin`` /
``poll_pin_once`` / ``finalize_authentication``) so the UI can display the code
and poll ``/api/auth/status`` until the user authorizes on simkl.com.
"""
import logging
import threading
import time

from simkl_mps import simkl_api
from simkl_mps.credentials import get_credentials

logger = logging.getLogger(__name__)


class AuthManager:
    """Owns at most one in-flight device-code authentication attempt."""

    def __init__(self, on_authenticated=None, poll_interval=None):
        # on_authenticated(token, user_id) lets the live app pick up the token.
        self._on_authenticated = on_authenticated
        self._poll_interval_override = poll_interval
        self._lock = threading.Lock()
        self._thread = None
        self._flow = {
            "in_progress": False,
            "user_code": None,
            "verification_url": None,
            "pin_url": None,
            "error": None,
        }

    def status(self):
        creds = get_credentials() or {}
        with self._lock:
            flow = dict(self._flow)
        return {
            "authenticated": bool(creds.get("access_token")),
            "user_id": creds.get("user_id"),
            **flow,
        }

    def start(self):
        with self._lock:
            if self._flow["in_progress"]:
                return {"started": False, "reason": "already_in_progress", **self._flow}

        creds = get_credentials() or {}
        client_id = creds.get("client_id")
        if not client_id:
            return {"started": False, "reason": "missing_client_id"}

        pin = simkl_api.request_pin(client_id)
        if not pin:
            return {"started": False, "reason": "request_pin_failed"}

        with self._lock:
            self._flow = {
                "in_progress": True,
                "user_code": pin["user_code"],
                "verification_url": pin.get("verification_url"),
                "pin_url": pin.get("pin_url"),
                "error": None,
            }
        self._thread = threading.Thread(
            target=self._poll_loop, args=(pin, client_id), name="WebAuthPoll", daemon=True
        )
        self._thread.start()
        with self._lock:
            return {"started": True, **self._flow}

    def _finish(self, error=None):
        with self._lock:
            self._flow["in_progress"] = False
            self._flow["error"] = error

    def _poll_loop(self, pin, client_id):
        expires_in = pin.get("expires_in", 900)
        interval = (
            self._poll_interval_override
            if self._poll_interval_override is not None
            else pin.get("interval", 5)
        )
        deadline = time.monotonic() + expires_in
        try:
            while time.monotonic() < deadline:
                result = simkl_api.poll_pin_once(pin["user_code"], client_id)
                status = result.get("status")
                if status == "authorized":
                    token = result["access_token"]
                    user_id = simkl_api.finalize_authentication(token, client_id)
                    if self._on_authenticated:
                        try:
                            self._on_authenticated(token, user_id)
                        except Exception as e:  # pragma: no cover - callback is best-effort
                            logger.warning(f"on_authenticated callback failed: {e}")
                    self._finish()
                    return
                if status == "error":
                    self._finish(error=result.get("message", "authentication failed"))
                    return
                if status == "slow_down":
                    interval = min(interval * 2, 30)
                time.sleep(interval)
            self._finish(error="timed out")
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Web auth poll loop error: {e}", exc_info=True)
            self._finish(error="internal error")

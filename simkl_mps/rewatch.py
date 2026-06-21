"""Rewatch detection: decide whether an item has already been watched.

Checks the local watch history first (fast, precise for what the app has seen),
then falls back to the user's Simkl library. The Simkl watched library is
fetched via /sync/all-items and cached in memory, refreshed only when
/sync/activities reports a change (or after a TTL), so a scrobble doesn't incur
a heavy call every time.
"""
import logging
import threading
import time

from simkl_mps import simkl_api
from simkl_mps.simkl_api import is_internet_connected

logger = logging.getLogger(__name__)

# our media_type -> Simkl all-items type
_TYPE_MAP = {"movie": "movies", "show": "shows", "anime": "anime"}
# Simkl all-items type -> /sync/activities category key
_ACTIVITY_KEY = {"movies": "movies", "shows": "tv_shows", "anime": "anime"}

# Refresh the cached library at most this often even if activities is unavailable.
_CACHE_TTL_SECONDS = 600


class RewatchChecker:
    """Decides whether an item is a rewatch (local history first, then Simkl)."""

    def __init__(self, time_fn=time.monotonic):
        self._lock = threading.Lock()
        self._time = time_fn
        self._watched = {}     # simkl_type -> set[int] (movies) | {id: set[(season, ep)]}
        self._activity = {}    # simkl_type -> activity timestamp string
        self._fetched_at = {}  # simkl_type -> monotonic time of last fetch

    def is_rewatch(self, simkl_id, media_type, season, episode,
                   watch_history=None, client_id=None, access_token=None):
        """Return True if this (item / episode) was already watched before."""
        if simkl_id is None or media_type not in _TYPE_MAP:
            return False
        try:
            simkl_id = int(simkl_id)
        except (TypeError, ValueError):
            return False

        if self._local_says_watched(watch_history, simkl_id, media_type, episode):
            return True

        if client_id and access_token and is_internet_connected():
            try:
                return self._simkl_says_watched(simkl_id, media_type, season, episode,
                                                 client_id, access_token)
            except Exception as e:  # pragma: no cover - defensive; detection is best-effort
                logger.warning(f"Rewatch: Simkl check failed: {e}")
        return False

    # --- local history ---
    def _local_says_watched(self, watch_history, simkl_id, media_type, episode):
        if watch_history is None:
            return False
        entry = None
        for mt in (media_type, "tv", "show"):
            try:
                entry = watch_history.get_entry(simkl_id, mt)
            except Exception:
                entry = None
            if entry:
                break
        if not entry:
            return False
        if media_type == "movie":
            return True
        if episode is None:
            return True  # show already in history; no episode to disambiguate
        watched_eps = {e.get("number") for e in entry.get("episodes", []) if isinstance(e, dict)}
        return episode in watched_eps

    # --- Simkl library (cached) ---
    def _simkl_says_watched(self, simkl_id, media_type, season, episode, client_id, access_token):
        simkl_type = _TYPE_MAP[media_type]
        self._ensure_fresh(simkl_type, client_id, access_token)
        with self._lock:
            data = self._watched.get(simkl_type)
        if not data:
            return False
        if simkl_type == "movies":
            return simkl_id in data
        eps = data.get(simkl_id)
        if eps is None:
            return False
        if episode is None:
            return True
        if season is not None and (season, episode) in eps:
            return True
        return any(ep == episode for (_s, ep) in eps)  # season-agnostic fallback

    def _ensure_fresh(self, simkl_type, client_id, access_token):
        now = self._time()
        with self._lock:
            have = simkl_type in self._watched
            fetched_at = self._fetched_at.get(simkl_type)
            old_activity = self._activity.get(simkl_type)

        activities = simkl_api.get_sync_activities(client_id, access_token)
        new_activity = None
        if isinstance(activities, dict):
            cat = activities.get(_ACTIVITY_KEY[simkl_type])
            if isinstance(cat, dict):
                new_activity = cat.get("all")

        need = (not have) or (fetched_at is None) or (now - fetched_at > _CACHE_TTL_SECONDS)
        if new_activity is not None and new_activity != old_activity:
            need = True
        if not need:
            return

        items = simkl_api.get_watched_items(client_id, access_token, simkl_type)
        parsed = self._parse(simkl_type, items)
        with self._lock:
            self._watched[simkl_type] = parsed
            self._fetched_at[simkl_type] = now
            if new_activity is not None:
                self._activity[simkl_type] = new_activity

    @staticmethod
    def _parse(simkl_type, items):
        if simkl_type == "movies":
            ids = set()
            for it in items or []:
                if not isinstance(it, dict):
                    continue
                node = it.get("movie") or it  # all-items may nest under 'movie'
                sid = (node.get("ids") or {}).get("simkl")
                if sid is not None:
                    try:
                        ids.add(int(sid))
                    except (TypeError, ValueError):
                        pass
            return ids

        shows = {}
        for it in items or []:
            if not isinstance(it, dict):
                continue
            node = it.get("show") or it  # all-items may nest under 'show'
            sid = (node.get("ids") or {}).get("simkl")
            if sid is None:
                continue
            try:
                sid = int(sid)
            except (TypeError, ValueError):
                continue
            eps = set()
            for season in (it.get("seasons") or node.get("seasons") or []):
                snum = season.get("number")
                for ep in (season.get("episodes") or []):
                    enum = ep.get("number")
                    if enum is not None:
                        eps.add((snum, enum))
            shows[sid] = eps
        return shows

"""A persistent local copy of the user's Simkl watched library.

Mirrors the movies and show/anime episodes the user has marked watched on Simkl
into a JSON snapshot in the app data dir, refreshed from /sync/all-items only when
/sync/activities reports a change. The snapshot is used as the comparison material
for rewatch detection and works even while offline.
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from simkl_mps import simkl_api

logger = logging.getLogger(__name__)

# our media_type -> Simkl all-items type
_TYPE_MAP = {"movie": "movies", "show": "shows", "anime": "anime"}
# Simkl all-items type -> /sync/activities category key
_ACTIVITY_KEY = {"movies": "movies", "shows": "tv_shows", "anime": "anime"}

_FILE_NAME = "simkl_watched_library.json"
# Don't poll /sync/activities more often than this (the sync thread runs ~120s).
_MIN_SYNC_INTERVAL = 60


def _parse_movies(items):
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


def _parse_shows(items):
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


class WatchedLibrary:
    """Persistent snapshot of the user's Simkl watched movies/shows/anime."""

    def __init__(self, app_data_dir):
        self.path = Path(app_data_dir) / _FILE_NAME
        self._lock = threading.Lock()
        self._movies = set()   # set[int]
        self._shows = {}       # {int: set[(season, episode)]}
        self._anime = {}       # {int: set[(season, episode)]}
        self._activities = {}  # {simkl_type: activity timestamp}
        self._synced_at = None
        self._last_sync_attempt = 0.0
        self._load()

    # --- persistence ---
    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.warning(f"WatchedLibrary: could not load {self.path}: {e}")
            return
        try:
            self._movies = {int(x) for x in data.get("movies", [])}
            self._shows = {int(k): {tuple(p) for p in v} for k, v in (data.get("shows") or {}).items()}
            self._anime = {int(k): {tuple(p) for p in v} for k, v in (data.get("anime") or {}).items()}
            self._activities = data.get("activities") or {}
            self._synced_at = data.get("synced_at")
        except (TypeError, ValueError) as e:
            logger.warning(f"WatchedLibrary: malformed snapshot, ignoring: {e}")

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": 1,
                "synced_at": self._synced_at,
                "activities": self._activities,
                "movies": sorted(self._movies),
                "shows": {str(k): [list(p) for p in v] for k, v in self._shows.items()},
                "anime": {str(k): [list(p) for p in v] for k, v in self._anime.items()},
            }
            tmp = self.path.with_name(self.path.name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp, self.path)
        except OSError as e:
            logger.warning(f"WatchedLibrary: could not save {self.path}: {e}")

    # --- queries ---
    def is_watched(self, simkl_id, media_type, season=None, episode=None):
        if simkl_id is None or media_type not in _TYPE_MAP:
            return False
        try:
            simkl_id = int(simkl_id)
        except (TypeError, ValueError):
            return False
        simkl_type = _TYPE_MAP[media_type]
        with self._lock:
            if simkl_type == "movies":
                return simkl_id in self._movies
            eps = (self._shows if simkl_type == "shows" else self._anime).get(simkl_id)
        if eps is None:
            return False
        if episode is None:
            return True
        if season is not None:
            # Season is known -> require an exact (season, episode) match. A bare
            # episode-number match across seasons would wrongly flag e.g. S02E06 as
            # watched just because S01E06 was seen.
            return (season, episode) in eps
        # Season unknown -> best-effort match on episode number across seasons.
        return any(ep == episode for (_s, ep) in eps)

    def stats(self):
        with self._lock:
            return {
                "movies": len(self._movies),
                "shows": len(self._shows),
                "anime": len(self._anime),
                "total": len(self._movies) + len(self._shows) + len(self._anime),
                "synced_at": self._synced_at,
            }

    # --- sync ---
    def ensure_synced(self, client_id, access_token, force=False):
        """Refresh the local copy from Simkl if activities changed. Returns True if updated."""
        if not client_id or not access_token:
            return False
        now = time.monotonic()
        if not force and (now - self._last_sync_attempt) < _MIN_SYNC_INTERVAL:
            return False
        self._last_sync_attempt = now

        activities = simkl_api.get_sync_activities(client_id, access_token)
        changed = False
        for simkl_type in ("movies", "shows", "anime"):
            new_activity = None
            if isinstance(activities, dict):
                cat = activities.get(_ACTIVITY_KEY[simkl_type])
                if isinstance(cat, dict):
                    new_activity = cat.get("all")

            with self._lock:
                synced_before = simkl_type in self._activities  # synced at least once (even if empty)
                have_data = self._has_type(simkl_type)
                unchanged = (new_activity is not None
                             and new_activity == self._activities.get(simkl_type))
            if not force and synced_before and unchanged:
                continue

            items = simkl_api.get_watched_items(client_id, access_token, simkl_type)
            if not items and have_data:
                continue  # don't wipe a non-empty snapshot on an empty/failed fetch

            parsed = _parse_movies(items) if simkl_type == "movies" else _parse_shows(items)
            with self._lock:
                self._set_type(simkl_type, parsed)
                # Record the activity (or a marker) so the type counts as synced next time.
                self._activities[simkl_type] = new_activity if new_activity is not None else ""
            changed = True

        if changed:
            with self._lock:
                self._synced_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                self._save()
            logger.info(f"WatchedLibrary: local Simkl copy updated ({self.stats()}).")
        return changed

    # caller holds the lock
    def _has_type(self, simkl_type):
        if simkl_type == "movies":
            return bool(self._movies)
        return bool(self._shows if simkl_type == "shows" else self._anime)

    # caller holds the lock
    def _set_type(self, simkl_type, parsed):
        if simkl_type == "movies":
            self._movies = parsed
        elif simkl_type == "shows":
            self._shows = parsed
        else:
            self._anime = parsed

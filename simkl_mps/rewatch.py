"""Rewatch detection: decide whether an item has already been watched.

Checks the local watch history first (precise for what the app has recorded),
then the local copy of the user's Simkl watched library (``WatchedLibrary``),
which works offline. No network calls happen here — the library is kept fresh by
a background sync.
"""
import logging

logger = logging.getLogger(__name__)

_TYPE_MAP = {"movie": "movies", "show": "shows", "anime": "anime"}


def is_rewatch(simkl_id, media_type, season, episode, watch_history=None, library=None):
    """Return True if this (item / episode) was already watched before."""
    if simkl_id is None or media_type not in _TYPE_MAP:
        return False
    try:
        simkl_id = int(simkl_id)
    except (TypeError, ValueError):
        return False

    if _local_says_watched(watch_history, simkl_id, media_type, episode):
        return True

    if library is not None:
        try:
            if library.is_watched(simkl_id, media_type, season, episode):
                return True
        except Exception as e:  # pragma: no cover - defensive; detection is best-effort
            logger.warning(f"Rewatch: library check failed: {e}")
    return False


def _local_says_watched(watch_history, simkl_id, media_type, episode):
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

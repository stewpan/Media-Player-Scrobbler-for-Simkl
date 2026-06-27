"""JSON API blueprint for the embedded web dashboard.

All endpoints are read-only in this version (dashboard + read views). Settings
and auth writes are added in a later change. The blueprint is created with a
``context`` object that exposes the live scrobbler and the on-disk managers, so
the same factory can be driven by the running app or by a test double.
"""
import logging

from flask import Blueprint, jsonify, request

from simkl_mps.config_manager import get_setting, set_setting, _sanitize_dir_list

logger = logging.getLogger(__name__)

# Only these settings may be read/written via the web UI. Destructive actions
# (clear/reset) and daemon start/stop are intentionally excluded in this version.
_SETTINGS_KEYS = (
    "watch_completion_threshold",
    "disable_notifications",
    "skip_rewatch_scrobble",
    "auto_sync_interval",
    "allow_dirs",
    "deny_dirs",
)


def create_api_blueprint(context):
    """Build the ``/api`` blueprint.

    ``context`` must provide:
      - ``get_scrobbler()``      -> the live MediaScrobbler (or None)
      - ``is_monitor_running()`` -> bool
      - ``get_watch_history_manager()`` -> WatchHistoryManager (or None)
      - ``get_backlog_cleaner()``       -> BacklogCleaner (or None)
    """
    api = Blueprint("api", __name__)

    @api.get("/status")
    def status():
        scrobbler = context.get_scrobbler()
        running = context.is_monitor_running()
        if scrobbler is None:
            return jsonify({"monitor_running": running, "tracking": False})
        data = scrobbler.get_status()
        data["monitor_running"] = running
        return jsonify(data)

    @api.get("/history")
    def history():
        manager = context.get_watch_history_manager()
        if manager is None:
            return jsonify({"entries": [], "total": 0})
        try:
            limit = request.args.get("limit", type=int)
            offset = request.args.get("offset", default=0, type=int)
            sort_by = request.args.get("sort_by", default="watched_at")
            sort_order = request.args.get("sort_order", default="desc")
        except (TypeError, ValueError):
            limit, offset, sort_by, sort_order = None, 0, "watched_at", "desc"
        entries = manager.get_history(
            limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order
        )
        total = len(manager.get_history())
        return jsonify({"entries": entries, "total": total})

    @api.get("/stats")
    def stats():
        manager = context.get_watch_history_manager()
        counts = {"movie": 0, "show": 0, "anime": 0, "total": 0}
        if manager is not None:
            for entry in manager.get_history():
                media_type = (entry.get("type") or "movie").lower()
                if media_type in ("tv", "show"):
                    counts["show"] += 1
                elif media_type == "anime":
                    counts["anime"] += 1
                else:
                    counts["movie"] += 1
                counts["total"] += 1
        return jsonify(counts)

    @api.get("/backlog")
    def backlog():
        cleaner = context.get_backlog_cleaner()
        if cleaner is None:
            return jsonify({"items": [], "count": 0})
        pending = cleaner.get_pending() or {}
        items = list(pending.values()) if isinstance(pending, dict) else list(pending)
        return jsonify({"items": items, "count": len(items)})

    @api.get("/library")
    def library():
        lib = context.get_watched_library() if hasattr(context, "get_watched_library") else None
        if lib is None:
            return jsonify({"movies": 0, "shows": 0, "anime": 0, "total": 0, "synced_at": None})
        return jsonify(lib.stats())

    @api.post("/library/sync")
    def library_sync():
        lib = context.get_watched_library() if hasattr(context, "get_watched_library") else None
        if lib is None:
            return jsonify({"synced": False, "reason": "unavailable"}), 503
        from simkl_mps.credentials import get_credentials
        creds = get_credentials() or {}
        cid, tok = creds.get("client_id"), creds.get("access_token")
        if not cid or not tok:
            return jsonify({"synced": False, "reason": "not_authenticated"}), 400
        try:
            lib.ensure_synced(cid, tok, force=True)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Manual library sync failed: {e}")
            return jsonify({"synced": False, "reason": "error"}), 500
        return jsonify({"synced": True, **lib.stats()})

    @api.get("/settings")
    def get_settings():
        return jsonify({key: get_setting(key) for key in _SETTINGS_KEYS})

    @api.post("/settings")
    def update_settings():
        payload = request.get_json(silent=True) or {}
        unknown = [k for k in payload if k not in _SETTINGS_KEYS]
        if unknown:
            return jsonify({"error": "unknown_keys", "keys": unknown}), 400

        applied = {}
        dirs_changed = False
        for key, value in payload.items():
            if key == "watch_completion_threshold":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    return jsonify({"error": "invalid_value", "key": key}), 400
                if not (1 <= value <= 100):
                    return jsonify({"error": "out_of_range", "key": key}), 400
            elif key == "auto_sync_interval":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    return jsonify({"error": "invalid_value", "key": key}), 400
                if value < 0:
                    return jsonify({"error": "out_of_range", "key": key}), 400
            elif key in ("disable_notifications", "skip_rewatch_scrobble"):
                if not isinstance(value, bool):
                    return jsonify({"error": "invalid_value", "key": key}), 400
            elif key in ("allow_dirs", "deny_dirs"):
                value = _sanitize_dir_list(value)
                dirs_changed = True
            set_setting(key, value)
            applied[key] = value

        if dirs_changed:
            scrobbler = context.get_scrobbler()
            if scrobbler is not None and hasattr(scrobbler, "signal_dir_filters_update"):
                try:
                    scrobbler.signal_dir_filters_update()
                except Exception as e:  # pragma: no cover - best-effort signal
                    logger.debug(f"Failed to signal dir filter update: {e}")

        return jsonify({"updated": applied})

    @api.get("/auth/status")
    def auth_status():
        return jsonify(context.get_auth_manager().status())

    @api.post("/auth/start")
    def auth_start():
        result = context.get_auth_manager().start()
        ok = result.get("started") or result.get("reason") == "already_in_progress"
        return jsonify(result), (200 if ok else 400)

    return api

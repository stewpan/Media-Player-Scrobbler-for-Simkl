"""JSON API blueprint for the embedded web dashboard.

All endpoints are read-only in this version (dashboard + read views). Settings
and auth writes are added in a later change. The blueprint is created with a
``context`` object that exposes the live scrobbler and the on-disk managers, so
the same factory can be driven by the running app or by a test double.
"""
import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)


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

    return api

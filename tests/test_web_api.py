"""Tests for the embedded web dashboard API (read-only endpoints) and the
MediaScrobbler.get_status() snapshot it relies on.
"""
import socket
import types

import pytest

from simkl_mps.web.server import create_app, WebServer
from simkl_mps.media_scrobbler import MediaScrobbler


# --- test doubles -------------------------------------------------------------

class FakeHistoryManager:
    def __init__(self, entries):
        self._entries = entries
        self.calls = []

    def get_history(self, limit=None, offset=0, sort_by="watched_at", sort_order="desc"):
        self.calls.append((limit, offset, sort_by, sort_order))
        data = self._entries[offset:]
        return data[:limit] if limit else data


class FakeBacklog:
    def __init__(self, pending):
        self._pending = pending

    def get_pending(self):
        return self._pending


class FakeScrobbler:
    def __init__(self, status, backlog):
        self._status = status
        self.backlog_cleaner = backlog

    def get_status(self):
        return dict(self._status)


class FakeContext:
    def __init__(self, scrobbler=None, history=None, running=False):
        self._scrobbler = scrobbler
        self._history = history
        self._running = running

    def get_scrobbler(self):
        return self._scrobbler

    def is_monitor_running(self):
        return self._running

    def get_watch_history_manager(self):
        return self._history

    def get_backlog_cleaner(self):
        return self._scrobbler.backlog_cleaner if self._scrobbler else None


HISTORY = [
    {"simkl_id": 1, "title": "A Movie", "type": "movie", "watched_at": "2025-01-03"},
    {"simkl_id": 2, "title": "A Show", "type": "show", "watched_at": "2025-01-02"},
    {"simkl_id": 3, "title": "An Anime", "type": "anime", "watched_at": "2025-01-01"},
]


def _client(context, missing_dist=True):
    dist = "/nonexistent/dist" if missing_dist else None
    app = create_app(context, dist_dir=dist)
    app.testing = True
    return app.test_client()


# --- /api/status --------------------------------------------------------------

def test_status_with_scrobbler():
    status = {"tracking": True, "title": "Dune", "state": "Playing", "progress_percent": 42.0}
    scrobbler = FakeScrobbler(status, FakeBacklog({}))
    client = _client(FakeContext(scrobbler=scrobbler, running=True))
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Dune"
    assert body["monitor_running"] is True


def test_status_without_scrobbler():
    client = _client(FakeContext(scrobbler=None, running=False))
    body = client.get("/api/status").get_json()
    assert body == {"monitor_running": False, "tracking": False}


# --- /api/history -------------------------------------------------------------

def test_history_returns_entries_and_total():
    history = FakeHistoryManager(HISTORY)
    client = _client(FakeContext(history=history))
    body = client.get("/api/history").get_json()
    assert body["total"] == 3
    assert len(body["entries"]) == 3


def test_history_passes_paging_args():
    history = FakeHistoryManager(HISTORY)
    client = _client(FakeContext(history=history))
    client.get("/api/history?limit=1&offset=2&sort_by=title&sort_order=asc")
    assert (1, 2, "title", "asc") in history.calls


def test_history_without_manager():
    body = _client(FakeContext(history=None)).get("/api/history").get_json()
    assert body == {"entries": [], "total": 0}


# --- /api/stats ---------------------------------------------------------------

def test_stats_counts_by_type():
    client = _client(FakeContext(history=FakeHistoryManager(HISTORY)))
    body = client.get("/api/stats").get_json()
    assert body == {"movie": 1, "show": 1, "anime": 1, "total": 3}


# --- /api/backlog -------------------------------------------------------------

def test_backlog_returns_items():
    pending = {"10": {"simkl_id": 10, "title": "Queued"}}
    scrobbler = FakeScrobbler({}, FakeBacklog(pending))
    client = _client(FakeContext(scrobbler=scrobbler))
    body = client.get("/api/backlog").get_json()
    assert body["count"] == 1
    assert body["items"][0]["title"] == "Queued"


# --- SPA fallback -------------------------------------------------------------

def test_spa_serves_guidance_when_dist_missing():
    resp = _client(FakeContext()).get("/")
    assert resp.status_code == 200
    assert b"Dashboard not built" in resp.data


# --- MediaScrobbler.get_status() ----------------------------------------------

def test_webserver_bind_conflict_is_graceful():
    # Occupy a port, then a WebServer on the same port must fail soft (False),
    # never raise / exit — the dashboard is optional and must not crash the app.
    occupier = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupier.bind(("127.0.0.1", 0))
    occupier.listen()
    port = occupier.getsockname()[1]
    try:
        fake_app = types.SimpleNamespace(monitor=None, watch_history_manager=None)
        ws = WebServer(fake_app, port=port)
        assert ws.start() is False
    finally:
        occupier.close()


def test_webserver_start_serve_stop():
    fake_app = types.SimpleNamespace(
        monitor=types.SimpleNamespace(
            scrobbler=FakeScrobbler({"tracking": True, "title": "Live"}, FakeBacklog({})),
            running=True,
        ),
        watch_history_manager=None,
    )
    # Bind an ephemeral free port to avoid clashes in CI.
    probe = socket.socket(); probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]; probe.close()
    ws = WebServer(fake_app, port=port)
    assert ws.start() is True
    try:
        client = ws._app.test_client()
        body = client.get("/api/status").get_json()
        assert body["title"] == "Live"
    finally:
        ws.stop()


def test_get_status_snapshot(tmp_path):
    scrobbler = MediaScrobbler(app_data_dir=tmp_path, client_id="cid", access_token="tok")
    scrobbler.currently_tracking = "Dune.2021.mkv"
    scrobbler.movie_name = "Dune"
    scrobbler.media_type = "movie"
    scrobbler.state = "Playing"
    scrobbler.current_position_seconds = 30
    scrobbler.total_duration_seconds = 120
    status = scrobbler.get_status()
    assert status["tracking"] is True
    assert status["title"] == "Dune"
    assert status["progress_percent"] == 25.0
    assert status["duration_seconds"] == 120

"""Tests for WatchHistoryManager.record_rewatch (last-rewatched tracking)."""
from simkl_mps.watch_history_manager import WatchHistoryManager


def test_record_rewatch_updates_existing_entry(tmp_path):
    wh = WatchHistoryManager(tmp_path)
    wh.history.append({"simkl_id": 5, "type": "show", "title": "X", "watched_at": "2025-01-01"})
    wh._save_history()

    wh.record_rewatch(5, "show", "X", when="2026-06-27T10:00:00Z")

    # Persisted and visible on reload.
    fresh = WatchHistoryManager(tmp_path)
    entry = fresh.get_entry(5, "show")
    assert entry["last_rewatched_at"] == "2026-06-27T10:00:00Z"
    assert len(fresh.get_history()) == 1  # updated in place, not duplicated


def test_record_rewatch_creates_stub_for_unknown_item(tmp_path):
    wh = WatchHistoryManager(tmp_path)
    wh.record_rewatch(99, "anime", "Some Anime", when="2026-06-27T10:00:00Z")
    entry = wh.get_entry(99, "anime")
    assert entry is not None
    assert entry["title"] == "Some Anime"
    assert entry["last_rewatched_at"] == "2026-06-27T10:00:00Z"

"""Tests for the persistent local copy of the Simkl watched library."""
from unittest.mock import patch, MagicMock

import simkl_mps.simkl_api as simkl_api
from simkl_mps.watched_library import WatchedLibrary

ACTIVITIES = {"movies": {"all": "t1"}, "tv_shows": {"all": "t1"}, "anime": {"all": "t1"}}
MOVIES = [{"movie": {"ids": {"simkl": 100}}}, {"ids": {"simkl": 101}}]
SHOWS = [{"show": {"ids": {"simkl": 200}}, "seasons": [{"number": 1, "episodes": [{"number": 1}, {"number": 2}]}]}]


def _patched(activities=ACTIVITIES, movies=MOVIES, shows=SHOWS, anime=None):
    return (
        patch("simkl_mps.watched_library.simkl_api.get_sync_activities", return_value=activities),
        patch("simkl_mps.watched_library.simkl_api.get_watched_items",
              side_effect=lambda c, t, st: {"movies": movies, "shows": shows, "anime": anime or []}[st]),
    )


def test_sync_populates_and_queries(tmp_path):
    lib = WatchedLibrary(tmp_path)
    p_act, p_items = _patched()
    with p_act, p_items:
        assert lib.ensure_synced("c", "t", force=True) is True
    assert lib.is_watched(100, "movie") is True
    assert lib.is_watched(999, "movie") is False
    assert lib.is_watched(200, "show", 1, 2) is True
    assert lib.is_watched(200, "show", 1, 9) is False
    assert lib.stats()["movies"] == 2
    assert lib.stats()["shows"] == 1


def test_snapshot_persists_to_disk_and_reloads(tmp_path):
    lib = WatchedLibrary(tmp_path)
    p_act, p_items = _patched()
    with p_act, p_items:
        lib.ensure_synced("c", "t", force=True)
    assert (tmp_path / "simkl_watched_library.json").exists()

    # New instance loads from disk with no network at all.
    fresh = WatchedLibrary(tmp_path)
    assert fresh.is_watched(101, "movie") is True
    assert fresh.is_watched(200, "show", 1, 1) is True
    assert fresh.stats()["total"] == 3


def test_unchanged_activity_skips_refetch(tmp_path):
    lib = WatchedLibrary(tmp_path)
    with patch("simkl_mps.watched_library.simkl_api.get_sync_activities", return_value=ACTIVITIES), \
         patch("simkl_mps.watched_library.simkl_api.get_watched_items",
               side_effect=lambda c, t, st: {"movies": MOVIES, "shows": SHOWS, "anime": []}[st]) as items:
        lib.ensure_synced("c", "t", force=True)
        first = items.call_count
        lib._last_sync_attempt = 0.0  # bypass the time throttle
        lib.ensure_synced("c", "t", force=False)  # activity unchanged -> no refetch
        assert items.call_count == first


def test_empty_fetch_does_not_wipe_existing(tmp_path):
    lib = WatchedLibrary(tmp_path)
    p_act, p_items = _patched()
    with p_act, p_items:
        lib.ensure_synced("c", "t", force=True)
    # A later sync that returns nothing must keep the existing copy.
    with patch("simkl_mps.watched_library.simkl_api.get_sync_activities", return_value={"movies": {"all": "t2"}}), \
         patch("simkl_mps.watched_library.simkl_api.get_watched_items", return_value=[]):
        lib.ensure_synced("c", "t", force=True)
    assert lib.is_watched(100, "movie") is True


def test_no_credentials_is_noop(tmp_path):
    assert WatchedLibrary(tmp_path).ensure_synced(None, None) is False


def test_is_watched_is_season_strict(tmp_path):
    # Regression: only Season 1 (ep 1-8) watched; S02E06 must NOT count as watched
    # just because S01E06 was seen.
    lib = WatchedLibrary(tmp_path)
    shows = [{
        "show": {"ids": {"simkl": 1398568}},
        "seasons": [{"number": 1, "episodes": [{"number": n} for n in range(1, 9)]}],
    }]
    with patch("simkl_mps.watched_library.simkl_api.get_sync_activities", return_value={"tv_shows": {"all": "t1"}}), \
         patch("simkl_mps.watched_library.simkl_api.get_watched_items",
               side_effect=lambda c, t, st: {"movies": [], "shows": shows, "anime": []}[st]):
        lib.ensure_synced("c", "t", force=True)
    assert lib.is_watched(1398568, "show", 1, 6) is True    # S01E06 watched
    assert lib.is_watched(1398568, "show", 2, 6) is False   # S02E06 NOT watched (strict)
    assert lib.is_watched(1398568, "show", None, 6) is True  # season unknown -> episode match


# --- simkl_api sync helpers ---------------------------------------------------

def _resp(status, data):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    return r


@patch("simkl_mps.simkl_api.requests.get")
def test_get_watched_items_returns_type_list(mock_get):
    mock_get.return_value = _resp(200, {"movies": [{"ids": {"simkl": 1}}]})
    assert simkl_api.get_watched_items("c", "t", "movies") == [{"ids": {"simkl": 1}}]


def test_get_watched_items_rejects_bad_type():
    assert simkl_api.get_watched_items("c", "t", "bogus") == []
    assert simkl_api.get_watched_items(None, "t", "movies") == []


@patch("simkl_mps.simkl_api.requests.get")
def test_get_sync_activities(mock_get):
    mock_get.return_value = _resp(200, {"all": "ts"})
    assert simkl_api.get_sync_activities("c", "t") == {"all": "ts"}

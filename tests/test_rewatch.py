"""Tests for rewatch detection (local-first, Simkl fallback) and the sync API."""
from unittest.mock import patch, MagicMock

import simkl_mps.simkl_api as simkl_api
from simkl_mps.rewatch import RewatchChecker


class FakeWatchHistory:
    def __init__(self, entries):
        # entries keyed by (simkl_id, media_type)
        self.entries = entries

    def get_entry(self, simkl_id, media_type="movie"):
        return self.entries.get((simkl_id, media_type))


def _checker():
    # Fixed clock so the TTL never elapses between calls in a test.
    return RewatchChecker(time_fn=lambda: 1000.0)


# --- local history ------------------------------------------------------------

def test_local_movie_is_rewatch_without_simkl_call():
    wh = FakeWatchHistory({(123, "movie"): {"simkl_id": 123, "type": "movie"}})
    with patch("simkl_mps.rewatch.is_internet_connected") as inet:
        assert _checker().is_rewatch(123, "movie", None, None, watch_history=wh) is True
        inet.assert_not_called()  # local hit short-circuits


def test_local_episode_watched():
    wh = FakeWatchHistory({(55, "show"): {"episodes": [{"number": 4}, {"number": 5}]}})
    c = _checker()
    assert c.is_rewatch(55, "show", 1, 4, watch_history=wh) is True


def test_local_episode_not_watched_and_offline_is_false():
    wh = FakeWatchHistory({(55, "show"): {"episodes": [{"number": 4}]}})
    # No credentials -> no Simkl fallback.
    assert _checker().is_rewatch(55, "show", 1, 9, watch_history=wh) is False


def test_first_watch_is_not_rewatch():
    assert _checker().is_rewatch(1, "movie", None, None, watch_history=FakeWatchHistory({})) is False


# --- Simkl fallback -----------------------------------------------------------

@patch("simkl_mps.rewatch.is_internet_connected", return_value=True)
@patch("simkl_mps.simkl_api.get_watched_items")
@patch("simkl_mps.simkl_api.get_sync_activities", return_value={"movies": {"all": "t1"}})
def test_simkl_movie_rewatch(mock_act, mock_items, _inet):
    mock_items.return_value = [{"movie": {"ids": {"simkl": 777}}}]
    c = _checker()
    assert c.is_rewatch(777, "movie", None, None, client_id="c", access_token="t") is True
    assert c.is_rewatch(111, "movie", None, None, client_id="c", access_token="t") is False


@patch("simkl_mps.rewatch.is_internet_connected", return_value=True)
@patch("simkl_mps.simkl_api.get_watched_items")
@patch("simkl_mps.simkl_api.get_sync_activities", return_value={"tv_shows": {"all": "t1"}})
def test_simkl_episode_rewatch(mock_act, mock_items, _inet):
    mock_items.return_value = [
        {"show": {"ids": {"simkl": 888}}, "seasons": [{"number": 2, "episodes": [{"number": 3}]}]}
    ]
    c = _checker()
    assert c.is_rewatch(888, "show", 2, 3, client_id="c", access_token="t") is True
    assert c.is_rewatch(888, "show", 2, 4, client_id="c", access_token="t") is False


@patch("simkl_mps.rewatch.is_internet_connected", return_value=True)
@patch("simkl_mps.simkl_api.get_watched_items")
@patch("simkl_mps.simkl_api.get_sync_activities", return_value={"movies": {"all": "t1"}})
def test_simkl_library_cached_until_activity_changes(mock_act, mock_items, _inet):
    mock_items.return_value = [{"ids": {"simkl": 5}}]
    c = _checker()
    c.is_rewatch(5, "movie", None, None, client_id="c", access_token="t")
    c.is_rewatch(5, "movie", None, None, client_id="c", access_token="t")
    # Activity timestamp unchanged -> the heavy all-items fetch happened once.
    assert mock_items.call_count == 1


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

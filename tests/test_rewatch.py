"""Tests for the rewatch decision (local history first, then the local Simkl copy)."""
from simkl_mps.rewatch import is_rewatch


class FakeWatchHistory:
    def __init__(self, entries):
        self.entries = entries  # keyed by (simkl_id, media_type)

    def get_entry(self, simkl_id, media_type="movie"):
        return self.entries.get((simkl_id, media_type))


class FakeLibrary:
    def __init__(self, movies=None, episodes=None):
        self.movies = set(movies or [])
        # episodes: {simkl_id: set[(season, episode)]}
        self.episodes = episodes or {}

    def is_watched(self, simkl_id, media_type, season=None, episode=None):
        if media_type == "movie":
            return simkl_id in self.movies
        eps = self.episodes.get(simkl_id)
        if eps is None:
            return False
        if episode is None:
            return True
        if season is not None:
            return (season, episode) in eps  # season-strict
        return any(e == episode for (_s, e) in eps)


def test_local_movie_is_rewatch():
    wh = FakeWatchHistory({(123, "movie"): {"type": "movie"}})
    assert is_rewatch(123, "movie", None, None, watch_history=wh) is True


def test_local_episode_watched():
    wh = FakeWatchHistory({(55, "show"): {"season": 1, "episodes": [{"number": 4}]}})
    assert is_rewatch(55, "show", 1, 4, watch_history=wh) is True


def test_local_episode_wrong_season_not_rewatch():
    # S01E06 in history must not flag S02E06 as a rewatch.
    wh = FakeWatchHistory({(55, "show"): {"season": 1, "episodes": [{"number": 6}]}})
    assert is_rewatch(55, "show", 2, 6, watch_history=wh) is False
    assert is_rewatch(55, "show", 1, 6, watch_history=wh) is True


def test_library_movie_when_not_local():
    lib = FakeLibrary(movies={777})
    assert is_rewatch(777, "movie", None, None, watch_history=FakeWatchHistory({}), library=lib) is True
    assert is_rewatch(778, "movie", None, None, watch_history=FakeWatchHistory({}), library=lib) is False


def test_library_episode_when_not_local():
    lib = FakeLibrary(episodes={888: {(2, 3)}})
    assert is_rewatch(888, "show", 2, 3, watch_history=None, library=lib) is True
    assert is_rewatch(888, "show", 2, 4, watch_history=None, library=lib) is False


def test_first_watch_is_not_rewatch():
    assert is_rewatch(1, "movie", None, None, watch_history=FakeWatchHistory({}), library=FakeLibrary()) is False


def test_bad_inputs():
    assert is_rewatch(None, "movie", None, None) is False
    assert is_rewatch("not-int", "movie", None, None) is False
    assert is_rewatch(5, "podcast", None, None) is False

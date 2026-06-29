"""Unit tests for the deterministic core logic in MediaScrobbler.

Covers percentage/completion math, scrobble-payload construction across media
types, pause detection, file-change detection and the display suffix — all
without network or a running player.
"""
import pytest

from simkl_mps.media_scrobbler import MediaScrobbler

WATCHED_AT = "2025-01-01T00:00:00Z"


@pytest.fixture
def scrobbler(tmp_path):
    return MediaScrobbler(app_data_dir=tmp_path, client_id="cid", access_token="token")


# --- _calculate_percentage ----------------------------------------------------

def test_percentage_position_based(scrobbler):
    scrobbler.current_position_seconds = 50
    scrobbler.total_duration_seconds = 100
    assert scrobbler._calculate_percentage(use_position=True) == 50.0


def test_percentage_accumulated(scrobbler):
    scrobbler.current_position_seconds = None
    scrobbler.total_duration_seconds = 120
    scrobbler.watch_time = 90
    assert scrobbler._calculate_percentage(use_accumulated=True) == 75.0


def test_percentage_capped_at_100(scrobbler):
    scrobbler.current_position_seconds = 130
    scrobbler.total_duration_seconds = 100
    assert scrobbler._calculate_percentage(use_position=True) == 100


def test_percentage_zero_duration_returns_none(scrobbler):
    scrobbler.current_position_seconds = 10
    scrobbler.total_duration_seconds = 0
    assert scrobbler._calculate_percentage(use_position=True) is None


# --- is_complete --------------------------------------------------------------

def test_is_complete_meets_threshold(scrobbler):
    scrobbler.currently_tracking = "Some Movie"
    scrobbler.completed = False
    scrobbler.completion_threshold = 80
    scrobbler.current_position_seconds = 80
    scrobbler.total_duration_seconds = 100
    assert scrobbler.is_complete() is True


def test_is_complete_below_threshold_override(scrobbler):
    scrobbler.currently_tracking = "Some Movie"
    scrobbler.completed = False
    scrobbler.completion_threshold = 80
    scrobbler.current_position_seconds = 80
    scrobbler.total_duration_seconds = 100
    assert scrobbler.is_complete(threshold_override=90) is False


def test_is_complete_not_tracking(scrobbler):
    scrobbler.currently_tracking = None
    assert scrobbler.is_complete() is False


# --- runtime plausibility guard -----------------------------------------------

def test_is_complete_blocked_when_played_far_shorter_than_runtime(scrobbler):
    # A 9-minute file claiming to be a 90-minute film must NOT complete, even at 100%.
    scrobbler.currently_tracking = "Some Movie"
    scrobbler.completed = False
    scrobbler.completion_threshold = 80
    scrobbler.current_position_seconds = 540  # 9 min, 100% of the (wrong) file length
    scrobbler.total_duration_seconds = 540    # player/file says 9 min
    scrobbler.runtime_seconds = 90 * 60       # Simkl says 90 min
    assert scrobbler.is_complete() is False


def test_is_complete_allows_minor_runtime_difference(scrobbler):
    # An 88-min file of a 90-min film is plausible — must still complete.
    scrobbler.currently_tracking = "Some Movie"
    scrobbler.completed = False
    scrobbler.completion_threshold = 80
    scrobbler.current_position_seconds = 88 * 60
    scrobbler.total_duration_seconds = 88 * 60
    scrobbler.runtime_seconds = 90 * 60
    assert scrobbler.is_complete() is True


def test_is_complete_allows_longer_than_official_runtime(scrobbler):
    # Extended cut / trailing credits: longer than Simkl's runtime is fine.
    scrobbler.currently_tracking = "Some Movie"
    scrobbler.completed = False
    scrobbler.completion_threshold = 80
    scrobbler.current_position_seconds = 110 * 60
    scrobbler.total_duration_seconds = 120 * 60
    scrobbler.runtime_seconds = 90 * 60
    assert scrobbler.is_complete() is True


def test_is_complete_no_runtime_known_does_not_block(scrobbler):
    # Without an official runtime we can't tell — guard must stay out of the way.
    scrobbler.currently_tracking = "Some Movie"
    scrobbler.completed = False
    scrobbler.completion_threshold = 80
    scrobbler.current_position_seconds = 80
    scrobbler.total_duration_seconds = 100
    scrobbler.runtime_seconds = None
    assert scrobbler.is_complete() is True


# --- _build_add_to_history_payload --------------------------------------------

def test_payload_movie(scrobbler):
    scrobbler.simkl_id = 123
    scrobbler.media_type = "movie"
    payload = scrobbler._build_add_to_history_payload(watched_at=WATCHED_AT)
    assert payload == {"movies": [{"ids": {"simkl": 123}, "watched_at": WATCHED_AT}]}


def test_payload_show_with_season_episode(scrobbler):
    scrobbler.simkl_id = 456
    scrobbler.media_type = "show"
    scrobbler.season = 2
    scrobbler.episode = 5
    scrobbler.movie_name = "Some Show"
    payload = scrobbler._build_add_to_history_payload(watched_at=WATCHED_AT)
    assert payload == {
        "shows": [{
            "ids": {"simkl": 456},
            "seasons": [{"number": 2, "episodes": [{"number": 5, "watched_at": WATCHED_AT}]}],
        }]
    }


def test_payload_show_season_override_for_season_specific_entry(scrobbler):
    # A season-specific Simkl entry (title says "Season 3") catalogs episodes
    # under season 1, so the scrobble season is overridden to 1.
    scrobbler.simkl_id = 789
    scrobbler.media_type = "show"
    scrobbler.season = 3
    scrobbler.episode = 4
    scrobbler.movie_name = "Jujutsu Kaisen Season 3"
    payload = scrobbler._build_add_to_history_payload(watched_at=WATCHED_AT)
    assert payload["shows"][0]["seasons"][0]["number"] == 1


def test_payload_show_missing_season_episode_returns_none(scrobbler):
    scrobbler.simkl_id = 456
    scrobbler.media_type = "show"
    scrobbler.season = None
    scrobbler.episode = None
    assert scrobbler._build_add_to_history_payload(watched_at=WATCHED_AT) is None


def test_payload_anime_without_season(scrobbler):
    # No season -> episodes nested directly under the show (OVA-style).
    scrobbler.simkl_id = 321
    scrobbler.media_type = "anime"
    scrobbler.season = None
    scrobbler.episode = 3
    scrobbler.movie_name = "Some Anime"
    payload = scrobbler._build_add_to_history_payload(watched_at=WATCHED_AT)
    assert payload == {
        "shows": [{
            "ids": {"simkl": 321},
            "episodes": [{"number": 3, "watched_at": WATCHED_AT}],
        }]
    }


def test_payload_anime_with_season_nests_under_season(scrobbler):
    scrobbler.simkl_id = 321
    scrobbler.media_type = "anime"
    scrobbler.season = 2
    scrobbler.episode = 3
    scrobbler.movie_name = "Some Anime"
    payload = scrobbler._build_add_to_history_payload(watched_at=WATCHED_AT)
    assert payload["shows"][0]["seasons"][0]["number"] == 2
    assert payload["shows"][0]["seasons"][0]["episodes"] == [
        {"number": 3, "watched_at": WATCHED_AT}
    ]


def test_payload_no_simkl_id_returns_none(scrobbler):
    scrobbler.simkl_id = None
    scrobbler.media_type = "movie"
    assert scrobbler._build_add_to_history_payload(watched_at=WATCHED_AT) is None


def test_payload_invalid_simkl_id_returns_none(scrobbler):
    scrobbler.simkl_id = "not-an-int"
    scrobbler.media_type = "movie"
    assert scrobbler._build_add_to_history_payload(watched_at=WATCHED_AT) is None


def test_payload_defaults_watched_at_to_utc_z(scrobbler):
    scrobbler.simkl_id = 123
    scrobbler.media_type = "movie"
    payload = scrobbler._build_add_to_history_payload()
    watched_at = payload["movies"][0]["watched_at"]
    assert watched_at.endswith("Z")
    assert "+00:00" not in watched_at


# --- _detect_pause ------------------------------------------------------------

@pytest.mark.parametrize("title, expected", [
    ("Movie.mkv - Paused - VLC", True),
    ("Movie.mkv [Paused]", True),
    ("Movie.mkv - pause", True),
    ("Movie.mkv - VLC media player", False),
])
def test_detect_pause(scrobbler, title, expected):
    assert scrobbler._detect_pause({"title": title}) is expected


def test_detect_pause_no_title(scrobbler):
    assert scrobbler._detect_pause(None) is False
    assert scrobbler._detect_pause({}) is False


# --- _has_media_file_changed (staticmethod) -----------------------------------

def test_file_changed_true_on_different_basename():
    assert MediaScrobbler._has_media_file_changed("/a/S01E01.mkv", "/a/S01E02.mkv") is True


def test_file_changed_false_same_basename_case_insensitive():
    assert MediaScrobbler._has_media_file_changed("/a/Episode.MKV", "/b/episode.mkv") is False


def test_file_changed_false_on_missing_input():
    assert MediaScrobbler._has_media_file_changed(None, "/a/x.mkv") is False
    assert MediaScrobbler._has_media_file_changed("/a/x.mkv", None) is False


# --- _build_episode_display_suffix --------------------------------------------

def test_display_suffix_show(scrobbler):
    scrobbler.media_type = "show"
    scrobbler.display_season = 3
    scrobbler.display_episode = 5
    scrobbler.season = None
    scrobbler.episode = None
    assert scrobbler._build_episode_display_suffix() == " S03E05"


def test_display_suffix_movie_is_empty(scrobbler):
    scrobbler.media_type = "movie"
    assert scrobbler._build_episode_display_suffix() == ""


# --- file-search result validation --------------------------------------------

def test_titles_roughly_match_rejects_unrelated():
    # Regression: Simkl /search/file returned "ZB1's ROCK Festival" for an Avatar file.
    assert MediaScrobbler._titles_roughly_match("Avatar The Last Airbender", "ZB1's ROCK Festival") is False


@pytest.mark.parametrize("expected, candidate", [
    ("Avatar The Last Airbender", "Avatar: The Last Airbender"),  # punctuation variant
    ("The Office US", "The Office"),                              # extra word
    ("Game of Thrones", "Game of Thrones"),                      # exact
])
def test_titles_roughly_match_accepts_variants(expected, candidate):
    assert MediaScrobbler._titles_roughly_match(expected, candidate) is True


def test_titles_roughly_match_unknown_does_not_reject():
    # Missing data must not cause a false rejection.
    assert MediaScrobbler._titles_roughly_match("", "ZB1's ROCK Festival") is True
    assert MediaScrobbler._titles_roughly_match("Avatar", "") is True


def test_title_from_filename(scrobbler):
    fn = "/tv/Avatar - The Last Airbender (2024) - S02E06 - The Parable [WEBDL-1080p]-FLUX.mkv"
    assert "Last Airbender" in scrobbler._title_from_filename(fn, None)


# --- match-confidence guard ---------------------------------------------------

def test_match_confidence_rejects_unrelated(scrobbler):
    assert scrobbler._match_is_confident(
        "Avatar The Last Airbender S02E05.mkv", "movie", "ZB1's ROCK Festival") is False


@pytest.mark.parametrize("inp, mtype, result", [
    ("Avatar The Last Airbender (2024).mkv", "movie", "Avatar: The Last Airbender"),
    ("Breaking Bad S01E01.mkv", "show", "Breaking Bad"),
])
def test_match_confidence_accepts_related(scrobbler, inp, mtype, result):
    assert scrobbler._match_is_confident(inp, mtype, result) is True


def test_match_confidence_skips_anime_alt_titles(scrobbler):
    # English filename, Japanese Simkl title -> anime is exempt, must not be rejected.
    assert scrobbler._match_is_confident(
        "Attack on Titan S01E01.mkv", "anime", "Shingeki no Kyojin") is True

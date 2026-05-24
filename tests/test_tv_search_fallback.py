"""Tests for the TV show search fallback behavior."""
from unittest.mock import MagicMock, patch
import pytest
from requests.exceptions import RequestException

from simkl_mps.simkl_api import search_tv
from simkl_mps.media_scrobbler import MediaScrobbler


def _make_response(status_code, json_data=None):
    response = MagicMock()
    response.status_code = status_code
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.side_effect = ValueError("not json")
    return response


@patch("simkl_mps.simkl_api.is_internet_connected", return_value=True)
@patch("simkl_mps.simkl_api.requests.get")
def test_search_tv_success(mock_get, _mock_inet):
    # Mock a successful response with a list of TV shows
    mock_get.return_value = _make_response(200, [
        {
            "title": "Breaking Bad",
            "ids": {
                "simkl_id": 12345
            }
        }
    ])

    result = search_tv("Breaking Bad", "client_id_123", "token_123")

    assert result == {
        "show": {
            "title": "Breaking Bad",
            "ids": {
                "simkl_id": 12345,
                "simkl": 12345
            }
        }
    }
    mock_get.assert_called_once()


@patch("simkl_mps.simkl_api.is_internet_connected", return_value=True)
@patch("simkl_mps.simkl_api.requests.get")
def test_search_tv_empty_results(mock_get, _mock_inet):
    mock_get.return_value = _make_response(200, [])

    result = search_tv("Unknown Show", "client_id_123", "token_123")

    assert result is None


@patch("simkl_mps.simkl_api.is_internet_connected", return_value=True)
@patch("simkl_mps.simkl_api.requests.get")
def test_search_tv_http_error(mock_get, _mock_inet):
    mock_get.return_value = _make_response(404)

    result = search_tv("Failed Show", "client_id_123", "token_123")

    assert result is None


@patch("simkl_mps.simkl_api.is_internet_connected", return_value=True)
@patch("simkl_mps.simkl_api.requests.get")
def test_search_tv_network_exception(mock_get, _mock_inet):
    mock_get.side_effect = RequestException("Network error")

    result = search_tv("Failed Show Network", "client_id_123", "token_123")

    assert result is None


@patch("simkl_mps.simkl_api.is_internet_connected", return_value=False)
def test_search_tv_offline(_mock_inet):
    result = search_tv("Offline Show", "client_id_123", "token_123")
    assert result is None


def test_search_tv_missing_credentials():
    result = search_tv("Some Show", None, "token_123")
    assert result is None

    result = search_tv("Some Show", "client_id_123", None)
    assert result is None


@patch("simkl_mps.media_scrobbler.is_internet_connected", return_value=True)
@patch("simkl_mps.media_scrobbler.resolve_season_entry")
@patch("simkl_mps.media_scrobbler.search_movie")
def test_media_scrobbler_searches_tv_first_with_episode_notation(mock_search_movie, mock_resolve_season, _mock_inet, tmp_path):
    scrobbler = MediaScrobbler(app_data_dir=tmp_path, client_id="cid", access_token="token")
    scrobbler._process_simkl_search_result = MagicMock()

    # Episode notation present: S01E01
    mock_resolve_season.return_value = {
        "simkl_id": 555,
        "title": "Game of Thrones",
        "type": "anime",
        "raw_result": {"title": "Game of Thrones", "ids": {"simkl": 555}}
    }
    
    # We trigger the search logic
    scrobbler._identify_movie("Game of Thrones S01E01")

    mock_resolve_season.assert_called_with("Game of Thrones", 1, 1, "cid", "token", media_type="anime")
    mock_search_movie.assert_not_called()
    scrobbler._process_simkl_search_result.assert_called_once_with(
        {"show": {"title": "Game of Thrones", "ids": {"simkl": 555}}},
        "Game of Thrones S01E01",
        "game of thrones s01e01",
        "simkl_search_resolver_anime"
    )


@patch("simkl_mps.media_scrobbler.is_internet_connected", return_value=True)
@patch("simkl_mps.media_scrobbler.resolve_season_entry")
@patch("simkl_mps.media_scrobbler.search_movie")
def test_media_scrobbler_falls_back_to_movie_if_tv_search_fails(mock_search_movie, mock_resolve_season, _mock_inet, tmp_path):
    scrobbler = MediaScrobbler(app_data_dir=tmp_path, client_id="cid", access_token="token")
    scrobbler._process_simkl_search_result = MagicMock()

    # Episode notation present: S01 (which resolves to Season 1, Episode 1)
    mock_resolve_season.return_value = None
    mock_search_movie.return_value = [{"title": "Game of Thrones Special", "ids": {"simkl_id": 999}}]

    scrobbler._identify_movie("Game of Thrones S01")

    # It will try anime first, then show
    mock_resolve_season.assert_any_call("Game of Thrones", 1, 1, "cid", "token", media_type="anime")
    mock_resolve_season.assert_any_call("Game of Thrones", 1, 1, "cid", "token", media_type="show")
    mock_search_movie.assert_called_once_with("Game of Thrones S01", "cid", "token", file_path=None)
    scrobbler._process_simkl_search_result.assert_called_once_with(
        [{"title": "Game of Thrones Special", "ids": {"simkl_id": 999}}],
        "Game of Thrones S01",
        "game of thrones s01",
        "simkl_search_movie"
    )


@patch("simkl_mps.media_scrobbler.is_internet_connected", return_value=True)
@patch("simkl_mps.media_scrobbler.resolve_season_entry")
@patch("simkl_mps.media_scrobbler.search_movie")
def test_media_scrobbler_searches_movie_directly_without_episode_notation(mock_search_movie, mock_resolve_season, _mock_inet, tmp_path):
    scrobbler = MediaScrobbler(app_data_dir=tmp_path, client_id="cid", access_token="token")
    scrobbler._process_simkl_search_result = MagicMock()

    # No episode notation
    mock_search_movie.return_value = [{"title": "Inception", "ids": {"simkl_id": 777}}]

    scrobbler._identify_movie("Inception")

    mock_resolve_season.assert_not_called()
    mock_search_movie.assert_called_once_with("Inception", "cid", "token", file_path=None)
    scrobbler._process_simkl_search_result.assert_called_once_with(
        [{"title": "Inception", "ids": {"simkl_id": 777}}],
        "Inception",
        "inception",
        "simkl_search_movie"
    )


@patch("simkl_mps.media_scrobbler.is_internet_connected", return_value=True)
@patch("simkl_mps.media_scrobbler.resolve_season_entry")
def test_media_scrobbler_searches_with_season_suffix_first(mock_resolve_season, _mock_inet, tmp_path):
    scrobbler = MediaScrobbler(app_data_dir=tmp_path, client_id="cid", access_token="token")
    scrobbler._process_simkl_search_result = MagicMock()

    # Episode notation present: S03E04
    mock_resolve_season.return_value = {
        "simkl_id": 12345,
        "title": "Jujutsu Kaisen Season 3",
        "type": "anime",
        "raw_result": {"title": "Jujutsu Kaisen Season 3", "ids": {"simkl": 12345}}
    }

    scrobbler._identify_movie("Jujutsu Kaisen S03E04")

    # Assert that resolve_season_entry was called with the correct parameters
    mock_resolve_season.assert_any_call("Jujutsu Kaisen", 3, 4, "cid", "token", media_type="anime")
    scrobbler._process_simkl_search_result.assert_called_once_with(
        {"show": {"title": "Jujutsu Kaisen Season 3", "ids": {"simkl": 12345}}},
        "Jujutsu Kaisen S03E04",
        "jujutsu kaisen s03e04",
        "simkl_search_resolver_anime"
    )


def test_build_add_to_history_payload_overrides_season_for_season_specific_entry(tmp_path):
    scrobbler = MediaScrobbler(app_data_dir=tmp_path, client_id="cid", access_token="token")
    scrobbler.simkl_id = 12345
    scrobbler.media_type = "show"
    scrobbler.season = 3
    scrobbler.episode = 4
    scrobbler.movie_name = "Jujutsu Kaisen Season 3"

    payload = scrobbler._build_add_to_history_payload()

    # The season should be overridden to 1 since Jujutsu Kaisen Season 3 is a season-level entry
    assert payload == {
        "shows": [{
            "ids": {"simkl": 12345},
            "seasons": [{"number": 1, "episodes": [{"number": 4, "watched_at": payload["shows"][0]["seasons"][0]["episodes"][0]["watched_at"]}]}]
        }]
    }


def test_build_add_to_history_payload_does_not_override_for_non_season_specific_entry(tmp_path):
    scrobbler = MediaScrobbler(app_data_dir=tmp_path, client_id="cid", access_token="token")
    scrobbler.simkl_id = 12345
    scrobbler.media_type = "show"
    scrobbler.season = 3
    scrobbler.episode = 4
    scrobbler.movie_name = "Jujutsu Kaisen"  # Main show title

    payload = scrobbler._build_add_to_history_payload()

    # The season should remain 3
    assert payload == {
        "shows": [{
            "ids": {"simkl": 12345},
            "seasons": [{"number": 3, "episodes": [{"number": 4, "watched_at": payload["shows"][0]["seasons"][0]["episodes"][0]["watched_at"]}]}]
        }]
    }


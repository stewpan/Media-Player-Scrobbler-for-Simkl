"""Tests for the season resolver and end-to-end Jujutsu Kaisen S03E04 resolution."""
from unittest.mock import MagicMock, patch
import pytest

from simkl_mps.season_resolver import (
    resolve_season_entry,
    verify_episode_exists,
    title_matches_season,
    clear_resolver_cache,
    _resolver_cache
)
from simkl_mps.media_scrobbler import MediaScrobbler


@pytest.fixture(autouse=True)
def clean_cache():
    clear_resolver_cache()


def test_title_matches_season():
    # Exact season label matches
    assert title_matches_season("Jujutsu Kaisen Season 3", 3) is True
    assert title_matches_season("Jujutsu Kaisen 3rd Season", 3) is True
    assert title_matches_season("Jujutsu Kaisen S3", 3) is True
    assert title_matches_season("Jujutsu Kaisen S03", 3) is True
    assert title_matches_season("Jujutsu Kaisen Part 3", 3) is True
    assert title_matches_season("Jujutsu Kaisen III", 3) is True
    assert title_matches_season("Jujutsu Kaisen Third Season", 3) is True
    
    # Non-matching
    assert title_matches_season("Jujutsu Kaisen Season 2", 3) is False
    assert title_matches_season("Jujutsu Kaisen", 3) is False


@patch("simkl_mps.season_resolver.query_simkl_search")
@patch("simkl_mps.season_resolver.verify_episode_exists")
def test_resolve_season_entry_exact_match(mock_verify, mock_search):
    mock_verify.return_value = True
    
    # Mock search results representing Jujutsu Kaisen seasons
    mock_search.side_effect = [
        # Results for query 'Jujutsu Kaisen Season 3'
        [
            {
                "title": "Jujutsu Kaisen Season 3",
                "ids": {
                    "simkl": 333333
                }
            }
        ],
        # Results for query 'Jujutsu Kaisen 3rd Season'
        [],
        # Results for query 'Jujutsu Kaisen'
        [
            {
                "title": "Jujutsu Kaisen",
                "ids": {
                    "simkl": 111111
                }
            },
            {
                "title": "Jujutsu Kaisen 2nd Season",
                "ids": {
                    "simkl": 222222
                }
            }
        ]
    ]

    result = resolve_season_entry(
        title="Jujutsu Kaisen",
        season=3,
        episode=4,
        client_id="cid",
        access_token="token",
        media_type="anime"
    )

    assert result is not None
    assert result["simkl_id"] == 333333
    assert result["title"] == "Jujutsu Kaisen Season 3"
    assert result["type"] == "anime"


@patch("simkl_mps.season_resolver.query_simkl_search")
@patch("simkl_mps.season_resolver.verify_episode_exists")
def test_resolve_season_entry_no_match_found(mock_verify, mock_search):
    # If no results at all are returned by the search
    mock_search.return_value = []

    result = resolve_season_entry(
        title="Unknown Show",
        season=2,
        episode=1,
        client_id="cid",
        access_token="token",
        media_type="anime"
    )

    assert result is None


@patch("simkl_mps.season_resolver.get_episodes")
def test_verify_episode_exists_success(mock_get_episodes):
    # Mocked list of episodes returning from /anime/{id}/episodes
    mock_get_episodes.return_value = [
        {"episode": 1, "title": "Episode 1"},
        {"episode": 2, "title": "Episode 2"},
        {"episode": 3, "title": "Episode 3"},
        {"episode": 4, "title": "Episode 4"}
    ]

    assert verify_episode_exists(123, 4, "cid", "token", "anime") is True
    assert verify_episode_exists(123, 5, "cid", "token", "anime") is False


@patch("simkl_mps.season_resolver.get_episodes")
def test_verify_episode_exists_empty(mock_get_episodes):
    mock_get_episodes.return_value = []
    assert verify_episode_exists(123, 4, "cid", "token", "anime") is False


@patch("simkl_mps.season_resolver.query_simkl_search")
@patch("simkl_mps.season_resolver.get_episodes")
def test_resolve_season_entry_verification_filtering(mock_get_episodes, mock_search):
    # Test case where one candidate fails verification and the resolver moves to the next valid one.
    # We search for Season 3.
    mock_search.return_value = [
        {
            "title": "Jujutsu Kaisen Season 3",
            "ids": {"simkl": 333}
        },
        {
            "title": "Jujutsu Kaisen Season 3 Special",
            "ids": {"simkl": 444}
        }
    ]
    
    # ID 333 has episodes 1,2,3 (episode 4 does not exist)
    # ID 444 has episodes 1,2,3,4 (episode 4 exists!)
    mock_get_episodes.side_effect = [
        [{"episode": 1}, {"episode": 2}, {"episode": 3}], # for ID 333
        [{"episode": 1}, {"episode": 2}, {"episode": 3}, {"episode": 4}] # for ID 444
    ]

    result = resolve_season_entry(
        title="Jujutsu Kaisen",
        season=3,
        episode=4,
        client_id="cid",
        access_token="token",
        media_type="anime"
    )

    # It should skip ID 333 because verification for episode 4 failed, and resolve to ID 444
    assert result is not None
    assert result["simkl_id"] == 444
    assert result["title"] == "Jujutsu Kaisen Season 3 Special"


@patch("simkl_mps.season_resolver.query_simkl_search")
@patch("simkl_mps.season_resolver.get_episodes")
@patch("simkl_mps.media_scrobbler.is_internet_connected", return_value=True)
def test_jujutsu_kaisen_s03e04_integration_end_to_end(mock_inet, mock_get_episodes, mock_search, tmp_path):
    # This is our integration test: Resolve Jujutsu Kaisen S03E04 end-to-end and assert correct ID and episode.
    
    # 1. Mock the search query calls
    # S03E04 will trigger clean_show_title = "Jujutsu Kaisen"
    # It will try queries: "Jujutsu Kaisen Season 3", "Jujutsu Kaisen 3rd Season", "Jujutsu Kaisen"
    def search_mock_side_effect(query, client_id, access_token, media_type):
        if "Season 3" in query:
            return [
                {
                    "title": "Jujutsu Kaisen Season 3",
                    "ids": {"simkl": 3333}
                }
            ]
        elif "3rd Season" in query:
            return []
        elif query == "Jujutsu Kaisen":
            return [
                {
                    "title": "Jujutsu Kaisen",
                    "ids": {"simkl": 1111}
                }
            ]
        return []
        
    mock_search.side_effect = search_mock_side_effect
    
    # 2. Mock episode lists
    # ID 3333 has episode 4
    # ID 1111 also has episode 4, but we prioritize 3333 because of season match
    def episodes_mock_side_effect(simkl_id, client_id, access_token, media_type):
        if simkl_id == 3333:
            return [{"episode": 1}, {"episode": 2}, {"episode": 3}, {"episode": 4}]
        elif simkl_id == 1111:
            return [{"episode": 1}, {"episode": 2}, {"episode": 3}, {"episode": 4}]
        return []
        
    mock_get_episodes.side_effect = episodes_mock_side_effect

    # Initialize MediaScrobbler
    scrobbler = MediaScrobbler(app_data_dir=tmp_path, client_id="cid_123", access_token="token_123")
    scrobbler._process_simkl_search_result = MagicMock()

    # Trigger movie identification on Jujutsu Kaisen S03E04
    scrobbler._identify_movie("Jujutsu Kaisen S03E04")

    # Assert that search resolved to the correct Jujutsu Kaisen Season 3 ID (3333)
    # Wrap raw_result as expected in results: {"show": best_item}
    expected_result_show = {
        "show": {
            "title": "Jujutsu Kaisen Season 3",
            "ids": {"simkl": 3333}
        }
    }
    
    scrobbler._process_simkl_search_result.assert_called_once_with(
        expected_result_show,
        "Jujutsu Kaisen S03E04",
        "jujutsu kaisen s03e04",
        "simkl_search_resolver_anime"
    )

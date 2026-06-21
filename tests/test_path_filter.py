"""Unit tests for the pure path allow/deny helpers in utils.path_filter.

Uses lowercase absolute paths so results are identical on case-sensitive
(Linux CI) and case-insensitive (macOS) filesystems.
"""
from simkl_mps.utils.path_filter import (
    is_path_allowed,
    _contains_glob,
    _is_path_within_directory,
)


# --- low-level helpers --------------------------------------------------------

def test_contains_glob():
    assert _contains_glob("/data/*.mkv") is True
    assert _contains_glob("season?.mkv") is True
    assert _contains_glob("/data/movies/a.mkv") is False


def test_is_path_within_directory():
    assert _is_path_within_directory("/data/movies/a.mkv", "/data/movies") is True
    assert _is_path_within_directory("/data/movies", "/data/movies") is True  # equal
    assert _is_path_within_directory("/data/other/a.mkv", "/data/movies") is False
    assert _is_path_within_directory("/data", "/data/movies") is False  # shorter
    assert _is_path_within_directory("", "/data") is False


# --- is_path_allowed ----------------------------------------------------------

def test_allow_by_default_when_no_rules():
    assert is_path_allowed("/data/movies/a.mkv") is True


def test_none_path_is_allowed():
    assert is_path_allowed(None) is True


def test_deny_directory_prefix():
    assert is_path_allowed("/data/movies/a.mkv", deny_dirs=["/data/movies"]) is False
    assert is_path_allowed("/data/shows/a.mkv", deny_dirs=["/data/movies"]) is True


def test_allow_list_restricts_to_listed_dirs():
    assert is_path_allowed("/data/movies/a.mkv", allow_dirs=["/data/movies"]) is True
    assert is_path_allowed("/data/other/a.mkv", allow_dirs=["/data/movies"]) is False


def test_deny_wins_over_allow():
    # Inside the allow dir but also inside a deny sub-dir -> denied.
    assert is_path_allowed(
        "/data/movies/private/a.mkv",
        allow_dirs=["/data/movies"],
        deny_dirs=["/data/movies/private"],
    ) is False


def test_deny_glob_match_anywhere():
    assert is_path_allowed("/data/downloads/a.mkv", deny_dirs=["**/downloads/*"]) is False

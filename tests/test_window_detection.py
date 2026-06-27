"""Unit tests for the pure helpers in window_detection.

These cover deterministic logic only (player matching, macOS output parsing,
size formatting, non-video filtering) — no real OS window calls are made.
"""
import pytest

import simkl_mps.window_detection as wd
from simkl_mps.window_detection import (
    is_video_player,
    format_file_size,
    parse_filename_from_path,
    parse_media_title,
    _parse_macos_tab_window_output,
    _parse_macos_legacy_applescript_pairs,
    _merge_macos_window_lists,
)


# --- is_video_player ----------------------------------------------------------

@pytest.mark.parametrize("platform, info, expected", [
    ("linux", {"process_name": "vlc"}, True),
    ("linux", {"process_name": "mpv"}, True),
    ("linux", {"process_name": "firefox"}, False),
    ("windows", {"process_name": "vlc.exe"}, True),
    ("windows", {"process_name": "notepad.exe"}, False),
    ("darwin", {"process_name": "", "app_name": "IINA"}, True),
    ("darwin", {"process_name": "", "app_name": "Safari"}, False),
])
def test_is_video_player(monkeypatch, platform, info, expected):
    monkeypatch.setattr(wd, "PLATFORM", platform)
    assert is_video_player(info) is expected


def test_is_video_player_none_or_empty():
    assert is_video_player(None) is False
    assert is_video_player({}) is False


# --- format_file_size ---------------------------------------------------------

@pytest.mark.parametrize("size, expected", [
    (None, "Unknown"),
    (0, "0 B"),
    (512, "512 B"),
    (1024, "1.00 KB"),
    (1024 * 1024, "1.00 MB"),
    (1024 * 1024 * 1024, "1.00 GB"),
    (1536, "1.50 KB"),
])
def test_format_file_size(size, expected):
    assert format_file_size(size) == expected


# --- macOS tab-delimited window output ---------------------------------------

def test_parse_macos_tab_window_output():
    output = "VLC\tMovie.mkv\nFinder\tDocuments\n"
    assert _parse_macos_tab_window_output(output) == [
        ("VLC", "Movie.mkv"),
        ("Finder", "Documents"),
    ]


def test_parse_macos_tab_window_output_skips_malformed():
    # Lines without a tab, or with an empty side, are dropped.
    output = "no-tab-here\nVLC\tMovie.mkv\n\t\nApp\t\n"
    assert _parse_macos_tab_window_output(output) == [("VLC", "Movie.mkv")]


def test_parse_macos_tab_window_output_empty():
    assert _parse_macos_tab_window_output("") == []
    assert _parse_macos_tab_window_output(None) == []


# --- macOS legacy AppleScript list output ------------------------------------

def test_parse_macos_legacy_applescript_pairs_quoted():
    output = '{"VLC", "Movie"}, {"Finder", "Desktop"}'
    assert _parse_macos_legacy_applescript_pairs(output) == [
        ("VLC", "Movie"),
        ("Finder", "Desktop"),
    ]


def test_parse_macos_legacy_applescript_pairs_empty():
    assert _parse_macos_legacy_applescript_pairs("") == []
    assert _parse_macos_legacy_applescript_pairs(None) == []


# --- macOS window list merge (dedup by process_name + title) -----------------

def test_merge_macos_window_lists_dedups():
    primary = [{"process_name": "VLC", "title": "Movie"}]
    secondary = [
        {"process_name": "VLC", "title": "Movie"},   # duplicate, dropped
        {"process_name": "VLC", "title": "Other"},    # new, kept
    ]
    merged = _merge_macos_window_lists(primary, secondary)
    assert merged == [
        {"process_name": "VLC", "title": "Movie"},
        {"process_name": "VLC", "title": "Other"},
    ]


# --- parse_filename_from_path (deterministic guard branches) ------------------

def test_parse_filename_from_path_rejects_non_video():
    assert parse_filename_from_path("/movies/readme.txt") is None


def test_parse_filename_from_path_empty():
    assert parse_filename_from_path("") is None
    assert parse_filename_from_path(None) is None


# --- parse_media_title: multi-word titles with hyphen separators ---------------

def test_hyphenated_title_is_not_truncated():
    # Regression: "Avatar - The Last Airbender" must not be truncated to "Avatar"
    # (which previously misidentified to an unrelated show).
    info = parse_media_title("Avatar - The Last Airbender (2024) - S02E05")
    assert "Last Airbender" in info["title"]
    assert info["title"] != "Avatar"
    assert info["season"] == 2
    assert info["episode"] == 5


def test_hyphenated_word_preserved():
    # A hyphen inside a word (no surrounding spaces) must stay intact.
    info = parse_media_title("Spider-Man (2002)")
    assert "Spider-Man" in info["title"]


def test_simple_show_title_and_episode():
    info = parse_media_title("Breaking Bad - S05E14")
    assert info["title"] == "Breaking Bad"
    assert info["season"] == 5
    assert info["episode"] == 14

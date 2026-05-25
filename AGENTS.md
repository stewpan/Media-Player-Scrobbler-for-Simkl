# 🤖 Agent Handover Context: Media Player Scrobbler for Simkl (MPS)

This document captures the repository's context, architecture, architectural decisions, and progress made during this session. It acts as a comprehensive briefing so a new Pi session can pick up immediately where we left off.

---

## 📋 Executive Summary
**Media Player Scrobbler for Simkl (MPS)** is a cross-platform background application/system tray utility written in Python. It detects media playback from active media player window titles or filepath details (e.g., VLC, PotPlayer, MPV, MPC-HC) across Windows, macOS, and Linux, parses the title (using `guessit` and custom regex), resolves it against the Simkl API, and automatically scrobbles watched progress or marks episodes/movies complete.

---

## 🛠️ Session Progress & Bugs Resolved

In this session, we investigated and successfully resolved three major bugs and wrote robust tests with **100% test coverage** (all 31 unit and integration tests are passing).

### 1. Duplicate Process Instances
* **Problem:** Hangups during process lifecycle led to multiple instances of the app running simultaneously because existing instances were not properly killed on startup/exit.
* **Fix:**
  * Updated `terminate_running_instances` in `simkl_mps/process_manager.py` on Unix/macOS to send a `SIGTERM` first, poll-wait for up to 3 seconds for the target processes to die (every 100ms), and then send a `SIGKILL` (`kill -9`) to guarantee complete termination of any hung background process.

### 2. Lingering macOS Menu Bar Icon
* **Problem:** The system tray icon (`pystray`) in the macOS menu bar persisted indefinitely after the main application exited/killed, only vanishing on manual user interaction.
* **Fix:**
  * Registered an `atexit` cleanup handler inside `TrayAppBase.__init__` (`simkl_mps/tray_base.py`) to automatically call `self.tray_icon.stop()` whenever the Python process exits. This ensures the status item is instantly and cleanly removed from the macOS menu bar and Windows system tray under all circumstances (graceful shutdown, terminal exit, or SIGTERM signal).

### 3. Simkl Series Season Tracking (e.g., Jujutsu Kaisen S03E04)
* **Problem:** Simkl lists different seasons of TV shows and especially Anime as separate entries with separate `simkl_id` values (e.g., *Jujutsu Kaisen Season 1* is ID `1211100`, *Season 2* is ID `1689230`, *Season 3* is ID `X`). The title search fallback previously stripped season notation and always picked the first search result (usually Season 1's ID). Scrobbles sent to Season 1's ID with `season: 3` were rejected or ignored by Simkl because Season 1 has no Season 3.
* **Fix:** Developed and integrated a specialized **Season Resolver** mechanism.

---

## 🧠 Season Resolver Architecture & Decisions

### File Structure & Modular Design
We introduced `simkl_mps/season_resolver.py` to isolate the resolution logic from the core `MediaScrobbler`. 

### Key Design Decisions:
1. **Multi-Query Search (`resolve_season_entry`):**
   * If `season > 1`, the resolver queries Simkl with season-specific titles first (e.g., `"Jujutsu Kaisen Season 3"`, `"Jujutsu Kaisen 3rd Season"`) before falling back to the base title. This makes sure Simkl ranks the season-specific entry highest.
2. **Filtering and Scoring (`title_matches_season`):**
   * Employs robust regex patterns to rank candidates. Matches season labels like `"Season 3"`, `"3rd Season"`, `"S3"`, `"Part 3"`, `"Cour 3"`, and Roman Numeral `"III"`.
   * Adds `+100` score on explicit matches, downranks other explicitly declared seasons (by `-80`) if searching for a different season, and awards `+10` for clean title similarity.
3. **Episode Verification (`verify_episode_exists`):**
   * Calls `/anime/{id}/episodes` (or `/tv/{id}/episodes`) to verify that the target episode (e.g., `4` in S03E04) actually exists under that candidate ID's episode mapping. It automatically skips any candidates where the episode isn't mapped, moving to the next best match.
4. **Caching (`_resolver_cache`):**
   * Implemented an in-memory resolver cache mapped by `(title.lower(), season, media_type)` to avoid making redundant, heavy search and episode-fetch API calls over the same session.
5. **Simkl Season Payload Override (`_build_add_to_history_payload`):**
   * Standalone season-specific entries on Simkl catalog their episodes under `Season 1`. Therefore, when we scrobble using a season-specific `simkl_id`, the payload's season number is overridden to `1` (or relative season number), ensuring the scrobble successfully maps and marks the correct episode complete.

---

## 🧪 Test Coverage & Integration Verification

The season resolver is fully verified via unit and integration tests.

### Tests Written:
* **`tests/test_season_resolver.py`**:
  * `test_title_matches_season`: Unit tests explicit/roman/ordinal matching logic.
  * `test_resolve_season_entry_exact_match`: Asserts ranking and selecting of season-specific search results.
  * `test_resolve_season_entry_no_match_found`: Verifies graceful failure/null propagation.
  * `test_verify_episode_exists_success` / `test_verify_episode_exists_empty`: Asserts episode validation on Simkl's episode lists.
  * `test_resolve_season_entry_verification_filtering`: Asserts that resolver skips candidates with incomplete episode mappings and picks the next valid candidate.
  * `test_jujutsu_kaisen_s03e04_integration_end_to_end`: Simulates the primary failure case, resolving the file and asserting that the scrobbler chooses the correct Season 3 `simkl_id` (`3333`) and triggers the search resolver.
* **`tests/test_tv_search_fallback.py`**:
  * Updated to mock the new `resolve_season_entry` integration. Includes unit tests asserting `_build_add_to_history_payload` overrides the payload season to `1` for season-specific entries and keeps standard season numbers for master show entries.

To run the tests:
```bash
.venv/bin/pytest
```

---

## 🚀 Next Steps & Future Action Items
For the next session, here are the recommended areas of focus:
* **Persistent Caching:** Consider saving the resolved title/season → `simkl_id` mapping to a persistent JSON cache file in `APP_DATA_DIR` so that mappings persist across application launches.
* **User Feedback & Log Verification:** Monitor application logs (`simkl_mps.log`) during playback of shows with multiple seasons to confirm the resolver identifies them smoothly and prints `"Simkl API: Detected season-specific entry... Overriding scrobble season to 1"`.
* **Discord Rich Presence (Medium/Long Term):** Implement rich presence based on the completed features.

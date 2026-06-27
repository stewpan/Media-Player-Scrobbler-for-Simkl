# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.8.2] - 2026-06-27

### Added
- A confidence guard on title identification: if Simkl's best match for a movie or
  live-action show is clearly unrelated to what was played (near-zero title overlap), it is
  rejected instead of scrobbling a wrong guess, and a notification is shown. Anime are
  exempt because they legitimately have very different alternate titles (e.g. "Attack on
  Titan" vs "Shingeki no Kyojin"). (#21)

## [2.8.1] - 2026-06-27

### Fixed
- Rewatch detection no longer assumes you watch episodes strictly in order. For titles
  without a precise per-episode list, it now uses Simkl's progress pointers
  (`next_to_watch` / `last_watched`): everything before the next-to-watch frontier counts
  as watched, so a genuine first watch (at or beyond the frontier — e.g. a stand-alone
  episode of a comedy or long-running show) is never wrongly skipped. Shows are compared
  season-aware; anime (split one id per cour) by episode number. (#20)

## [2.8.0] - 2026-06-27

### Fixed
- **Rewatch detection now works for anime and split-per-season titles.** Simkl splits many
  anime franchises into one id per season/cour and exposes only a `watched_episodes_count`
  (not a per-episode list), so the local copy previously had no episode data for ~99% of
  anime and rewatches went undetected. The local copy now stores the watched-episode count
  and uses it (episodes 1..count) when a per-episode list isn't available, and matches on
  episode number alone for single-season ids (where the detected "franchise" season won't
  line up with Simkl's internal numbering). Multi-season ids (e.g. Avatar 2024) stay
  season-strict. The snapshot format is bumped to v2 (old snapshots load and are upgraded
  on the next sync). (#19)

## [2.7.4] - 2026-06-27

### Fixed
- **Rewatch detection is now season-strict.** An episode number was matched across seasons,
  so e.g. watching S02E06 was wrongly flagged as a rewatch (and skipped) just because
  S01E06 had been seen. When the season is known, only an exact (season, episode) match
  counts — both against the local Simkl copy and the local watch history. (#18)

### Added
- The app now logs its version, Python version and platform at startup
  (`simkl-mps vX.Y.Z | Python ... | platform ...`), so a glance at the log shows what's
  running. (#18)

## [2.7.3] - 2026-06-27

### Fixed
- The season resolver crashed (`'str' object has no attribute 'get'`) when Simkl's
  episodes endpoint returned a non-list payload, aborting identification. It now guards
  against that shape and falls back to title/year ranking.
- **Release year is now used to pick the right title** when several versions share a name
  (e.g. *Avatar: The Last Airbender* 2005 vs the 2024 Netflix series). The year is parsed
  from the title (or passed in) and strongly weighted in candidate ranking. (#17)

## [2.7.2] - 2026-06-27

### Fixed
- Simkl's file search (`/search/file`) sometimes maps a file to a completely unrelated
  title (e.g. an Avatar episode identified as "ZB1's ROCK Festival"), which was accepted
  blindly and scrobbled the wrong show. File-search results are now validated against the
  title parsed from the filename and rejected (falling back to title search) when they
  don't match. This is the real cause of the misidentification 2.7.1 partially addressed. (#16)

## [2.7.1] - 2026-06-21

### Fixed
- Titles containing a hyphen separator (e.g. `Avatar - The Last Airbender (2024) - S02E05`)
  were truncated to the first segment ("Avatar") before identification, because guessit
  treats `" - "` as a title separator — leading to severe misidentification (matching an
  unrelated show). The title is now normalized (hyphen separators → spaces) before parsing,
  so the full title is preserved. Hyphenated words like "Spider-Man" are unaffected. (#15)

## [2.7.0] - 2026-06-21

### Added
- **Local copy of your Simkl watched library.** The app now keeps a local snapshot of all
  the movies and show/anime episodes you've watched on Simkl
  (`simkl_watched_library.json` in the data dir), refreshed in the background and only when
  `/sync/activities` reports a change. Rewatch detection uses this copy as its comparison
  material, so it now works **offline** and without a network call per scrobble. The
  dashboard shows the copy's size and last sync, and a new `GET /api/library` exposes it. (#14)

## [2.6.0] - 2026-06-21

### Added
- **Rewatch detection.** Before scrobbling, the app now checks whether you've already
  watched the movie/episode — first in the local history, then against your Simkl library
  (`/sync/all-items`, cached and refreshed only when `/sync/activities` reports a change).
  When a rewatch is detected it is flagged in the dashboard ("Rewatch" badge) and, with the
  new `skip_rewatch_scrobble` setting (default on), is **not** re-scrobbled so your Simkl
  watch count isn't incremented again. Toggle it off in Settings to count rewatches. (#13)

## [2.5.1] - 2026-06-21

### Fixed
- The built web dashboard (`simkl_mps/web/dist`) was never bundled in packages, so
  installs showed "Dashboard not built" even when the front-end had been built — the
  assets are gitignored and poetry-core excludes VCS-ignored files. Force-include them via
  `[tool.poetry] include`, and build the front-end (`npm run build`) in the PyPI publish
  workflow so released wheels ship a working dashboard. (#12)

## [2.5.0] - 2026-06-21

### Changed
- **Data directory moved to `~/.simkl-mps`** (a single hidden folder in your home),
  replacing the confusing developer-named `~/kavin/simkl-mps` location. Existing data
  (credentials, settings, watch history, cache) is **migrated automatically** on first
  run — no re-authentication needed. Legacy `~/kavin/simkl-mps` and
  `~/kavinthangavel/simkl-mps` are both handled. (#11)
- Neutralized internal OS identifiers that embedded the old name: the Windows registry
  key (`Software\simkl-mps\…`), the notification AppUserModelID (`simkl-mps`), and the
  macOS updater LaunchAgent (`com.simkl-mps.updater`) — also migrated automatically.
- Removed the now-unused `user_subdir` setting.

## [2.4.1] - 2026-06-21

### Fixed
- `simkl-mps --version` / `-v` no longer errors with "the following arguments are
  required: command". The top-level version flag now prints version info and exits, and
  running `simkl-mps` with no command prints help instead of erroring. (#10)

## [2.4.0] - 2026-06-21

### Added
- **Local web dashboard** — a browser UI served on `http://127.0.0.1:5555` by an
  embedded server inside the running app. Three pages: **Dashboard** (live now-playing
  with progress, plus watch stats), **History** (searchable/filterable watch history),
  and **Settings** (completion threshold, notifications, auto-sync interval, directory
  filters, and Simkl sign-in). Open it from the tray's new **Open Dashboard** item or by
  visiting the URL. Localhost-only and enabled by default; see
  [docs/web-dashboard.md](docs/web-dashboard.md). (#6, #7, #8)
- **Browser-based Simkl sign-in** for the dashboard via the device-code flow — the page
  shows the PIN and verification link and completes automatically once you authorize. (#7)
- **Settings:** `web_ui_enabled` (default `true`) and `web_ui_port` (default `5555`) to
  control the dashboard. (#6)
- **Persistent season-resolver cache** — resolved show/season → Simkl-id mappings are now
  saved to `season_resolver_cache.json` in the app data directory and reused across
  restarts, avoiding repeated lookups for multi-season shows and anime. (#4)
- **Automated test suite** running on CI (pytest, Python 3.10 and 3.13) — grown from none
  to 115 tests covering the scrobbler core, window detection, path filters, the season
  resolver, credentials, and the web API. (#1, #5)

### Changed
- Importing the `simkl_mps` package no longer pulls in the GUI/tray modules, so it is safe
  to import in headless environments (and on the correct platform's tray at runtime). (#2)

### Fixed
- Replaced the deprecated `datetime.utcnow()` used when building scrobble payloads with a
  timezone-aware UTC timestamp. (#3)
- macOS VLC window detection, credential loading and Simkl `412` handling, and
  Simkl season-level tracking for multi-season shows/anime.

[Unreleased]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.8.2...HEAD
[2.8.2]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.8.1...v2.8.2
[2.8.1]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.8.0...v2.8.1
[2.8.0]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.7.4...v2.8.0
[2.7.4]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.7.3...v2.7.4
[2.7.3]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.7.2...v2.7.3
[2.7.2]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.7.1...v2.7.2
[2.7.1]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.7.0...v2.7.1
[2.7.0]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.6.0...v2.7.0
[2.6.0]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.5.1...v2.6.0
[2.5.1]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.5.0...v2.5.1
[2.5.0]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.4.1...v2.5.0
[2.4.1]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.4.0...v2.4.1
[2.4.0]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/releases/tag/v2.4.0

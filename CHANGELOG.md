# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.7.0...HEAD
[2.7.0]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.6.0...v2.7.0
[2.6.0]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.5.1...v2.6.0
[2.5.1]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.5.0...v2.5.1
[2.5.0]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.4.1...v2.5.0
[2.4.1]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.4.0...v2.4.1
[2.4.0]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/releases/tag/v2.4.0

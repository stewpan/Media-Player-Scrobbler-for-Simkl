# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/compare/v2.4.0...HEAD
[2.4.0]: https://github.com/ByteTrix/Media-Player-Scrobbler-for-Simkl/releases/tag/v2.4.0

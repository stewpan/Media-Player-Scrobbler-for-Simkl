# 🌐 Web Dashboard

MPS for SIMKL includes a small **web dashboard** that runs locally while the app is
running. It gives you a live view of what's playing, your watch history, and the most
common settings — all from your browser, on any platform.

## Opening it

- **From the tray:** right-click the tray icon → **Open Dashboard**.
- **Directly:** open **`http://127.0.0.1:5555`** in your browser.

The dashboard is served by the app itself, so it's only available while MPS for SIMKL is
running (`simkl-mps tray` or `simkl-mps start`).

## Pages

### Dashboard
- **Now playing** — the currently tracked title (with season/episode for shows and anime),
  the playback state (playing / paused / stopped), and a progress bar toward the
  completion threshold.
- **Stats** — counts of movies, shows, and anime you've watched.

Updates live (polls every couple of seconds) — no need to refresh.

### History
- A searchable, type-filterable table of everything in your local watch history
  (movies, shows, anime), with watched dates and season/episode.

### Settings
- **Completion threshold** — the percentage of a title you must watch before it's marked
  complete.
- **Notifications** — turn desktop notifications on or off.
- **Skip rewatches** — when on (default), items you've already watched (locally or on
  Simkl) are flagged as a rewatch and not scrobbled again, so your Simkl watch count isn't
  incremented. Turn it off to count every rewatch. The app keeps a **local copy of your
  Simkl watched library** (`simkl_watched_library.json`), refreshed in the background, which
  is used as the comparison material and lets rewatch detection work offline.
- **Auto-sync interval** — how often the offline backlog is synced.
- **Directory filters** — allow/deny lists controlling which folders are scrobbled.
- **Simkl account** — sign in via the browser-based device-code flow: click **Connect to
  Simkl**, then enter the shown code at the Simkl link. The page detects completion
  automatically.

Changes are saved immediately and use the same settings file (`settings.json`) as the tray.

## Configuration

Two settings (in `settings.json`, or editable via the tray / dashboard) control it:

| Setting | Default | Description |
|---------|---------|-------------|
| `web_ui_enabled` | `true` | Whether the dashboard server runs at all. |
| `web_ui_port` | `5555` | The localhost port it listens on. |

If the port is already in use, the app logs a warning and simply skips the dashboard — your
scrobbling is never affected.

## Security

The dashboard binds to **`127.0.0.1` (localhost) only**, so it is reachable solely from the
computer running the app and is **not** exposed to your network. There is no password — it
relies on localhost being private to your machine. Remote/LAN access is intentionally not
supported in this version.

## Building from source

Packaged builds (the Windows installer and release binaries) include the dashboard. If you
installed from source (e.g. `pip install -e .` from a checkout), build the front-end once:

```bash
cd webui
npm install
npm run build
```

This produces `simkl_mps/web/dist/`, which the app serves. Until it's built, opening the
dashboard shows a short "run `npm run build`" message; the JSON API under `/api/` still
works.

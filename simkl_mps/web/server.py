"""Embedded Flask web server for the local dashboard.

Runs in a daemon thread inside the background app process and binds to
127.0.0.1 only. Designed to never take the app down: a bind failure (e.g. the
port is already in use) is logged and the server simply doesn't run.
"""
import logging
import threading
from pathlib import Path

from flask import Flask, send_from_directory

from simkl_mps.web.api import create_api_blueprint

logger = logging.getLogger(__name__)

# Built React/Vite assets are bundled here (gitignored; produced by `npm run build`).
DIST_DIR = Path(__file__).resolve().parent / "dist"

_MISSING_DIST_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Simkl MPS Dashboard</title>
<style>body{font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;padding:0 1rem;line-height:1.6}code{background:#eee;padding:.1rem .3rem;border-radius:.2rem}</style>
</head><body>
<h1>Dashboard not built</h1>
<p>The web UI front-end has not been built yet. From the project root run:</p>
<pre><code>cd webui &amp;&amp; npm install &amp;&amp; npm run build</code></pre>
<p>The JSON API is already available under <code>/api/</code>.</p>
</body></html>"""


class _ScrobblerContext:
    """Adapts a running SimklScrobbler into the accessor API the blueprint needs."""

    def __init__(self, scrobbler_app):
        self._app = scrobbler_app

    def get_scrobbler(self):
        monitor = getattr(self._app, "monitor", None)
        return getattr(monitor, "scrobbler", None) if monitor else None

    def is_monitor_running(self):
        monitor = getattr(self._app, "monitor", None)
        return bool(getattr(monitor, "running", False)) if monitor else False

    def get_watch_history_manager(self):
        return getattr(self._app, "watch_history_manager", None)

    def get_backlog_cleaner(self):
        scrobbler = self.get_scrobbler()
        return getattr(scrobbler, "backlog_cleaner", None) if scrobbler else None


def create_app(context, dist_dir=DIST_DIR):
    """Create the Flask application serving the API and the SPA."""
    app = Flask(__name__, static_folder=None)
    app.register_blueprint(create_api_blueprint(context), url_prefix="/api")

    dist_dir = Path(dist_dir)

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def serve_spa(path):
        # Serve a real built asset if it exists, else fall back to index.html
        # so client-side routing works. If the build is missing, show guidance.
        if path:
            candidate = (dist_dir / path)
            if candidate.is_file():
                return send_from_directory(dist_dir, path)
        index = dist_dir / "index.html"
        if index.is_file():
            return send_from_directory(dist_dir, "index.html")
        return _MISSING_DIST_HTML, 200

    return app


class WebServer:
    """Owns the werkzeug server + its daemon thread."""

    def __init__(self, scrobbler_app, host="127.0.0.1", port=5555, dist_dir=DIST_DIR):
        self.host = host
        self.port = port
        self._app = create_app(_ScrobblerContext(scrobbler_app), dist_dir=dist_dir)
        self._server = None
        self._thread = None

    def start(self):
        """Start serving in a daemon thread. Returns True on success."""
        if self._thread is not None:
            return True
        try:
            # Imported lazily so importing this module never requires a free port.
            from werkzeug.serving import make_server
            self._server = make_server(self.host, self.port, self._app, threaded=True)
        except (OSError, SystemExit) as e:
            # werkzeug raises OSError on bind failure, and on some versions calls
            # sys.exit() (SystemExit) when the port is in use. Neither must ever
            # take down the host app — the dashboard is optional.
            logger.warning(
                f"Web dashboard could not bind {self.host}:{self.port} ({e!r}); "
                f"dashboard disabled for this session."
            )
            self._server = None
            return False
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="WebServer", daemon=True
        )
        self._thread.start()
        logger.info(f"Web dashboard available at http://{self.host}:{self.port}")
        return True

    def stop(self):
        """Shut the server down cleanly (safe to call if never started)."""
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception as e:  # pragma: no cover - best-effort shutdown
                logger.debug(f"Error shutting down web server: {e}")
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._server = None
        self._thread = None

"""Embedded local web dashboard for Media Player Scrobbler for Simkl.

A lightweight Flask server runs inside the background app process and serves a
read-only dashboard plus a JSON API on 127.0.0.1. See ``server.WebServer``.
"""

from simkl_mps.web.server import WebServer

__all__ = ["WebServer"]

"""Importable ASGI factory used by the reload-capable development server."""

from __future__ import annotations

import os

from .application import PHFrame


def create_app() -> PHFrame:
    return PHFrame.from_file(os.environ.get("PHFRAME_CONFIG", "phframe.yaml"))

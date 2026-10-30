"""The local HTTP API and WebSocket of the runtime (FastAPI). See ``create_app``."""

from primum_runtime.api.app import create_app

__all__ = ["create_app"]

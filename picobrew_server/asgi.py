"""ASGI entry point for serving the Flask application with Uvicorn."""

from typing import cast

from a2wsgi import WSGIMiddleware
from a2wsgi.wsgi_typing import WSGIApp

from picobrew_server import create_app as create_flask_app


def create_app(config: dict | None = None) -> WSGIMiddleware:
    """Create an ASGI adapter around a fresh Flask application."""
    return WSGIMiddleware(cast(WSGIApp, create_flask_app(config).wsgi_app))

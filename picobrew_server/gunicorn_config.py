"""Gunicorn settings for serving the Zymatic.

Load with `gunicorn --config python:picobrew_server.gunicorn_config` or run the
`picobrew-server` command, which uses it. The repository's `gunicorn.conf.py`
re-exports these settings for existing deployments.
"""

from picobrew_server.gunicorn_compat import install as install_bare_lf_support

__all__ = ["wsgi_app", "bind", "workers", "worker_class", "timeout", "accesslog", "errorlog", "loglevel"]

# The Zymatic firmware terminates HTTP header lines with a bare LF, which
# gunicorn's pure-Python parser never accepts. See picobrew_server/gunicorn_compat.py.
install_bare_lf_support()

# WSGI app
wsgi_app = "picobrew_server:create_app()"

# Server socket: the machine always connects to port 80.
bind = "0.0.0.0:80"

# One machine needs little concurrency, and few workers keep SQLite lock contention low on a Pi.
workers = 2
worker_class = "sync"
timeout = 30

# Logging — write to stdout/stderr so the host's log collector picks them up
accesslog = "-"
errorlog = "-"
loglevel = "info"

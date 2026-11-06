import multiprocessing

from picobrew_server.gunicorn_compat import install as install_bare_lf_support

# The Zymatic firmware terminates HTTP header lines with a bare LF, which
# gunicorn's pure-Python parser never accepts. See picobrew_server/gunicorn_compat.py.
install_bare_lf_support()

# WSGI app
wsgi_app = "picobrew_server:create_app()"

# Server socket
bind = "0.0.0.0:80"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 30

# Logging — write to stdout/stderr so the host's log collector picks them up
accesslog = "-"
errorlog = "-"
loglevel = "info"

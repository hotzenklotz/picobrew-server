import multiprocessing

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

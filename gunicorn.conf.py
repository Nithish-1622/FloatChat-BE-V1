# Gunicorn configuration file for production deployment

import multiprocessing
import os

# Server socket
bind = os.getenv('GUNICORN_BIND', '0.0.0.0:8000')
backlog = 2048

# Worker processes
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
worker_connections = 1000
timeout = 120
keepalive = 5

# Process naming
proc_name = 'argo_ai'

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# Hook functions
def on_starting(server):
    """Called before master process is initialized."""
    pass

def on_reload(server):
    """Called after reloading."""
    pass

def worker_int(worker):
    """Called on SIGINT in worker."""
    pass

def worker_abort(worker):
    """Called when worker receives SIGABRT."""
    pass

def pre_fork(server, worker):
    """Called just before worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after worker is forked."""
    pass

def post_worker_init(worker):
    """Called after worker initialization."""
    pass

def worker_exit(server, worker):
    """Called when worker exits."""
    pass

def nworkers_changed(server, new_value, old_value):
    """Called when number of workers changes."""
    pass

def on_exit(server):
    """Called just before master process exits."""
    pass

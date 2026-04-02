# Worker Settings
import multiprocessing
workers = 2 * multiprocessing.cpu_count() + 1  # Dynamically determine the optimal workers
worker_class = 'gevent'  # Use gevent async workers
worker_connections = 1000  # Maximum concurrent connections per worker

# Server Settings
bind = "0.0.0.0:8000"  # Ensure it matches the Nginx proxy_pass setting
#forwarded_allow_ips = "*"  # Allow requests from Nginx
#proxy_protocol = True  # Enable proxy support

# Timeout Settings
timeout = 120  # Automatically restart workers if they take too long
graceful_timeout = 120  # Graceful shutdown for workers

# Keep-Alive Settings
keepalive = 2  # Keep connections alive for 2s

# Worker Restart Settings
max_requests = 1000  # Restart workers after processing 1000 requests
max_requests_jitter = 50  # Add randomness to avoid mass restarts

# Logging Settings
accesslog = "-"  # Log HTTP requests to a file
errorlog = "-"  # Log errors to a file
loglevel = "warning"  # Set log verbosity (debug, info, warning, error, critical)
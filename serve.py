#!/usr/bin/env python3
"""
Aegis Arena — development file server.

Serves the frontend on port 3000 with Cache-Control: no-cache headers
so that the browser always fetches the latest JavaScript files instead
of using stale cached versions.

Usage:
    python serve.py
"""

import os
from http.server import HTTPServer, SimpleHTTPRequestHandler


class NoCacheHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with no-cache headers on every response."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Suppress 304 noise; still print 200/404 for visibility
        code = args[1] if len(args) > 1 else ""
        if code not in ("304",):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    os.chdir(frontend_dir)
    server = HTTPServer(("", 3000), NoCacheHandler)
    print("Aegis Arena frontend  →  http://localhost:3000")
    print("(serving from frontend/ with no-cache headers)")
    print("Press Ctrl+C to stop.\n")
    server.serve_forever()

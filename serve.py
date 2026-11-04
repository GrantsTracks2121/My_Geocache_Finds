#!/usr/bin/env python3
"""
Geocache Day Replay - local web server.

Shows the pages in this folder (like `python3 -m http.server`) and also
saves your favourite days to favorites.json in this folder.

Usage (from Terminal, in this folder):
    python3 serve.py          # http://localhost:8002/day-replay.html
    python3 serve.py 8003     # use a different port

Stop it with Control-C. Only this Mac can reach it.
Uses only the Python standard library.
"""

import json
import os
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAVORITES_PATH = HERE / "favorites.json"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def read_favorites():
    try:
        data = json.loads(FAVORITES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = {}
    data.setdefault("days", [])
    return data


def write_favorites(data):
    tmp = FAVORITES_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, FAVORITES_PATH)


class Handler(SimpleHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # Make the browser check for fresh files every time, so a rebuilt
        # days.js shows up on a normal refresh.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/api/favorites":
            self.send_json(200, read_favorites())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/favorites":
            self.send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            incoming = json.loads(self.rfile.read(min(length, 1_000_000)))
            days = sorted({d for d in incoming.get("days", []) if isinstance(d, str) and DATE_RE.match(d)},
                          reverse=True)
        except (ValueError, AttributeError):
            self.send_json(400, {"error": "bad favourites data"})
            return
        data = read_favorites()
        data["days"] = days
        write_favorites(data)
        self.send_json(200, data)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(HERE)))
    print(f"Serving this folder at http://localhost:{port}/day-replay.html  (Control-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

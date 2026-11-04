#!/usr/bin/env python3
"""
My Geocache Finds - local web server.

Shows the pages in this folder (like `python3 -m http.server`) and also:
  - saves your favourite days to favorites.json
  - saves site-wide settings to settings.json
  - saves your trips (a name and a date range) to trips.json
  - takes a My Finds Pocket Query dropped on the Dashboard, saves it in this
    folder and rebuilds data/days.js with build_days.py

Usage (from Terminal, in this folder):
    python3 serve.py          # http://localhost:8002/
    python3 serve.py 8003     # use a different port

Stop it with Control-C. Only this Mac can reach it.
Uses only the Python standard library.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
FAVORITES_PATH = HERE / "favorites.json"
SETTINGS_PATH = HERE / "settings.json"
DAYS_PATH = HERE / "data" / "days.js"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Site-wide settings, their allowed values and defaults (changed on the Dashboard)
SETTINGS = {
    # Sequence of Daily Finds: "auto" plays the route when a day is chosen,
    # "manual" shows all the day's caches and waits for the Play button.
    "dailyFindsSequence": (("auto", "manual"), "auto"),
}

MAX_UPLOAD = 400 * 1024 * 1024     # bytes
# A new My Finds file with fewer than this share of the current logs is
# refused as probably the wrong Pocket Query.
MIN_SHARE = 0.8
upload_lock = threading.Lock()


def write_json(path, data):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_settings():
    try:
        saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        saved = {}
    return {key: saved.get(key) if saved.get(key) in allowed else default
            for key, (allowed, default) in SETTINGS.items()}


def read_favorites():
    try:
        data = json.loads(FAVORITES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = {}
    data.setdefault("days", [])
    return data


TRIPS_PATH = HERE / "trips.json"
TRIP_ID_RE = re.compile(r"^[a-z0-9-]{1,40}$")


def read_trips():
    try:
        data = json.loads(TRIPS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = {}
    data.setdefault("trips", [])
    return data


def clean_trip(t):
    """A trip from the page, checked: id, name, start, end (YYYY-MM-DD), note."""
    if not isinstance(t, dict):
        raise ValueError("bad trip")
    trip = {
        "id": str(t.get("id", "")),
        "name": str(t.get("name", "")).strip()[:100],
        "start": str(t.get("start", "")),
        "end": str(t.get("end", "")),
        "note": str(t.get("note", "")).strip()[:2000],
    }
    if not (TRIP_ID_RE.match(trip["id"]) and trip["name"]
            and DATE_RE.match(trip["start"]) and DATE_RE.match(trip["end"])
            and trip["start"] <= trip["end"]):
        raise ValueError("bad trip")
    return trip


def count_logs(days_js):
    """Number of logs in a days.js file (0 if there isn't one)."""
    try:
        return days_js.read_text(encoding="utf-8").count('"logId":')
    except FileNotFoundError:
        return 0


def safe_gpx_name(name):
    name = re.sub(r"[^\w.-]", "_", Path(name).name)
    return name if name.lower().endswith(".gpx") else name + ".gpx"


class UploadError(Exception):
    pass


def take_finds_upload(filename, tmp):
    """Turn an uploaded .gpx or .zip (saved at tmp) into a GPX file in this
    folder and rebuild days.js from it. Returns a summary for the page."""
    if filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(tmp) as z:
                gpxs = [i for i in z.infolist() if i.filename.lower().endswith(".gpx")
                        and not i.filename.lower().endswith("-wpts.gpx")]
                if not gpxs:
                    raise UploadError("There's no .gpx file inside that .zip.")
                member = max(gpxs, key=lambda i: i.file_size)
                gpx_name = safe_gpx_name(member.filename)
                data = z.read(member)
        except zipfile.BadZipFile:
            raise UploadError("That .zip file can't be opened.")
    elif filename.lower().endswith(".gpx"):
        gpx_name = safe_gpx_name(filename)
        data = tmp.read_bytes()
    else:
        raise UploadError("Please drop a .gpx or .zip file.")

    head = data[:4000]
    if b"<gpx" not in head or b"groundspeak" not in head:
        raise UploadError("That doesn't look like a Geocaching.com Pocket Query.")

    target = HERE / gpx_name
    old_target = target.with_name(target.name + ".bak") if target.exists() else None
    prev_days = DAYS_PATH.with_name("days.prev.js")
    before = count_logs(DAYS_PATH)
    if old_target:
        os.replace(target, old_target)
    if DAYS_PATH.exists():
        shutil.copy2(DAYS_PATH, prev_days)
    target.write_bytes(data)

    def undo(message):
        target.unlink(missing_ok=True)
        if old_target:
            os.replace(old_target, target)
        if prev_days.exists():
            os.replace(prev_days, DAYS_PATH)
        raise UploadError(message)

    try:
        run = subprocess.run([sys.executable, str(HERE / "build_days.py"), str(target)],
                             cwd=HERE, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        undo("Rebuilding took too long and was stopped. Your previous data is unchanged.")
    if run.returncode != 0:
        tail = (run.stderr or run.stdout).strip().splitlines()[-1:] or ["unknown error"]
        undo("Rebuilding failed (" + tail[0] + "). Your previous data is unchanged.")
    m = re.search(r"Wrote data/days\.js: (\d+) days, (\d+) stops", run.stdout)
    if not m:
        undo("Rebuilding didn't finish as expected. Your previous data is unchanged.")
    days, logs = int(m.group(1)), int(m.group(2))
    if before and logs < before * MIN_SHARE:
        undo(f"That file has only {logs:,} logs, far fewer than the {before:,} you have now, "
             "so it's probably not your My Finds Pocket Query. Nothing was changed.")

    if old_target:
        old_target.unlink(missing_ok=True)
    prev_days.unlink(missing_ok=True)
    return {"ok": True, "file": gpx_name, "days": days, "logs": logs, "previousLogs": before}


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
        path = self.path.split("?")[0]
        if path == "/api/favorites":
            self.send_json(200, read_favorites())
        elif path == "/api/settings":
            self.send_json(200, read_settings())
        elif path == "/api/trips":
            self.send_json(200, read_trips())
        else:
            super().do_GET()

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(min(length, 1_000_000)))

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/settings":
            self.post_settings()
        elif path == "/api/favorites":
            self.post_favorites()
        elif path == "/api/upload/finds":
            self.post_finds()
        elif path == "/api/trips":
            self.post_trips()
        else:
            self.send_json(404, {"error": "not found"})

    def post_trips(self):
        """Replace the list of trips with the one the page sends."""
        try:
            incoming = self.read_body().get("trips", [])
            trips = [clean_trip(t) for t in incoming]
            if len({t["id"] for t in trips}) != len(trips):
                raise ValueError("duplicate trip id")
        except (ValueError, AttributeError):
            self.send_json(400, {"error": "bad trips data"})
            return
        trips.sort(key=lambda t: (t["start"], t["end"]), reverse=True)
        write_json(TRIPS_PATH, {"trips": trips})
        self.send_json(200, {"trips": trips})

    def post_settings(self):
        try:
            incoming = self.read_body()
            settings = read_settings()
            for key, value in incoming.items():
                if key in SETTINGS and value in SETTINGS[key][0]:
                    settings[key] = value
        except (ValueError, AttributeError):
            self.send_json(400, {"error": "bad settings data"})
            return
        write_json(SETTINGS_PATH, settings)
        self.send_json(200, settings)

    def post_favorites(self):
        try:
            incoming = self.read_body()
            days = sorted({d for d in incoming.get("days", []) if isinstance(d, str) and DATE_RE.match(d)},
                          reverse=True)
        except (ValueError, AttributeError):
            self.send_json(400, {"error": "bad favourites data"})
            return
        data = read_favorites()
        data["days"] = days
        write_json(FAVORITES_PATH, data)
        self.send_json(200, data)

    def post_finds(self):
        filename = unquote(self.headers.get("X-Filename", ""))
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_UPLOAD:
            self.send_json(400, {"ok": False, "error": "That file is empty or too large."})
            return
        if not upload_lock.acquire(blocking=False):
            self.send_json(409, {"ok": False, "error": "Another file is still being loaded. Try again shortly."})
            return
        tmp = HERE / ".upload.tmp"
        try:
            with open(tmp, "wb") as out:
                left = length
                while left:
                    chunk = self.rfile.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    out.write(chunk)
                    left -= len(chunk)
            self.send_json(200, take_finds_upload(filename, tmp))
        except UploadError as err:
            self.send_json(200, {"ok": False, "error": str(err)})
        finally:
            tmp.unlink(missing_ok=True)
            upload_lock.release()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(HERE)))
    print(f"Serving this folder at http://localhost:{port}/  (Control-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

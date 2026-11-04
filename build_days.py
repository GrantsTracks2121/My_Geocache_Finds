#!/usr/bin/env python3
"""
Geocache Day Replay - data builder.

Reads the "My Finds" pocket query GPX file and writes data/days.js,
which day-replay.html loads. Uses only the Python standard library.

Usage (from Terminal, in this folder):
    python3 build_days.py              # uses the newest .gpx file in this folder
    python3 build_days.py MyFile.gpx   # uses a specific file

Run it again whenever you download a newer My Finds file.
"""

import gzip
import html
import json
import re
import math
import sys
from collections import Counter
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
GPX_NS = "{http://www.topografix.com/GPX/1/0}"
GS_NS = "{http://www.groundspeak.com/cache/1/0/1}"

# Log types that count as a stop on the day's route
STOP_TYPES = {"Found it", "Didn't find it", "Attended", "Webcam Photo Taken", "Write note"}

# Logs with a real time are stored in UTC. Convert them to local time so an
# evening find stays on the right day: Edmonton time for the Americas,
# Central European time for anything east of the mid-Atlantic.
AMERICAS_TZ = ZoneInfo("America/Edmonton")
EUROPE_TZ = ZoneInfo("Europe/Paris")


def pick_gpx():
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()
    files = sorted(HERE.glob("*.gpx"), key=lambda p: p.stat().st_mtime)
    if not files:
        sys.exit("No .gpx file found in " + str(HERE))
    return files[-1]


def log_day(stamp, lon):
    """Return the caching day (YYYY-MM-DD) for a log date.

    Geocaching.com stores many log dates as a bare date shown as 19:00 or
    20:00 UTC; for those the date part is the day. Logs made from an app
    carry a real UTC time; those are converted to local time first.
    """
    local_tz = EUROPE_TZ if lon > -30 else AMERICAS_TZ
    stamp = stamp.strip()
    date_part, _, time_part = stamp.partition("T")
    if time_part.startswith(("19:00:00", "20:00:00")) or not time_part:
        return date_part
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return date_part
        return dt.astimezone(local_tz).date().isoformat()
    except ValueError:
        return date_part


def text(el, tag):
    found = el.find(GS_NS + tag)
    return found.text.strip() if found is not None and found.text else ""


# ---------------------------------------------------------------------------
# Alberta Brass Cap Cache (GC43F3)
#
# GC43F3 was one listing that pointed at a different survey brass cap every
# few weeks, so the My Finds file puts every one of its logs at the listing's
# single location. Each log names its cap ("BCP769 Kinsmen Participark ...");
# the real cap locations come from brasscaps/brasscaps.json, saved once by
# fetch_brasscaps.py. Caps the brass cap site no longer lists (archived ones)
# fall back to the "Posted:" coordinates Grant wrote in his log.
# ---------------------------------------------------------------------------

BRASS_CAP_CODES = {"GC43F3", "GC72DVJ", "GC9P577"}
BRASS_CAP_PATH = HERE / "brasscaps" / "brasscaps.json"
BRASS_CAP_PAGE = "https://brasscap.albertabattlecache.ca/capbreakdown/{}.html"
BCP_RE = re.compile(r"BCP\s*-?\s*(\d{1,3})([A-Za-z])?(?![\d])")
# Coordinates Grant wrote in his log: "Posted: N53° 30.378' W112° 57.090'",
# "**Posted:** N50° 55.280' ...", or only "My GPSr: N52 16.077 W113 48.548".
# The posted coordinates are preferred; his GPS reading is the fallback.
COORD_TAIL = r"[*:\s]*N\s*(\d{1,2})\s*[°º\s]\s*(\d{1,2}\.\d+)\s*'?\s*,?\s*W\s*(\d{2,3})\s*[°º\s]\s*(\d{1,2}\.\d+)"
POSTED_RE = re.compile(r"Posted" + COORD_TAIL, re.I)
MYGPS_RE = re.compile(r"My\s*GPS\w*" + COORD_TAIL, re.I)

_brass_caps = None
brass_report = {"by_archive": 0, "by_posted": 0, "unplaced": [], "retyped": [], "added": []}
brass_seen_log_ids = set()


def brass_caps():
    global _brass_caps
    if _brass_caps is None:
        _brass_caps = {}
        if BRASS_CAP_PATH.exists():
            for rec in json.loads(BRASS_CAP_PATH.read_text(encoding="utf-8")):
                _brass_caps[rec["bcp"].upper()] = rec
    return _brass_caps


def bcp_id(num, suffix):
    return "BCP" + num.zfill(3) + (suffix or "").upper()


def place_brass_cap(stop, log_text, log_id):
    """Move a brass cap log to its cap. Returns None if the cap can't be located."""
    plain = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(log_text)))
    m = BCP_RE.search(plain)
    cap_id = bcp_id(m.group(1), m.group(2)) if m else ""
    rec = brass_caps().get(cap_id)
    stop["type"] = "Brass Cap"
    stop["bcp"] = cap_id
    brass_seen_log_ids.add(int(log_id))
    # The brass cap site captured some logs before Geocaching.com changed them
    # (e.g. three 2017-05-19 finds now stored as Write note). Grant chose to
    # show the type the site recorded.
    if rec:
        for ml in rec.get("my_logs", []):
            if ml["log_id"] == int(log_id) and ml["type"] and ml["type"] != stop["log"]:
                brass_report["retyped"].append((cap_id, stop["log"], ml["type"]))
                stop["log"] = ml["type"]
    if rec:
        stop.update(lat=round(rec["lat"], 6), lon=round(rec["lon"], 6),
                    name=f"{cap_id} {rec['name']}", url=BRASS_CAP_PAGE.format(cap_id))
        brass_report["by_archive"] += 1
        return stop
    p = POSTED_RE.search(plain) or MYGPS_RE.search(plain)
    if p:
        lat = int(p.group(1)) + float(p.group(2)) / 60
        lon = -(int(p.group(3)) + float(p.group(4)) / 60)
        name_m = re.search(re.escape(m.group(0)) + r"\s*-?\s*([^\n]{1,60}?)\s*(?:Posted|My\s*GPS|\n|$)", plain) if m else None
        label = (name_m.group(1).strip(" -:*") if name_m else "")
        stop.update(lat=round(lat, 6), lon=round(lon, 6),
                    name=(cap_id + (" " + label if label else "")).strip() or "Brass cap",
                    url=BRASS_CAP_PAGE.format(cap_id) if cap_id else "")
        if cap_id:
            brass_learned.setdefault(cap_id, (stop["lat"], stop["lon"], stop["name"]))
        brass_report["by_posted"] += 1
        return stop
    # Not locatable from this log alone; another of Grant's logs on the same
    # cap may give its coordinates. resolve_brass_caps() settles it at the end.
    stop["_pending"] = (cap_id, log_id)
    return stop


brass_learned = {}


def add_missing_brass_caps(days):
    """Add Grant's brass cap logs that the brass cap site saved but that are
    no longer in the My Finds file (14 finds from June-July 2017)."""
    for cap_id, rec in brass_caps().items():
        for ml in rec.get("my_logs", []):
            if ml["log_id"] in brass_seen_log_ids or ml["type"] not in STOP_TYPES:
                continue
            stop = {
                "code": "GC43F3", "name": f"{cap_id} {rec['name']}", "type": "Brass Cap",
                "state": rec.get("state") or "Alberta", "country": rec.get("country") or "Canada",
                "lat": round(rec["lat"], 6), "lon": round(rec["lon"], 6),
                "log": ml["type"], "logId": ml["log_id"], "bcp": cap_id,
                "url": BRASS_CAP_PAGE.format(cap_id), "source": "brass cap archive",
            }
            days[ml["date"]].append(stop)
            brass_seen_log_ids.add(ml["log_id"])
            brass_report["added"].append((cap_id, ml["date"], ml["type"]))


def resolve_brass_caps(days):
    """Place pending brass cap logs using coordinates learned from other logs
    on the same cap; drop the ones that still can't be located."""
    for day, stops in days.items():
        keep = []
        for s in stops:
            pending = s.pop("_pending", None)
            if pending is None:
                keep.append(s)
                continue
            cap_id, log_id = pending
            if cap_id in brass_learned:
                s["lat"], s["lon"], s["name"] = brass_learned[cap_id]
                s["url"] = BRASS_CAP_PAGE.format(cap_id)
                brass_report["by_posted"] += 1
                keep.append(s)
            else:
                brass_report["unplaced"].append((s["log"], cap_id or "no BCP number", log_id))
        stops[:] = keep
    for day in [d for d, v in days.items() if not v]:
        del days[day]


def report_brass_caps():
    r = brass_report
    if not (r["by_archive"] or r["by_posted"] or r["unplaced"]):
        return
    print(f"Brass caps: {r['by_archive']} placed from the brass cap archive, "
          f"{r['by_posted']} from coordinates written in Grant's logs, "
          f"{len(r['unplaced'])} left off the map (location unknown)")
    if r["retyped"]:
        print(f"  {len(r['retyped'])} logs shown with the type the brass cap site recorded: "
              + ", ".join(f"{c} ({a} -> {b})" for c, a, b in r["retyped"]))
    if r["added"]:
        print(f"  {len(r['added'])} logs added from the brass cap archive (not in My Finds): "
              + ", ".join(f"{c} {d}" for c, d, _ in r["added"]))
    for kind, cap, log_id in r["unplaced"]:
        print(f"    {kind}: {cap} (log {log_id})")


# ---------------------------------------------------------------------------
# Place names (from geonames/places.tsv.gz, made by build_places.py)
# ---------------------------------------------------------------------------

PLACES_PATH = HERE / "geonames" / "places.tsv.gz"
CELL = 0.25                 # grid cell size in degrees for the nearby-place search
SEARCH_CELLS = 2            # look this many cells around a stop in each direction
NEAR_KM = 2.0               # farther than this outside a place -> "near <place>"
AREA_KM = 2.0               # neighbourhood must be this close to count
AREA_MIN_POP = 30000        # only name neighbourhoods inside places this big
HOME_COUNTRY = "Canada"     # country left out of titles


def cell_of(lat, lon):
    return (math.floor(lat / CELL), math.floor(lon / CELL))


def km_between(lat1, lon1, lat2, lon2):
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371.0 * math.hypot(x, y)


def reach_km(pop):
    """Rough radius of a place from its population, so a cache in the suburbs
    of a big city is credited to the city and not to a small town whose
    centre point happens to be closer."""
    return min(25.0, 0.6 * math.sqrt(pop / 1000.0)) if pop > 0 else 0.0


def load_places(stops):
    """Load only the places in grid cells around the stops."""
    wanted = set()
    for s in stops:
        cy, cx = cell_of(s["lat"], s["lon"])
        for dy in range(-SEARCH_CELLS, SEARCH_CELLS + 1):
            for dx in range(-SEARCH_CELLS, SEARCH_CELLS + 1):
                wanted.add((cy + dy, cx + dx))
    grid = defaultdict(list)
    with gzip.open(PLACES_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            name, lat, lon, code, _cc, pop = line.rstrip("\n").split("\t")
            lat, lon = float(lat), float(lon)
            key = cell_of(lat, lon)
            if key in wanted:
                grid[key].append((name, lat, lon, code, int(pop or 0)))
    return grid


# ---------------------------------------------------------------------------
# Canadian municipal boundaries (from boundaries/csd.tsv.gz, made by
# build_boundaries.py). Inside a city, town or village the stop is credited to
# that municipality. Inside a county or rural municipality (Strathcona County,
# Parkland County, ...) it is credited to the nearest community there, such as
# Sherwood Park, or called "near <town>" when a town's limits are closest.
# Outside Canada the population-circle guess below is used as before.
# ---------------------------------------------------------------------------

BOUNDARY_PATH = HERE / "boundaries" / "csd.tsv.gz"
# Statistics Canada types that are a city, town or village in their own right
URBAN_TYPES = {"CY", "C", "CV", "T", "TV", "V", "VL", "SV", "RV", "DM", "TL"}
URBAN_SEARCH_KM = 25.0      # how far to look for a town's limits from a rural stop


class Municipality:
    __slots__ = ("name", "urban", "box", "rings")

    def __init__(self, name, kind, box, rings):
        # Lloydminster straddles Alberta and Saskatchewan and is listed as
        # "Lloydminster (Part)" in each province.
        self.name = name.replace(" (Part)", "")
        self.urban = kind in URBAN_TYPES
        self.box = box          # (min_lon, min_lat, max_lon, max_lat)
        self.rings = rings      # [[(lon, lat), ...], ...]

    def contains(self, lat, lon):
        x0, y0, x1, y1 = self.box
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            return False
        inside = False
        for ring in self.rings:
            px, py = ring[-1]
            for qx, qy in ring:
                if (qy > lat) != (py > lat) and lon < px + (lat - py) * (qx - px) / (qy - py):
                    inside = not inside
                px, py = qx, qy
        return inside

    def box_km(self, lat, lon):
        """Distance to this municipality's bounding box (a quick lower bound)."""
        x0, y0, x1, y1 = self.box
        dx = max(x0 - lon, 0, lon - x1) * 111.32 * math.cos(math.radians(lat))
        dy = max(y0 - lat, 0, lat - y1) * 110.57
        return math.hypot(dx, dy)

    def edge_km(self, lat, lon):
        """Distance from a point outside the municipality to its limits."""
        kx, ky = 111.32 * math.cos(math.radians(lat)), 110.57
        best = float("inf")
        for ring in self.rings:
            ax, ay = (ring[-1][0] - lon) * kx, (ring[-1][1] - lat) * ky
            for qx, qy in ring:
                bx, by = (qx - lon) * kx, (qy - lat) * ky
                sx, sy = bx - ax, by - ay
                seg = sx * sx + sy * sy
                t = 0.0 if seg == 0 else max(0.0, min(1.0, -(ax * sx + ay * sy) / seg))
                d = (ax + t * sx) ** 2 + (ay + t * sy) ** 2
                if d < best:
                    best = d
                ax, ay = bx, by
        return math.sqrt(best)


class Boundaries:
    def __init__(self, stops):
        wanted = set()
        for s in stops:
            cy, cx = cell_of(s["lat"], s["lon"])
            for dy in range(-SEARCH_CELLS, SEARCH_CELLS + 1):
                for dx in range(-SEARCH_CELLS, SEARCH_CELLS + 1):
                    wanted.add((cy + dy, cx + dx))
        self.grid = defaultdict(list)
        with gzip.open(BOUNDARY_PATH, "rt", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                name, kind, _prov, x0, y0, x1, y1, rings = line.rstrip("\n").split("\t", 7)
                box = (float(x0), float(y0), float(x1), float(y1))
                (cy0, cx0), (cy1, cx1) = cell_of(box[1], box[0]), cell_of(box[3], box[2])
                if (cy1 - cy0 + 1) * (cx1 - cx0 + 1) <= len(wanted):
                    cells = [(cy, cx) for cy in range(cy0, cy1 + 1) for cx in range(cx0, cx1 + 1)
                             if (cy, cx) in wanted]
                else:
                    cells = [c for c in wanted if cy0 <= c[0] <= cy1 and cx0 <= c[1] <= cx1]
                if not cells:
                    continue
                muni = Municipality(name, kind, box,
                                    [[tuple(p) for p in r] for r in json.loads(rings)])
                for c in cells:
                    self.grid[c].append(muni)
        self._memo = {}

    def find(self, lat, lon):
        """The municipality containing a point, or None (outside Canada)."""
        key = (lat, lon)
        if key not in self._memo:
            self._memo[key] = next(
                (m for m in self.grid.get(cell_of(lat, lon), ()) if m.contains(lat, lon)), None)
        return self._memo[key]

    def nearby_urban(self, lat, lon):
        cy, cx = cell_of(lat, lon)
        seen = set()
        for dy in range(-SEARCH_CELLS, SEARCH_CELLS + 1):
            for dx in range(-SEARCH_CELLS, SEARCH_CELLS + 1):
                for m in self.grid.get((cy + dy, cx + dx), ()):
                    if m.urban and id(m) not in seen:
                        seen.add(id(m))
                        yield m


def label_stop(grid, lat, lon, bounds=None):
    """Return (town, near, area) for a stop.

    town  - the place the stop belongs to
    near  - True if the stop is outside that place
    area  - neighbourhood within a larger place, or "" """
    muni = bounds.find(lat, lon) if bounds else None
    if muni is not None:
        return label_canadian_stop(grid, bounds, muni, lat, lon)
    cy, cx = cell_of(lat, lon)
    best_town, best_eff, best_pop = None, None, 0
    best_area, best_area_d = "", None
    for dy in range(-SEARCH_CELLS, SEARCH_CELLS + 1):
        for dx in range(-SEARCH_CELLS, SEARCH_CELLS + 1):
            for name, plat, plon, code, pop in grid.get((cy + dy, cx + dx), ()):
                d = km_between(lat, lon, plat, plon)
                if code != "PPLX":
                    eff = d - reach_km(pop)
                    if best_eff is None or eff < best_eff:
                        best_town, best_eff, best_pop = name, eff, pop
                if (code == "PPLX" or pop == 0) and d <= AREA_KM:
                    if best_area_d is None or d < best_area_d:
                        best_area, best_area_d = name, d
    if best_town is None:
        return ("", False, "")
    area = best_area if best_pop >= AREA_MIN_POP and best_area != best_town else ""
    return (best_town, best_eff > NEAR_KM, area)


def nearby_places(grid, lat, lon):
    cy, cx = cell_of(lat, lon)
    for dy in range(-SEARCH_CELLS, SEARCH_CELLS + 1):
        for dx in range(-SEARCH_CELLS, SEARCH_CELLS + 1):
            for place in grid.get((cy + dy, cx + dx), ()):
                name, plat, plon, code, pop = place
                yield place, km_between(lat, lon, plat, plon)


def label_canadian_stop(grid, bounds, muni, lat, lon):
    """(town, near, area) for a stop inside a Canadian municipality."""
    if muni.urban:
        # Inside city / town / village limits: that is the place.
        town_pop, best_area, best_area_d = 0, "", None
        for (name, plat, plon, code, pop), d in nearby_places(grid, lat, lon):
            if d > URBAN_SEARCH_KM or bounds.find(plat, plon) is not muni:
                continue
            if code != "PPLX":
                town_pop = max(town_pop, pop)
            if (code == "PPLX" or pop == 0) and d <= AREA_KM and name != muni.name:
                if best_area_d is None or d < best_area_d:
                    best_area, best_area_d = name, d
        return (muni.name, False, best_area if town_pop >= AREA_MIN_POP else "")

    # In a county or rural municipality: the nearest community outside any
    # town's limits (a hamlet like Sherwood Park), unless a town's limits are
    # closer, in which case the stop is "near" that town.
    best_town, best_eff, best_pop, best_near = None, None, 0, False
    best_area, best_area_d = "", None
    for (name, plat, plon, code, pop), d in nearby_places(grid, lat, lon):
        home = bounds.find(plat, plon)
        if home is not None and home.urban:
            continue    # covered by that town's own boundary below
        if code != "PPLX":
            eff = d - reach_km(pop)
            if best_eff is None or eff < best_eff:
                best_town, best_eff, best_pop, best_near = name, eff, pop, eff > NEAR_KM
        if (code == "PPLX" or pop == 0) and d <= AREA_KM:
            if best_area_d is None or d < best_area_d:
                best_area, best_area_d = name, d
    for town in sorted(bounds.nearby_urban(lat, lon), key=lambda m: m.box_km(lat, lon)):
        limit = min(URBAN_SEARCH_KM, best_eff if best_eff is not None else URBAN_SEARCH_KM)
        if town.box_km(lat, lon) >= limit:
            break
        d = town.edge_km(lat, lon)
        if d < limit:
            best_town, best_eff, best_pop, best_near = town.name, d, 0, True
            best_area = ""
    if best_town is None:
        return (muni.name, False, "")
    area = best_area if best_pop >= AREA_MIN_POP and best_area != best_town else ""
    return (best_town, best_near, area)


def stop_region(s):
    parts = []
    if s["state"] and s["state"] != "None":
        parts.append(s["state"])
    if s["country"] and s["country"] != HOME_COUNTRY:
        parts.append(s["country"])
    return ", ".join(parts)


def region_text(stops):
    regions = Counter(stop_region(s) for s in stops if stop_region(s))
    return regions.most_common(1)[0][0] if regions else ""


def town_label(town, stops):
    """'Edmonton (Terwillegar)' or 'near Wabamun' for the given stops in a town."""
    near = sum(1 for s in stops if s["near"]) > len(stops) / 2
    label = ("near " if near else "") + town
    areas = Counter(s["area"] for s in stops if s.get("area"))
    if areas:
        area, n = areas.most_common(1)[0]
        if n >= len(stops) * 0.5:
            label += " (" + area + ")"
    return label


def day_title(stops):
    """Title for a day.

    - Mostly in one or two places: the main place (with neighbourhood when
      most of the day was in one), a second place if it had a good share,
      then the province/state.
    - A road trip through many places: 'first place to last place'."""
    located = [s for s in stops if s.get("town")]
    if not located:
        return region_text(stops) or "Unknown location"
    by_town = defaultdict(list)
    for s in located:
        by_town[s["town"]].append(s)
    ranked = sorted(by_town.items(), key=lambda kv: -len(kv[1]))

    if len(by_town) >= 3 and len(ranked[0][1]) < len(located) * 0.4:
        first, last = located[0], located[-1]
        a = town_label(first["town"], [first])
        b = town_label(last["town"], [last])
        ra, rb = stop_region(first), stop_region(last)
        if ra == rb:
            return a + " to " + b + (", " + ra if ra else "")
        ca = first["country"] if first["country"] != HOME_COUNTRY else ""
        cb = last["country"] if last["country"] != HOME_COUNTRY else ""
        if ca == cb:
            # Same country: name each state, then the country once at the end
            sa = first["state"] if first["state"] not in ("", "None") else ""
            sb = last["state"] if last["state"] not in ("", "None") else ""
            return (a + (", " + sa if sa else "") + " to " + b + (", " + sb if sb else "")
                    + (", " + ca if ca else ""))
        return (a + (", " + ra if ra else "")) + " to " + (b + (", " + rb if rb else ""))

    pieces, used = [], []
    for town, town_stops in ranked[:2]:
        if pieces and len(town_stops) < max(2, len(located) * 0.25):
            break
        pieces.append(town_label(town, town_stops))
        used.extend(town_stops)
    region = region_text(used)
    return " & ".join(pieces) + (", " + region if region else "")


def main():
    gpx = pick_gpx()
    print("Reading", gpx.name, "...")
    root = ET.parse(gpx).getroot()

    days = defaultdict(list)
    for wpt in root.iter(GPX_NS + "wpt"):
        cache = wpt.find(GS_NS + "cache")
        if cache is None:
            continue
        # Locationless caches carry placeholder coordinates, not a place you visited
        if text(cache, "type").startswith("Locationless"):
            continue
        code_el = wpt.find(GPX_NS + "name")
        base = {
            "code": code_el.text.strip() if code_el is not None else "",
            "name": text(cache, "name"),
            "type": text(cache, "type"),
            "state": text(cache, "state"),
            "country": text(cache, "country"),
            "lat": round(float(wpt.get("lat")), 6),
            "lon": round(float(wpt.get("lon")), 6),
        }
        logs = cache.find(GS_NS + "logs")
        if logs is None:
            continue
        for log in logs.findall(GS_NS + "log"):
            kind = text(log, "type")
            if kind not in STOP_TYPES:
                continue
            stop = dict(base)
            stop["log"] = kind
            stop["logId"] = int(log.get("id"))
            if base["code"] in BRASS_CAP_CODES:
                stop = place_brass_cap(stop, text(log, "text"), log.get("id"))
            days[log_day(text(log, "date"), stop["lon"])].append(stop)
    resolve_brass_caps(days)
    add_missing_brass_caps(days)
    report_brass_caps()

    all_stops = [s for v in days.values() for s in v]
    if PLACES_PATH.exists():
        print("Looking up place names ...")
        grid = load_places(all_stops)
        bounds = None
        if BOUNDARY_PATH.exists():
            print("Loading Canadian municipal boundaries ...")
            bounds = Boundaries(all_stops)
        else:
            print("No boundary file yet (run build_boundaries.py); Canadian places will be guessed from town size.")
        memo = {}
        for s in all_stops:
            key = (s["lat"], s["lon"])
            if key not in memo:
                memo[key] = label_stop(grid, *key, bounds=bounds)
            s["town"], s["near"], s["area"] = memo[key]
    else:
        print("No place-name file yet (run build_places.py); titles will show the province/state only.")

    out = []
    for day in sorted(days, reverse=True):
        stops = sorted(days[day], key=lambda s: s["logId"])
        entry = {"date": day, "title": day_title(stops), "stops": stops}
        out.append(entry)

    data_dir = HERE / "data"
    data_dir.mkdir(exist_ok=True)
    target = data_dir / "days.js"
    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    target.write_text(
        "// Generated by build_days.py from " + gpx.name + " - do not edit by hand\n"
        "window.GEOCACHE_DAYS = " + payload + ";\n",
        encoding="utf-8",
    )
    total = sum(len(d["stops"]) for d in out)
    print(f"Wrote {target.relative_to(HERE)}: {len(out)} days, {total} stops")


if __name__ == "__main__":
    main()

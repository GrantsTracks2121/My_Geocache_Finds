#!/usr/bin/env python3
"""
My Geocache Finds - Alberta Brass Cap Cache finds.

The Alberta Brass Cap Cache (GC43F3, later GC72DVJ and GC9P577) was a single
listing that pointed at a different survey brass cap every few weeks, so the
My Finds file puts every one of its logs at the listing's one location. This
script reads a cacher's stats page on brasscap.albertabattlecache.ca and the
GPX file of each cap they found, so build_days.py can put each brass cap log
where it actually happened.

You don't normally run this yourself: paste your stats page address into
Settings > Alberta Brass Cap Cache on the Dashboard and the app runs it.
From a terminal it is:

    python3 fetch_brasscaps.py https://brasscap.albertabattlecache.ca/cacherbreakdown/<id>.html

Run it with no address to refresh from the page used last time.

It writes (all in the brasscaps/ folder):
    stats.html          copy of your stats page
    brasscaps.json      your caps and finds (used by build_days.py)
    gpx/BCPnnn.gpx      each cap's GPX file. These are public cap details
                        shared by everyone, so the app comes with most of
                        them and only new ones are downloaded, one a second.

Safe to stop and run again. Uses only the Python standard library.
"""

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "brasscaps"
GPX_DIR = OUT / "gpx"
JSON_PATH = OUT / "brasscaps.json"
STATS_PATH = OUT / "stats.html"
GONE_PATH = GPX_DIR / "no_gpx_on_site.txt"
BASE = "https://brasscap.albertabattlecache.ca"
STATS_URL_RE = re.compile(
    r"^(?:https?://)?brasscap\.albertabattlecache\.ca/cacherbreakdown/([0-9a-fA-F-]{36})\.html$")
HEADERS = {"User-Agent": "MyGeocacheFinds/1.0 (personal archive of one cacher's brass cap finds)"}
PAUSE = 1.0  # seconds between cap downloads

GPX_NS = "{http://www.topografix.com/GPX/1/0}"
GS_NS = "{http://www.groundspeak.com/cache/1/0/1}"


class FetchError(Exception):
    pass


def stats_url(text):
    """The cacher stats page address in a standard form, or None if it isn't one."""
    m = STATS_URL_RE.match(text.strip().split("#")[0].split("?")[0])
    return f"{BASE}/cacherbreakdown/{m.group(1).lower()}.html" if m else None


def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def cacher_name(page):
    m = re.search(r"Cacher Stats for\s*(.*?)\s*</title>", page, re.S | re.I)
    return html.unescape(m.group(1)).strip() if m else ""


def parse_stats(page):
    """Return [(bcp, name, difficulty, terrain, date_found, log_luid, archived), ...] from the stats page.

    Each row looks like:
    <tr><td><a href="../capbreakdown/BCP769.html">BCP769</a> - Kinsmen Participark (1.5/2)</td>
        <td>...</td><td><a href="https://www.geocaching.com/seek/log.aspx?LUID=...">2017-07-10</A></td></tr>
    """
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", page, re.S | re.I):
        cells = re.findall(r"<td>(.*?)</td>", tr, re.S | re.I)
        if len(cells) < 3 or "capbreakdown/" not in cells[0]:
            continue
        text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cells[0])).strip())
        m = re.match(r"(BCP\d+[A-Za-z]?)\s*-\s*(.*?)\s*\(([\d.]+)/([\d.]+)\)$", text)
        d = re.search(r"(?:LUID=([0-9a-fA-F-]+)\">)?\s*(\d{4}-\d\d-\d\d)", cells[2])
        if m and d:
            rows.append((m.group(1).upper(), m.group(2), m.group(3), m.group(4), d.group(2), d.group(1) or "",
                         'class="archived"' in cells[0]))
        else:
            print("  Could not read stats row:", text)
    return rows


def parse_cap_gpx(raw, finder_name):
    root = ET.fromstring(raw)
    wpt = root.find(GPX_NS + "wpt")
    cache = wpt.find(GS_NS + "cache")

    def gs(tag):
        el = cache.find(GS_NS + tag)
        return el.text.strip() if el is not None and el.text else ""

    ele = wpt.find(GPX_NS + "ele")
    placed = wpt.find(GPX_NS + "time")

    # The cacher's own logs, when they are still among the cap's last 5 logs
    my_logs = []
    logs = cache.find(GS_NS + "logs")
    for log in (logs.findall(GS_NS + "log") if logs is not None else []):
        finder = log.find(GS_NS + "finder")
        if finder is not None and (finder.text or "").strip().lower() == finder_name.lower():
            def lg(tag):
                el = log.find(GS_NS + tag)
                return el.text.strip() if el is not None and el.text else ""
            my_logs.append({"log_id": int(log.get("id")), "date": lg("date")[:10],
                            "type": lg("type"), "text": lg("text")})

    return {
        "lat": float(wpt.get("lat")),
        "lon": float(wpt.get("lon")),
        "elevation_m": float(ele.text) if ele is not None and ele.text else None,
        "name": gs("name"),
        "placed_by": gs("placed_by"),
        "added": placed.text[:10] if placed is not None and placed.text else "",
        "difficulty": gs("difficulty"),
        "terrain": gs("terrain"),
        "state": gs("state"),
        "country": gs("country"),
        "description": gs("encoded_hints"),
        "my_logs": my_logs,
    }


def caps_in_my_logs():
    """BCP numbers named in the brass cap logs of the newest My Finds file
    (this catches caps logged only as Didn't find it or Write note)."""
    files = sorted(HERE.glob("*.gpx"), key=lambda p: p.stat().st_mtime)
    if not files:
        return []
    text = files[-1].read_text(encoding="utf-8", errors="replace")
    found = []
    for code in ("GC43F3", "GC72DVJ", "GC9P577"):
        i = text.find(f"<name>{code}</name>")
        if i < 0:
            continue
        block = text[text.rfind("<wpt", 0, i):text.find("</wpt>", i)]
        for log in re.findall(r"<groundspeak:text[^>]*>(.*?)</groundspeak:text>", block, re.S):
            m = re.search(r"BCP\s*-?\s*(\d{1,3})([A-Za-z])?(?!\d)", log)
            if m:
                found.append("BCP" + m.group(1).zfill(3) + (m.group(2) or "").upper())
    return found


def saved_url():
    try:
        return json.loads(JSON_PATH.read_text(encoding="utf-8")).get("url", "")
    except (FileNotFoundError, ValueError, AttributeError):
        return ""


def fetch(url, log=print):
    """Read the stats page at url and write brasscaps.json. Returns a summary."""
    clean = stats_url(url)
    if not clean:
        raise FetchError("That isn't a brass cap Cacher Stats page address. It should look like "
                         f"{BASE}/cacherbreakdown/…….html")
    OUT.mkdir(exist_ok=True)
    GPX_DIR.mkdir(exist_ok=True)

    log("Fetching the stats page ...")
    try:
        page = get(clean).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise FetchError("That stats page wasn't found on the brass cap site." if exc.code == 404
                         else f"The brass cap site answered with an error ({exc.code}).")
    except (urllib.error.URLError, OSError):
        raise FetchError("Couldn't reach the brass cap site. Check your internet connection.")
    name = cacher_name(page)
    rows = parse_stats(page)
    if not name or not rows:
        raise FetchError("That page has no brass cap finds in it.")
    STATS_PATH.write_text(page, encoding="utf-8")
    log(f"{name}: {len(rows)} finds on the stats page")

    caps = list(dict.fromkeys(bcp for bcp, *_ in rows))
    extra = sorted(set(caps_in_my_logs()) - set(caps))

    # Archived caps have no GPX file on the site; remember them so reruns skip them
    gone = set(GONE_PATH.read_text().split()) if GONE_PATH.exists() else set()
    todo = [b for b in caps + extra if not (GPX_DIR / f"{b}.gpx").exists() and b not in gone]
    if todo:
        log(f"Downloading {len(todo)} cap{'s' if len(todo) != 1 else ''} (about {len(todo)} seconds) ...")
    failed = 0
    for i, bcp in enumerate(todo, 1):
        try:
            (GPX_DIR / f"{bcp}.gpx").write_bytes(get(f"{BASE}/capbreakdown/{bcp}.gpx"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                gone.add(bcp)
            else:
                failed += 1
        except Exception:  # keep going; a rerun retries failures
            failed += 1
        if i % 25 == 0:
            log(f"  {i}/{len(todo)}")
        time.sleep(PAUSE)
    GONE_PATH.write_text("\n".join(sorted(gone)) + "\n")

    records = {}

    def record(bcp, stats_name, archived):
        path = GPX_DIR / f"{bcp}.gpx"
        if not path.exists():
            return None
        if bcp not in records:
            rec = {"bcp": bcp}
            rec.update(parse_cap_gpx(path.read_bytes(), name))
            rec["stats_name"] = stats_name or rec["name"]
            rec["archived"] = archived
            rec["finds"] = []
            records[bcp] = rec
        return records[bcp]

    for bcp, cap_name, _d, _t, found, luid, archived in rows:
        rec = record(bcp, cap_name, archived)
        if rec:
            rec["finds"].append({"date": found, "log_luid": luid})
    for bcp in extra:
        record(bcp, "", False)

    caps_out = sorted(records.values(), key=lambda r: (int(re.match(r"BCP(\d+)", r["bcp"]).group(1)), r["bcp"]))
    JSON_PATH.write_text(json.dumps({
        "cacher": name, "url": clean, "fetched": date.today().isoformat(),
        "finds": len(rows), "caps": caps_out,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    missing = sorted(set(caps) - set(records))
    log(f"Wrote {JSON_PATH.relative_to(HERE)}: {len(caps_out)} caps")
    if missing:
        log(f"No GPX file on the site (archived caps, placed from your logs instead): {', '.join(missing)}")
    if failed:
        log(f"{failed} downloads failed; run again to retry")
    return {"cacher": name, "finds": len(rows), "caps": len(caps_out), "failed": failed}


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else saved_url()
    if not url:
        sys.exit("Give your Cacher Stats page address, for example:\n"
                 f"    python3 fetch_brasscaps.py {BASE}/cacherbreakdown/<id>.html")
    try:
        fetch(url)
    except FetchError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()

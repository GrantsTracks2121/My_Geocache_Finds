#!/usr/bin/env python3
"""
Geocache Day Replay - one-time Brass Cap archive.

The Alberta Brass Cap Cache (GC43F3) was a single listing that pointed at a
different survey brass cap every few weeks, so the My Finds file places all
of its logs at the listing's one location. This script saves the real
location and details of every brass cap Grant found, from
brasscap.albertabattlecache.ca, so build_days.py can put each brass cap log
where it actually happened.

It fetches the cacher stats page, then each cap's GPX file, one per second,
and writes:
    brasscaps/stats.html          copy of the stats page
    brasscaps/gpx/BCPnnn.gpx      each cap's GPX file as downloaded
    brasscaps/brasscaps.json      one record per cap (used by build_days.py)

Safe to stop and run again: caps already downloaded are skipped.
Uses only the Python standard library.

    python3 fetch_brasscaps.py
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "brasscaps"
GPX_DIR = OUT / "gpx"
BASE = "https://brasscap.albertabattlecache.ca"
STATS_URL = BASE + "/cacherbreakdown/cf6bc313-53fa-47a2-af63-5e266f5504c1.html"
HEADERS = {"User-Agent": "GeocacheDayReplay/1.0 (personal one-time archive of my own brass cap finds)"}
PAUSE = 1.0  # seconds between requests
MY_NAME = "Coolcat21"

GPX_NS = "{http://www.topografix.com/GPX/1/0}"
GS_NS = "{http://www.groundspeak.com/cache/1/0/1}"


def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def parse_stats(html):
    """Return [(bcp, name, difficulty, terrain, date_found, log_luid, archived), ...] from the stats page.

    Each row looks like:
    <tr><td><a href="../capbreakdown/BCP769.html">BCP769</a> - Kinsmen Participark (1.5/2)</td>
        <td>...</td><td><a href="https://www.geocaching.com/seek/log.aspx?LUID=...">2017-07-10</A></td></tr>
    """
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S | re.I):
        cells = re.findall(r"<td>(.*?)</td>", tr, re.S | re.I)
        if len(cells) < 3 or "capbreakdown/" not in cells[0]:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cells[0])).strip()
        m = re.match(r"(BCP\d+[A-Za-z]?)\s*-\s*(.*?)\s*\(([\d.]+)/([\d.]+)\)$", text)
        d = re.search(r"(?:LUID=([0-9a-fA-F-]+)\">)?\s*(\d{4}-\d\d-\d\d)", cells[2])
        if m and d:
            rows.append((m.group(1), m.group(2), m.group(3), m.group(4), d.group(2), d.group(1) or "",
                         'class="archived"' in cells[0]))
        else:
            print("  Could not read stats row:", text)
    return rows


def parse_cap_gpx(raw):
    root = ET.fromstring(raw)
    wpt = root.find(GPX_NS + "wpt")
    cache = wpt.find(GS_NS + "cache")

    def gs(tag):
        el = cache.find(GS_NS + tag)
        return el.text.strip() if el is not None and el.text else ""

    ele = wpt.find(GPX_NS + "ele")
    placed = wpt.find(GPX_NS + "time")

    # Grant's own logs, when they are still among the cap's last 5 logs
    my_logs = []
    logs = cache.find(GS_NS + "logs")
    for log in (logs.findall(GS_NS + "log") if logs is not None else []):
        finder = log.find(GS_NS + "finder")
        if finder is not None and (finder.text or "").strip() == MY_NAME:
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


def main():
    OUT.mkdir(exist_ok=True)
    GPX_DIR.mkdir(exist_ok=True)

    stats_path = OUT / "stats.html"
    if not stats_path.exists():
        print("Fetching stats page ...")
        stats_path.write_bytes(get(STATS_URL))
        time.sleep(PAUSE)
    rows = parse_stats(stats_path.read_text(encoding="utf-8", errors="replace"))
    print(f"Stats page lists {len(rows)} finds")

    caps = {}
    for bcp, *_ in rows:
        caps.setdefault(bcp, None)

    # Also caps named only in Didn't find it or note logs (not on the stats page)
    extra = sorted(set(caps_in_my_logs()) - set(caps))
    print(f"{len(caps)} caps found, plus {len(extra)} named only in DNF or note logs")

    # Archived caps have no GPX file on the site; remember them so reruns skip them
    gone_path = OUT / "no_gpx_on_site.txt"
    gone = set(gone_path.read_text().split()) if gone_path.exists() else set()
    todo = [b for b in list(caps) + extra if not (GPX_DIR / f"{b}.gpx").exists() and b not in gone]
    print(f"{len(todo)} still to download")
    for i, bcp in enumerate(todo, 1):
        try:
            (GPX_DIR / f"{bcp}.gpx").write_bytes(get(f"{BASE}/capbreakdown/{bcp}.gpx"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                gone.add(bcp)
            else:
                print(f"  {bcp}: failed ({exc}); run again to retry")
        except Exception as exc:  # keep going; a rerun retries failures
            print(f"  {bcp}: failed ({exc}); run again to retry")
        if i % 25 == 0:
            print(f"  {i}/{len(todo)}")
        time.sleep(PAUSE)
    gone_path.write_text("\n".join(sorted(gone)) + "\n")

    records = {}
    for bcp, name, diff, terr, found, luid, archived in rows:
        path = GPX_DIR / f"{bcp}.gpx"
        if not path.exists():
            continue
        if bcp not in records:
            rec = {"bcp": bcp}
            rec.update(parse_cap_gpx(path.read_bytes()))
            rec["stats_name"] = name
            rec["archived"] = archived
            rec["finds"] = []
            records[bcp] = rec
        records[bcp]["finds"].append({"date": found, "log_luid": luid})
    for bcp in extra:
        path = GPX_DIR / f"{bcp}.gpx"
        if path.exists() and bcp not in records:
            rec = {"bcp": bcp}
            rec.update(parse_cap_gpx(path.read_bytes()))
            rec["stats_name"] = rec["name"]
            rec["archived"] = False
            rec["finds"] = []
            records[bcp] = rec

    target = OUT / "brasscaps.json"
    target.write_text(json.dumps(sorted(records.values(), key=lambda r: (int(re.match(r"BCP(\d+)", r["bcp"]).group(1)), r["bcp"])),
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {target.relative_to(HERE)}: {len(records)} caps")
    if gone:
        print(f"No GPX file on the site (archived caps): {', '.join(sorted(gone))}")


def caps_in_my_logs():
    """BCP numbers named in Grant's GC43F3 logs in the newest My Finds file."""
    files = sorted(HERE.glob("*.gpx"), key=lambda p: p.stat().st_mtime)
    if not files:
        return []
    text = files[-1].read_text(encoding="utf-8", errors="replace")
    i = text.find("<name>GC43F3</name>")
    if i < 0:
        return []
    block = text[text.rfind("<wpt", 0, i):text.find("</wpt>", i)]
    found = []
    for log in re.findall(r"<groundspeak:text[^>]*>(.*?)</groundspeak:text>", block, re.S):
        m = re.search(r"BCP\s*-?\s*(\d{1,3})([A-Za-z])?(?!\d)", log)
        if m:
            found.append("BCP" + m.group(1).zfill(3) + (m.group(2) or "").upper())
    return found


if __name__ == "__main__":
    sys.exit(main())

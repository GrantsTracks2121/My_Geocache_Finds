#!/usr/bin/env python3
"""
Geocache Day Replay - place-name lookup builder.

Downloads the GeoNames "allCountries" file (about 400 MB) if it isn't already
in the geonames/ folder, then extracts every populated place in the world
(cities, towns, villages, hamlets and city neighbourhoods) into a compact
lookup file, geonames/places.tsv.gz, which build_days.py uses to name each
caching day.

Run it once. Run it again only if you want fresher GeoNames data.
Uses only the Python standard library.

    python3 build_places.py

Place names: GeoNames (https://www.geonames.org), licensed under
Creative Commons Attribution 4.0 (https://creativecommons.org/licenses/by/4.0/).
"""

import gzip
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEO_DIR = HERE / "geonames"
ZIP_PATH = GEO_DIR / "allCountries.zip"
OUT_PATH = GEO_DIR / "places.tsv.gz"
URL = "https://download.geonames.org/export/dump/allCountries.zip"

# GeoNames feature class P = populated place. Feature codes left out:
# PPLH historical, PPLQ abandoned, PPLW destroyed, PPLCH historical capital.
SKIP_CODES = {"PPLH", "PPLQ", "PPLW", "PPLCH"}


def download():
    GEO_DIR.mkdir(exist_ok=True)
    part = ZIP_PATH.with_suffix(".zip.part")
    print("Downloading", URL, "(about 400 MB) ...")
    req = urllib.request.Request(URL, headers={"User-Agent": "GeocacheDayReplay/1.0"})
    with urllib.request.urlopen(req) as resp, open(part, "wb") as out:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done * 100 // total}%", end="", flush=True)
    print()
    part.rename(ZIP_PATH)


def extract():
    print("Extracting populated places ...")
    kept = 0
    with zipfile.ZipFile(ZIP_PATH) as z, z.open("allCountries.txt") as raw, \
            gzip.open(OUT_PATH, "wt", encoding="utf-8", compresslevel=6) as out:
        out.write("# Place names from GeoNames (geonames.org), CC BY 4.0\n")
        out.write("# name\tlat\tlon\tfeature_code\tcountry_code\tpopulation\n")
        for line in io.TextIOWrapper(raw, encoding="utf-8"):
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 15 or cols[6] != "P" or cols[7] in SKIP_CODES:
                continue
            out.write("\t".join((
                cols[1],
                f"{float(cols[4]):.4f}",
                f"{float(cols[5]):.4f}",
                cols[7],
                cols[8],
                cols[14] or "0",
            )) + "\n")
            kept += 1
            if kept % 500000 == 0:
                print(f"  {kept:,} places so far")
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"Wrote {OUT_PATH.relative_to(HERE)}: {kept:,} places, {size_mb:.0f} MB")


def main():
    if not ZIP_PATH.exists():
        download()
    extract()


if __name__ == "__main__":
    sys.exit(main())

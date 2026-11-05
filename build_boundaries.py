#!/usr/bin/env python3
"""
Geocache Day Replay - Canadian city / town / county boundaries.

Reads Statistics Canada's census subdivision boundary file (every city,
town, village, county and municipal district in Canada) and writes a
compact lookup file, boundaries/csd.tsv.gz, which build_days.py uses so a
cache is credited to the municipality it is really in. Without it, a cache
in Sherwood Park could be called Edmonton just because Edmonton is big.

The app comes with boundaries/csd.tsv.gz already built, so users never need
to run this. It is only for rebuilding that file, for example from a newer
census. The boundary file has to be downloaded by hand, because the
Statistics Canada website blocks automatic downloads:

    https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcsd000b21a_e.zip
    (Cartographic Boundary Files, Census subdivisions, Shapefile)

Put lcsd000b21a_e.zip in the boundaries/ folder (no need to unzip it), then:

    python3 build_boundaries.py

Borders are simplified to within 10 m so the file stays small enough to
ship with the app. Uses only the Python standard library.

Boundaries: Statistics Canada, 2021 Census Boundary Files, reproduced and
distributed on an "as is" basis with the permission of Statistics Canada
(Statistics Canada Open Licence).
"""

import gzip
import json
import math
import struct
import sys
import zipfile
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOUND_DIR = HERE / "boundaries"
ZIP_PATH = BOUND_DIR / "lcsd000b21a_e.zip"
OUT_PATH = BOUND_DIR / "csd.tsv.gz"
STEM = "lcsd000b21a_e"

# Simplify each boundary so it stays within this many metres of the real one
# (Douglas-Peucker). Long straight borders shrink to their two ends, which
# keeps the file small enough to ship with the app; 10 m is far finer than
# needed to tell which town a cache is in.
SIMPLIFY_M = 10.0
DECIMALS = 4                # about 10 m

# --- NAD83 Statistics Canada Lambert (from the .prj file) -------------------
A = 6378137.0
INV_F = 298.257222101
E2 = (2 - 1 / INV_F) / INV_F
E = math.sqrt(E2)
LAT1, LAT2, LAT0 = math.radians(49), math.radians(77), math.radians(63.390675)
LON0 = math.radians(-91.86666666666666)
FE, FN = 6200000.0, 3000000.0


def _m(phi):
    return math.cos(phi) / math.sqrt(1 - E2 * math.sin(phi) ** 2)


def _t(phi):
    s = math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - E * s) / (1 + E * s)) ** (E / 2)


N = (math.log(_m(LAT1)) - math.log(_m(LAT2))) / (math.log(_t(LAT1)) - math.log(_t(LAT2)))
F = _m(LAT1) / (N * _t(LAT1) ** N)
RHO0 = A * F * _t(LAT0) ** N


def to_lat_lon(x, y):
    """Statistics Canada Lambert metres -> (lat, lon) in degrees."""
    dx, dy = x - FE, RHO0 - (y - FN)
    rho = math.hypot(dx, dy)
    theta = math.atan2(dx, dy)
    t = (rho / (A * F)) ** (1 / N)
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(8):
        s = math.sin(phi)
        phi = math.pi / 2 - 2 * math.atan(t * ((1 - E * s) / (1 + E * s)) ** (E / 2))
    return math.degrees(phi), math.degrees(theta / N + LON0)


# --- Shapefile reading -------------------------------------------------------

def read_dbf(data):
    count, header_len, rec_len = struct.unpack("<4xIHH", data[:12])
    fields, off = [], 32
    while data[off] != 0x0D:
        f = data[off:off + 32]
        fields.append((f[:11].split(b"\0")[0].decode(), f[16]))
        off += 32
    rows = []
    for i in range(count):
        rec = data[header_len + i * rec_len: header_len + (i + 1) * rec_len]
        pos, row = 1, {}
        for name, size in fields:
            row[name] = rec[pos:pos + size].decode("cp1252").strip()
            pos += size
        rows.append(row)
    return rows


def read_polygons(f):
    """Yield each record's rings as lists of (x, y) metres."""
    f.read(100)
    while True:
        head = f.read(8)
        if len(head) < 8:
            return
        _num, words = struct.unpack(">ii", head)
        content = f.read(words * 2)
        shape_type = struct.unpack("<i", content[:4])[0]
        if shape_type == 0:
            yield []
            continue
        num_parts, num_points = struct.unpack("<ii", content[36:44])
        parts = list(struct.unpack("<%di" % num_parts, content[44:44 + 4 * num_parts]))
        pts = array("d")
        start = 44 + 4 * num_parts
        pts.frombytes(content[start:start + 16 * num_points])
        if sys.byteorder != "little":
            pts.byteswap()
        parts.append(num_points)
        rings = []
        for a, b in zip(parts, parts[1:]):
            rings.append([(pts[2 * i], pts[2 * i + 1]) for i in range(a, b)])
        yield rings


def _offset2(p, a, b):
    """Squared distance (metres) from point p to the segment a-b."""
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    ex, ey = ax + t * dx - px, ay + t * dy - py
    return ex * ex + ey * ey


def thin(ring):
    """Douglas-Peucker simplification of a closed ring, to within SIMPLIFY_M."""
    if len(ring) < 5:
        return ring
    tol2 = SIMPLIFY_M ** 2
    keep = bytearray(len(ring))
    keep[0] = keep[-1] = 1
    stack = [(0, len(ring) - 1)]
    while stack:
        i, j = stack.pop()
        far, far_d = None, tol2
        a, b = ring[i], ring[j]
        for k in range(i + 1, j):
            d = _offset2(ring[k], a, b)
            if d > far_d:
                far, far_d = k, d
        if far is not None:
            keep[far] = 1
            stack.append((i, far))
            stack.append((far, j))
    return [p for p, k in zip(ring, keep) if k]


def main():
    if not ZIP_PATH.exists():
        sys.exit("Boundary file not found: " + str(ZIP_PATH.relative_to(HERE)) +
                 "\nDownload it by hand (see the notes at the top of this script).")
    print("Reading", ZIP_PATH.name, "...")
    with zipfile.ZipFile(ZIP_PATH) as z:
        rows = read_dbf(z.read(STEM + ".dbf"))
        written = points = 0
        with z.open(STEM + ".shp") as shp, \
                gzip.open(OUT_PATH, "wt", encoding="utf-8", compresslevel=6) as out:
            out.write("# Census subdivisions, Statistics Canada 2021 Census Boundary Files (Open Licence)\n")
            out.write("# name\ttype\tprovince_code\tmin_lon\tmin_lat\tmax_lon\tmax_lat"
                      "\trings as JSON [[[lon,lat],...],...]\n")
            for row, rings in zip(rows, read_polygons(shp)):
                ll_rings = []
                for ring in rings:
                    ring = thin(ring)
                    if len(ring) < 4:
                        continue
                    ll = []
                    for x, y in ring:
                        lat, lon = to_lat_lon(x, y)
                        ll.append([round(lon, DECIMALS), round(lat, DECIMALS)])
                    ll_rings.append(ll)
                    points += len(ll)
                if not ll_rings:
                    continue
                lons = [p[0] for r in ll_rings for p in r]
                lats = [p[1] for r in ll_rings for p in r]
                box = (min(lons), min(lats), max(lons), max(lats))
                out.write("\t".join((row["CSDNAME"], row["CSDTYPE"], row["PRUID"],
                                     *("%.5f" % v for v in box),
                                     json.dumps(ll_rings, separators=(",", ":")))) + "\n")
                written += 1
                if written % 500 == 0:
                    print(f"  {written:,} of {len(rows):,}")
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"Wrote {OUT_PATH.relative_to(HERE)}: {written:,} municipalities, "
          f"{points:,} boundary points, {size_mb:.0f} MB")


if __name__ == "__main__":
    main()

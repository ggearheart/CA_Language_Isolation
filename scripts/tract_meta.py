#!/usr/bin/env python3
"""Build per-tract search metadata: ZIP, city, and Regional Water Board.

- ZIP + city   come from the CalEnviroScreen CSV (columns ZIP, apx_loc).
- Regional board is a point-in-polygon assignment of each tract's centroid to
  the 9 Regional Water Quality Control Board boundaries.

Inputs : data/tracts_ces.json   (tract geometry; tract as float)
         data/ces5.csv           (CalEnviroScreen CSV: tract, ZIP, apx_loc, ...)
         data/rb_boundaries.json  (Regional Board polygons; props rb, rb_name)
Output : data/tract_meta.json     ({GEOID: {z, city, rb, rbn}})
"""
import csv, json, os

HERE = os.path.dirname(__file__)
GEOM = os.path.join(HERE, "..", "data", "tracts_ces.json")
CSV = os.path.join(HERE, "..", "data", "ces5.csv")
RB = os.path.join(HERE, "..", "data", "rb_boundaries.json")
OUT = os.path.join(HERE, "..", "data", "tract_meta.json")


def rings_of(geom):
    """Yield exterior rings (list of [lon,lat]) for Polygon/MultiPolygon."""
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon":
        yield c[0]
    elif t == "MultiPolygon":
        for part in c:
            yield part[0]


def bbox(ring):
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def centroid(geom):
    """Average of the largest exterior ring's vertices."""
    best = max(rings_of(geom), key=len)
    xs = [p[0] for p in best]; ys = [p[1] for p in best]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def in_ring(x, y, ring):
    """Ray-casting point-in-polygon for a single ring."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and \
           (x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi):
            inside = not inside
        j = i
    return inside


def main():
    # --- Regional Board polygons grouped by region ---
    rbfc = json.load(open(RB))
    regions = {}   # rb_num -> {"name":.., "parts":[(bbox, ring), ...]}
    for f in rbfc["features"]:
        p = f["properties"]
        num = str(p.get("rb"))
        name = p.get("rb_name")
        reg = regions.setdefault(num, {"name": name, "parts": []})
        for ring in rings_of(f["geometry"]):
            reg["parts"].append((bbox(ring), ring))

    def assign_region(x, y):
        for num, reg in regions.items():
            for bb, ring in reg["parts"]:
                if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3] and in_ring(x, y, ring):
                    return num, reg["name"]
        # fallback: nearest region by part-bbox center
        best, bd = None, 1e18
        for num, reg in regions.items():
            for bb, _ in reg["parts"]:
                cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
                d = (cx - x) ** 2 + (cy - y) ** 2
                if d < bd:
                    bd, best = d, (num, reg["name"])
        return best

    # --- ZIP + city from CES CSV, keyed by GEOID ---
    zipcity = {}
    with open(CSV, newline="") as fh:
        r = csv.DictReader(fh)
        # handle BOM on first header
        r.fieldnames = [fn.lstrip("﻿") for fn in r.fieldnames]
        for row in r:
            try:
                geoid = "0" + str(int(float(row["tract"])))
            except (ValueError, KeyError):
                continue
            zipcity[geoid] = (row.get("ZIP", "").strip(), row.get("apx_loc", "").strip())

    # --- walk tract geometry, assign everything ---
    geo = json.load(open(GEOM))
    out = {}
    fallback = 0
    for f in geo["features"]:
        geoid = "0" + str(int(f["properties"]["tract"]))
        cx, cy = centroid(f["geometry"])
        num, name = assign_region(cx, cy)
        z, city = zipcity.get(geoid, ("", ""))
        out[geoid] = {"z": z, "city": city, "rb": num, "rbn": name}

    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    # quick distribution
    from collections import Counter
    dist = Counter(v["rbn"] for v in out.values())
    print(f"wrote {OUT}: {len(out)} tracts")
    for k, v in sorted(dist.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5d}  {k}")


if __name__ == "__main__":
    main()

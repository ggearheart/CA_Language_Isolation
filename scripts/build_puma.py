#!/usr/bin/env python3
"""Build the PUMA-geography dataset (the geography PUMS is published at).

PUMAs are ~100k+ people each (281 in California) — coarser than census tracts
but with much larger ACS samples. CalEnviroScreen is published at census-tract
level ONLY, so there is no CES `ling`/`lingP` at PUMA: the isolation percentile
is unavailable here and `lp` is null. `lg` (% limited-English households) is
computed directly from ACS C16002 instead of taken from CES.

Inputs : data/pumas_geom.json    (PUMA polygons; props GEOID20, NAMELSAD20)
         data/acs_lang_puma.json (ACS C16002 + C16001 at PUMA)
         data/tracts_ces.json    (tract geometry + county — for the county crosswalk)
         docs/tracts.json        (canonical langNames, so language indices match)
Output : docs/pumas.json

Counties: PUMAs do not nest cleanly in counties (rural PUMAs combine several),
so each PUMA's county list is derived spatially — every tract centroid inside
the PUMA contributes its county.
"""
import bisect, json, os, sys
from collections import defaultdict

from tract_meta import rings_of, bbox, centroid, in_ring

HERE = os.path.dirname(__file__)
GEOM = os.path.join(HERE, "..", "data", "pumas_geom.json")
ACS = os.path.join(HERE, "..", "data", "acs_lang_puma.json")
TRACTS = os.path.join(HERE, "..", "data", "tracts_ces.json")
TRACTS_OUT = os.path.join(HERE, "..", "docs", "tracts.json")
OUT = os.path.join(HERE, "..", "docs", "pumas.json")

GROUP_ORDER = ["spanish", "other_indo_european", "asian_pacific_island", "other"]


def main():
    geo = json.load(open(GEOM))
    acs = json.load(open(ACS))
    pumas = acs["tracts"]
    group_labels = [acs["groupLabels"][k] for k in GROUP_ORDER]

    # Seed the language intern map from the tract dataset so both geographies
    # share identical language indices (the UI's language search relies on it).
    lang_names = list(json.load(open(TRACTS_OUT))["langNames"])
    lang_index = {n: i for i, n in enumerate(lang_names)}

    def idx(name):
        if name not in lang_index:
            lang_index[name] = len(lang_names)
            lang_names.append(name)
        return lang_index[name]

    # --- county crosswalk: which counties does each PUMA cover? ---
    parts = []   # (bbox, ring, puma_geoid)
    for f in geo["features"]:
        g = f["properties"]["GEOID20"]
        for ring in rings_of(f["geometry"]):
            parts.append((bbox(ring), ring, g))

    puma_counties = defaultdict(set)
    tr = json.load(open(TRACTS))
    unplaced = 0
    for f in tr["features"]:
        county = f["properties"].get("county")
        x, y = centroid(f["geometry"])
        hit = None
        for bb, ring, g in parts:
            if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3] and in_ring(x, y, ring):
                hit = g
                break
        if hit:
            puma_counties[hit].add(county)
        else:
            unplaced += 1

    # --- assemble ---
    feats = []
    matched = 0
    for f in geo["features"]:
        p = f["properties"]
        gid = p["GEOID20"]
        a = pumas.get(gid)
        cs = sorted(puma_counties.get(gid, []))
        props = {
            "t": gid,
            "nm": p.get("NAMELSAD20", "").replace(" PUMA", ""),
            "c": ", ".join(cs),
            "cs": cs,
            "lp": None,          # filled below: ACS-derived percentile, NOT CES
        }
        if a:
            matched += 1
            hh, lep = a["total_hh"], a["lep_hh"]
            props["hh"] = hh
            props["lep"] = lep
            props["pop"] = a.get("pop", 0)     # population age 5+
            props["lg"] = round(lep / hh * 100, 1) if hh else None
            props["g"] = [a["groups"].get(k, 0) for k in GROUP_ORDER]
            langs = [row for row in a["langs"]
                     if not row[0].lower().startswith("other and unspecified")]
            props["L"] = [[idx(n), tot, lep] for n, tot, lep in langs]
        f["properties"] = props
        feats.append(f)

    # ACS-derived isolation percentile: rank the PUMAs against each other by
    # % limited-English households (C16002). This is NOT the CalEnviroScreen
    # percentile — CES is tract-only — so it is tagged pctSrc="ACS" and the UI
    # labels it as such. Ties get the midrank, so identical values score alike.
    vals = sorted(f["properties"]["lg"] for f in feats
                  if f["properties"].get("lg") is not None)
    n = len(vals)
    for f in feats:
        v = f["properties"].get("lg")
        if v is None or not n:
            continue
        below = bisect.bisect_left(vals, v)
        equal = bisect.bisect_right(vals, v) - below
        f["properties"]["lp"] = round((below + 0.5 * equal) / n * 100, 1)

    out = {"type": "FeatureCollection", "pctSrc": "ACS",
           "langNames": lang_names, "groupLabels": group_labels,
           "features": feats}
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    sz = os.path.getsize(OUT) / 1e6
    multi = sum(1 for f in feats if len(f["properties"]["cs"]) > 1)
    print(f"pumas={len(feats)} matched ACS={matched} "
          f"multi-county={multi} tracts unplaced={unplaced} "
          f"langNames={len(lang_names)} -> {OUT} ({sz:.1f} MB)")


if __name__ == "__main__":
    main()

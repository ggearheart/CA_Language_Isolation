#!/usr/bin/env python3
"""Join CalEnviroScreen 5.0 tract geometry (ling/lingP) with ACS language data
into the compact GeoJSON the web map loads.

Inputs : data/tracts_ces.json   (geometry + ling, lingP; tract as float)
         data/acs_lang.json      (per-GEOID household + named-language data)
Output : docs/tracts.json        (GeoJSON; compact interned properties)

Property schema per feature:
  t   GEOID (11-digit string)
  c   county name
  lp  linguistic-isolation percentile (0-100, 1 dp)   <- CES lingP, map color
  lg  % limited-English-speaking households (1 dp)     <- CES ling
  hh  total households (ACS)
  lep limited-English-speaking households (ACS)
  g   [spanish, other_indo_euro, asian_pi, other]  broad LEP-household counts
  L   [[langIdx, persons], ...]  named langs (pop 5+, English < "very well"), desc
Top-level:
  langNames   index -> language name (for L)
  groupLabels ordered labels for g
"""
import json, os

HERE = os.path.dirname(__file__)
GEOM = os.path.join(HERE, "..", "data", "tracts_ces.json")
ACS = os.path.join(HERE, "..", "data", "acs_lang.json")
OUT = os.path.join(HERE, "..", "docs", "tracts.json")

GROUP_ORDER = ["spanish", "other_indo_european", "asian_pacific_island", "other"]


def r1(x):
    """Round to 1 dp; CES uses -999 as a no-data sentinel -> None."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v < 0 else round(v, 1)


def main():
    geo = json.load(open(GEOM))
    acs = json.load(open(ACS))
    tracts = acs["tracts"]
    group_labels = [acs["groupLabels"][k] for k in GROUP_ORDER]

    # intern language names
    lang_index = {}
    lang_names = []

    def idx(name):
        if name not in lang_index:
            lang_index[name] = len(lang_names)
            lang_names.append(name)
        return lang_index[name]

    matched = 0
    kept = []
    for f in geo["features"]:
        p = f["properties"]
        geoid = "0" + str(int(p["tract"]))  # CES drops the leading state 0
        a = tracts.get(geoid)
        props = {
            "t": geoid,
            "c": p.get("county"),
            "lp": r1(p.get("lingP")),
            "lg": r1(p.get("ling")),
        }
        if a:
            matched += 1
            props["hh"] = a["total_hh"]
            props["lep"] = a["lep_hh"]
            props["g"] = [a["groups"].get(k, 0) for k in GROUP_ORDER]
            # drop the catch-all "Other and unspecified" from the named list so
            # the popup highlights actual named languages; keep top 8
            langs = [(n, c) for n, c in a["langs"]
                     if not n.lower().startswith("other and unspecified")]
            props["L"] = [[idx(n), c] for n, c in langs[:8]]
        f["properties"] = props
        kept.append(f)

    out = {
        "type": "FeatureCollection",
        "langNames": lang_names,
        "groupLabels": group_labels,
        "features": kept,
    }
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    sz = os.path.getsize(OUT) / 1e6
    print(f"features={len(kept)} matched ACS={matched} "
          f"unmatched={len(kept)-matched} langNames={len(lang_names)} "
          f"-> {OUT} ({sz:.1f} MB)")


if __name__ == "__main__":
    main()

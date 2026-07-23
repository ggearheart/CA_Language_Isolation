#!/usr/bin/env python3
"""Pull ACS 2020-2024 5-year language data for all California census tracts and
write a per-tract JSON keyed by 11-digit GEOID.

Two tables:
  C16002  Household language by household limited-English-speaking status
          -> the 4 broad "limited English speaking household" groups.
             This matches CalEnviroScreen's household-level `ling` indicator.
  C16001  Language spoken at home by ability to speak English (pop 5+)
          -> named-language detail: persons who "speak English less than
             'very well'" per language ("languages isolated for").
             12 language groups; this is the finest split the Census
             publishes at census-tract level (B16001's ~40 languages are
             not released for tracts).

Geography (argv[1]): "tract" (default) or "puma".
  tract -> data/acs_lang.json      keyed by 11-digit tract GEOID
  puma  -> data/acs_lang_puma.json keyed by 7-char PUMA GEOID (state + PUMA code)
PUMA is the geography PUMS microdata is published at (~100k+ people each):
coarser than tracts, but larger samples. CalEnviroScreen has no PUMA equivalent.

Usage: CENSUS_KEY=xxxx python3 pull_acs.py [tract|puma]
"""
import json, os, sys, urllib.request

YEAR = "2024"
BASE = f"https://api.census.gov/data/{YEAR}/acs/acs5"
KEY = os.environ.get("CENSUS_KEY")
GEO = (sys.argv[1] if len(sys.argv) > 1 else "tract").lower()
_D = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(_D, "acs_lang_puma.json" if GEO == "puma" else "acs_lang.json")
VARS_URL = f"{BASE}/variables.json"

# C16002: total households + the four "Limited English speaking household" groups
C16002 = {
    "C16002_001E": "total_hh",
    "C16002_004E": "spanish",
    "C16002_007E": "other_indo_european",
    "C16002_010E": "asian_pacific_island",
    "C16002_013E": "other",
}
GROUP_LABELS = {
    "spanish": "Spanish",
    "other_indo_european": "Other Indo-European",
    "asian_pacific_island": "Asian & Pacific Island",
    "other": "Other languages",
}


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


PUMA_FOR = "public%20use%20microdata%20area"


def api(get_vars):
    g = ",".join(get_vars)
    if GEO == "puma":
        url = f"{BASE}?get={g}&for={PUMA_FOR}:*&in=state:06&key={KEY}"
    else:
        url = f"{BASE}?get={g}&for=tract:*&in=state:06&in=county:*&key={KEY}"
    return fetch_json(url)


def rows_to_dict(rows):
    """Census response -> {GEOID: {col: value}}.
    tract GEOID = state+county+tract (11); PUMA GEOID = state+puma code (7)."""
    head = rows[0]
    idx = {c: i for i, c in enumerate(head)}
    out = {}
    for row in rows[1:]:
        if GEO == "puma":
            geoid = row[idx["state"]] + row[idx["public use microdata area"]]
        else:
            geoid = row[idx["state"]] + row[idx["county"]] + row[idx["tract"]]
        out[geoid] = {c: row[i] for c, i in idx.items()}
    return out


def num(v):
    try:
        n = int(v)
        return n if n >= 0 else 0  # negative = census annotation/suppressed
    except (TypeError, ValueError):
        return 0


def main():
    if not KEY:
        sys.exit("Set CENSUS_KEY env var")

    # --- C16001 variable map: per language, the total-speakers var AND the
    #     "speak English less than very well" var; plus the pop-5+ denominator.
    # Labels: Estimate!!Total:                                    -> pop 5+
    #         Estimate!!Total:!!<Language>:                       -> total speakers
    #         Estimate!!Total:!!<Language>:!!Speak English less..  -> limited-English
    meta = fetch_json(VARS_URL)["variables"]
    POP = "C16001_001E"
    lang_total, lang_lep = {}, {}   # varcode -> language name
    for code, info in meta.items():
        if not code.startswith("C16001_"):
            continue
        parts = info.get("label", "").split("!!")
        if len(parts) == 3 and parts[2].endswith(":"):
            lang_total[code] = parts[2].rstrip(":").strip()
        elif len(parts) == 4 and 'less than "very well"' in parts[3]:
            lang_lep[code] = parts[2].rstrip(":").strip()
    # order languages by the total-var code so total/lep stay aligned
    names = [lang_total[c] for c in sorted(lang_total)]
    total_by_name = {v: k for k, v in lang_total.items()}
    lep_by_name = {v: k for k, v in lang_lep.items()}
    print(f"C16001 named languages: {len(names)}", file=sys.stderr)

    # --- pull C16002 (broad household groups) ---
    c_rows = api(list(C16002.keys()))
    c_data = rows_to_dict(c_rows)
    print(f"C16002 tracts: {len(c_data)}", file=sys.stderr)

    # --- pull C16001 (pop 5+, per-language total speakers + limited-English) ---
    b_codes = [POP] + [total_by_name[n] for n in names] + [lep_by_name[n] for n in names]
    b_rows = api(b_codes)
    b_data = rows_to_dict(b_rows)
    print(f"C16001 tracts: {len(b_data)}", file=sys.stderr)

    # --- merge per area ---
    result = {}
    geoids = set(c_data) | set(b_data)
    for g in geoids:
        c = c_data.get(g, {})
        total_hh = num(c.get("C16002_001E"))
        groups = {k: num(c.get(code)) for code, k in C16002.items() if k != "total_hh"}
        lep_hh = sum(groups.values())

        b = b_data.get(g, {})
        pop = num(b.get(POP))                 # population 5+ (language-% denominator)
        langs = []
        for name in names:
            tot = num(b.get(total_by_name[name]))
            lep = num(b.get(lep_by_name[name]))
            if tot > 0:
                langs.append([name, tot, lep])   # total speakers, limited-English
        langs.sort(key=lambda x: -x[1])           # by total speakers desc

        result[g] = {
            "total_hh": total_hh,
            "lep_hh": lep_hh,
            "groups": groups,            # broad household LEP counts
            "pop": pop,                  # population age 5+
            "langs": langs,              # [ [name, speakers, limited_english], ... ]
        }

    with open(OUT, "w") as f:
        json.dump({"groupLabels": GROUP_LABELS, "tracts": result}, f)
    print(f"wrote {OUT}: {len(result)} tracts", file=sys.stderr)


if __name__ == "__main__":
    main()

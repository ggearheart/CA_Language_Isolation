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

Usage: CENSUS_KEY=xxxx python3 pull_acs.py
Output: data/acs_lang.json
"""
import json, os, sys, urllib.request, urllib.parse

YEAR = "2024"
BASE = f"https://api.census.gov/data/{YEAR}/acs/acs5"
KEY = os.environ.get("CENSUS_KEY")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "acs_lang.json")
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


def api(get_vars):
    q = urllib.parse.urlencode({
        "get": ",".join(get_vars),
        "for": "tract:*",
        "in": "state:06 county:*",
        "key": KEY,
    })
    # requests wants the two `in` clauses space-joined; census accepts "&in="
    url = f"{BASE}?get={','.join(get_vars)}&for=tract:*&in=state:06&in=county:*&key={KEY}"
    return fetch_json(url)


def rows_to_dict(rows):
    """Census response -> {GEOID: {col: value}} using state+county+tract."""
    head = rows[0]
    idx = {c: i for i, c in enumerate(head)}
    out = {}
    for row in rows[1:]:
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

    # --- language-name map for C16001 "less than very well" variables ---
    meta = fetch_json(VARS_URL)["variables"]
    named = {}  # varcode -> language name
    for code, info in meta.items():
        if not code.startswith("C16001_"):
            continue
        label = info.get("label", "")
        if 'less than "very well"' not in label:
            continue
        # label: Estimate!!Total:!!<Language>:!!Speak English less than "very well"
        parts = label.split("!!")
        lang = parts[2].rstrip(":").strip()
        named[code] = lang
    print(f"C16001 named languages: {len(named)}", file=sys.stderr)

    # --- pull C16002 (broad household groups) ---
    c_rows = api(list(C16002.keys()))
    c_data = rows_to_dict(c_rows)
    print(f"C16002 tracts: {len(c_data)}", file=sys.stderr)

    # --- pull C16001 (named languages, less-than-very-well) ---
    b_codes = list(named.keys())
    b_rows = api(b_codes)
    b_data = rows_to_dict(b_rows)
    print(f"C16001 tracts: {len(b_data)}", file=sys.stderr)

    # --- merge per tract ---
    result = {}
    geoids = set(c_data) | set(b_data)
    for g in geoids:
        c = c_data.get(g, {})
        total_hh = num(c.get("C16002_001E"))
        groups = {k: num(c.get(code)) for code, k in C16002.items() if k != "total_hh"}
        lep_hh = sum(groups.values())

        b = b_data.get(g, {})
        langs = []
        for code, name in named.items():
            v = num(b.get(code))
            if v > 0:
                langs.append([name, v])
        langs.sort(key=lambda x: -x[1])

        result[g] = {
            "total_hh": total_hh,
            "lep_hh": lep_hh,
            "groups": groups,            # broad household LEP counts
            "langs": langs,              # [ [name, persons], ... ] desc, person-level
        }

    with open(OUT, "w") as f:
        json.dump({"groupLabels": GROUP_LABELS, "tracts": result}, f)
    print(f"wrote {OUT}: {len(result)} tracts", file=sys.stderr)


if __name__ == "__main__":
    main()

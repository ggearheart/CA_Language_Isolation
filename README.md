# California Language Isolation Map

An interactive census-tract map of **linguistic isolation** across California and the
**languages households are isolated in**. Built to modernize an older Power BI
prototype using the latest available data.

**Live demo:** served from `docs/` (GitHub Pages ready).

## What it shows

- **Isolation percentile** — CalEnviroScreen 5.0 linguistic-isolation percentile
  for each of California's 9,106 census tracts (statewide 0–100 ranking).
- **% isolated households** — share of households that are "limited-English-speaking"
  (no one age 14+ speaks English "very well").
- **Dominant language** — categorical map coloring each tract by the language group
  most of its isolated households speak.
- **Find a place** — one search box that matches an **address** (geocoded to its
  tract via the US Census geocoder, OSM/Nominatim fallback), **ZIP code**, **city**,
  **Regional Water Board** (by name or "region N"), or **census tract** GEOID — plus
  a **📍 Near me** button (phone geolocation → the tract you're standing in, via
  client-side point-in-polygon).
- **Search by language** — a controlled-vocabulary picker (the 11 named ACS
  tract-level language groups). Selecting one filters the map to tracts where
  that language is isolated for and shades them by the number of residents
  isolated (combines with the county filter).
- **Per-tract detail** — click any tract for its isolation score, a breakdown of
  isolated households by the four broad language groups, and the specific
  **languages isolated for** (Spanish, Chinese, Vietnamese, Tagalog, Korean,
  Arabic, Russian/Slavic, Armenian/Persian-group, etc.).
- Bilingual **English / Spanish** UI, colorblind-safe palette.

## Data sources

| Layer | Source | Level |
|-------|--------|-------|
| Linguistic isolation (`ling`, `lingP`) + tract geometry | [CalEnviroScreen 5.0 (draft), OEHHA](https://data.ca.gov/dataset/draft-calenviroscreen-5-0) | Census tract |
| Limited-English households by broad group | U.S. Census **ACS 2019–2023 5-year**, table **C16002** | Census tract |
| Languages isolated for (named) | U.S. Census **ACS 2019–2023 5-year**, table **C16001** | Census tract |
| ZIP + city (per tract) | CalEnviroScreen 5.0 CSV (`ZIP`, `apx_loc`) | Census tract |
| Regional Water Board | [State Water Board boundaries](https://gis.data.ca.gov/maps/5692f02f7c9a47e384522dfb496f522a) — tract centroid → region (point-in-polygon) | Census tract |

### A note on language granularity

CalEnviroScreen itself carries only a single linguistic-isolation score per tract —
no language breakdown — so the "languages isolated for" come from ACS.

The Census publishes the ~40-language table (**B16001**) only down to county/place
level; at the **census-tract** level the finest split available is **C16001's 11
named language groups**. This map therefore uses C16001 for named-language detail.
Household group counts (C16002) are household-level; named-language counts (C16001)
are people age 5+ who speak English less than "very well".

## Rebuilding the data

```bash
# 1. Named + broad language data (needs a free Census API key: https://api.census.gov/data/key_signup.html)
CENSUS_KEY=xxxxxxxx python3 scripts/pull_acs.py       # -> data/acs_lang.json

# 2. Tract geometry from the CalEnviroScreen 5.0 shapefile (reproject + simplify)
#    Download + unzip the shapefile into data/ first (see URL in scripts/build_data.py header),
#    then, with GDAL/ogr2ogr installed:
ogr2ogr -f GeoJSON -t_srs EPSG:4326 -select tract,county,ling,lingP \
  -simplify 100 -lco COORDINATE_PRECISION=4 \
  data/tracts_ces.json data/calenviroscreen50shp_D_12226/CES5_Draft_SHP.shp

# 3. Per-tract ZIP, city, and Regional Board (needs data/ces5.csv + data/rb_boundaries.json)
python3 scripts/tract_meta.py                          # -> data/tract_meta.json

# 4. Join geometry + ACS + metadata into the map's data file
python3 scripts/build_data.py                          # -> docs/tracts.json
```

## Running locally

```bash
cd docs && python3 -m http.server 8137
# open http://127.0.0.1:8137
```

## Layout

```
docs/            GitHub Pages site
  index.html     the map (self-contained; loads tracts.json)
  tracts.json    9,106 tracts: geometry + CES score + ACS language breakdown
scripts/
  pull_acs.py    Census ACS pull -> data/acs_lang.json
  build_data.py  join CES geometry + ACS -> docs/tracts.json
data/            intermediate build inputs (raw shapefile is gitignored)
```

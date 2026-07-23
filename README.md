# California Language Isolation Map

An interactive census-tract map of **linguistic isolation** across California and the
**languages households are isolated in**. Built to modernize an older Power BI
prototype using the latest available data.

**Live demo:** served from `docs/` (GitHub Pages ready).

## What it shows

- **Geography switch** — view the data by **census tract** (9,106, the default) or
  by **PUMA** (281 Public Use Microdata Areas — the geography PUMS microdata is
  published at, ~100k+ people each). PUMAs trade granularity for much larger ACS
  samples. See [PUMA caveats](#what-is-and-isnt-available-at-puma).
- **Isolation percentile** — at **tract**, the CalEnviroScreen 5.0
  linguistic-isolation percentile (each tract ranked against all 9,106). At
  **PUMA**, CalEnviroScreen doesn't exist, so the tab switches to an
  **ACS-based** percentile ranking the 281 PUMAs against each other by %
  limited-English households (C16002). These are two different statistics, so
  the active source is always shown — the tab reads *Isolation percentile
  (CES)* or *(ACS)*, and the legend, tooltip, detail card and CSV column name
  carry it too.
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
- **Regional Water Board buttons** — one click filters and zooms to any of the
  9 Regional Water Quality Control Boards (tract geography; PUMAs have no board).
- **Per-tract detail** — click any area for its isolation score and a
  **population-by-language table (age 5+)**: for each language, the number of
  speakers, that as a **% of the area's population**, and how many are
  limited-English — with a population total. Plus limited-English **households**
  by the four broad language groups.
- **Download CSV** — exports the current filtered view as one row per area (the
  CES 5.0 ⋈ ACS join), keyed on `census_tract_geoid` / `puma_geoid` so it joins
  to any other dataset at that geography. Per language it carries total speakers
  (`pop5_speakers_*`), their share of population (`pct_pop5_*`), and the
  limited-English subset (`pop5_lep_*`), plus `population_5plus` and the
  broad-group limited-English **household** counts (`hh_lep_*`). UTF-8 with BOM
  for Excel.
- Bilingual **English / Spanish** UI, colorblind-safe palette.

## Data sources

| Layer | Source | Level |
|-------|--------|-------|
| Linguistic isolation (`ling`, `lingP`) + tract geometry | [CalEnviroScreen 5.0 (draft), OEHHA](https://data.ca.gov/dataset/draft-calenviroscreen-5-0) | Census tract |
| Limited-English households by broad group | U.S. Census **ACS 2020–2024 5-year**, table **C16002** | Census tract |
| Languages isolated for (named) | U.S. Census **ACS 2020–2024 5-year**, table **C16001** | Census tract |
| ZIP + city (per tract) | CalEnviroScreen 5.0 CSV (`ZIP`, `apx_loc`) | Census tract |
| Regional Water Board | [State Water Board boundaries](https://gis.data.ca.gov/maps/5692f02f7c9a47e384522dfb496f522a) — tract centroid → region (point-in-polygon) | Census tract |
| PUMA language data | U.S. Census **ACS 2020–2024 5-year**, tables **C16002** + **C16001** | PUMA |
| PUMA boundaries | [TIGER/Line 2024 `PUMA20`](https://www2.census.gov/geo/tiger/TIGER2024/PUMA20/) (2020-vintage PUMAs) | PUMA |

### What is (and isn't) available at PUMA

CalEnviroScreen is published at **census-tract level only**, so switching to PUMA
changes what the map can honestly show:

| | Census tract | PUMA |
|---|---|---|
| Isolation percentile | ✅ **CES** `lingP` (vs 9,106 tracts) | ⚠️ **ACS**-derived (vs 281 PUMAs) — labeled `(ACS)`, *not* the CES percentile |
| % isolated households | ✅ from CES `ling` | ✅ computed from ACS C16002 |
| Dominant language / language search | ✅ | ✅ |
| ZIP, city, Regional Water Board | ✅ | ❌ tract-level attributes |
| Address search / 📍 Near me / CSV | ✅ | ✅ |

PUMAs do not nest cleanly inside counties (9 rural PUMAs combine several), so each
PUMA's county list is derived **spatially** — every tract centroid inside the PUMA
contributes its county. The county filter uses that crosswalk.

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

# 5. PUMA geography (optional second dataset). Boundaries:
#    https://www2.census.gov/geo/tiger/TIGER2024/PUMA20/tl_2024_06_puma20.zip
ogr2ogr -f GeoJSON -t_srs EPSG:4326 -select GEOID20,NAMELSAD20 \
  -simplify 0.0005 -lco COORDINATE_PRECISION=4 \
  data/pumas_geom.json tl_2024_06_puma20.shp
CENSUS_KEY=xxxxxxxx python3 scripts/pull_acs.py puma   # -> data/acs_lang_puma.json
python3 scripts/build_puma.py                          # -> docs/pumas.json
```

`build_puma.py` must run **after** `build_data.py`: it seeds its language index
from `docs/tracts.json` so both geographies share identical language IDs (the
language search depends on that).

## Running locally

```bash
cd docs && python3 -m http.server 8137
# open http://127.0.0.1:8137
```

## Layout

```
docs/            GitHub Pages site
  index.html     the map (self-contained; loads tracts.json / pumas.json)
  tracts.json    9,106 tracts: geometry + CES score + ACS language breakdown
  pumas.json     281 PUMAs: geometry + ACS language breakdown (lazy-loaded)
scripts/
  pull_acs.py    Census ACS pull [tract|puma] -> data/acs_lang[_puma].json
  build_data.py  join CES geometry + ACS + metadata -> docs/tracts.json
  tract_meta.py  ZIP, city, Regional Board per tract -> data/tract_meta.json
  build_puma.py  join PUMA geometry + ACS + county crosswalk -> docs/pumas.json
data/            intermediate build inputs (raw shapefile/CSV are gitignored)
```

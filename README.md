# Nola-tree

Count **New Orleans** street trees from **Google Street View** imagery and compare sample estimates against the official **ArborPro / City of New Orleans** inventory (August 20, 2019).

> **v1 is NOLA-only.** ZIP-level comparisons are labeled **`sample≠census`**: a handful of Street View panoramas is not a citywide tree census.

Target repo (do not push from this workspace unless asked): https://github.com/wreingru/Nola-tree

## Features

- Street View Static API client with metadata checks and multi-heading sweeps (0°/90°/180°/270°)
- CSV / GeoJSON sample points; default fixtures for ZIP **70115**
- Pluggable detectors: offline **OpenCV** color/shape heuristic (default), optional Google **Vision API**
- Cross-heading dedupe; optional nearby GIS inventory match when a cache is present
- Baked-in 2019 ZIP site counts and top species benchmarks (no PDF required at runtime)
- `tree-counter run --dry-run` works without an API key

## Official inventory (benchmark)

Source: [Total Tree Inventory Summary Report (PDF)](https://nola.gov/nola/media/PPW/Total-Tree-Inventory-Summary-Report.pdf)

| Metric | Value |
|--------|------:|
| Sites | ~105,813 |
| Trees | 104,117 |
| Stumps | ~1,696 |
| Street ROW | 98,610 (93.2%) |
| Parks | 7,203 (6.8%) |

Top species: crape myrtle 30,244 (28.6%), southern live oak 21,775 (20.6%), bald cypress 5,409 (5.1%), hybrid holly 3,529 (3.3%), slash pine 3,098 (2.9%).

Static copies live under `data/inventory_summary.json`.

GIS (best-effort, graceful offline fallback):

- data.nola.gov dataset `g94y-wr47` (Tree Locations)
- `https://gis.nola.gov/arcgis/rest/services/Basemaps/TreeCanopy/MapServer/0`

## Setup

Python **3.11+** recommended.

```bash
cd Nola-tree
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env and set GOOGLE_MAPS_API_KEY for live Street View
```

Enable **Street View Static API** on your Google Maps Platform key. Never commit `.env` or real keys.

Optional Vision detector:

```bash
pip install google-cloud-vision
export TREE_DETECTOR=vision
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

## How to run

Dry-run (fixtures, no key):

```bash
tree-counter run --dry-run --zip 70115
# or
python -m tree_counter run --dry-run --zip 70115
```

Writes:

- `artifacts/report.json`
- `artifacts/report.md`
- `artifacts/images/*.jpg`

Live Street View:

```bash
tree-counter run --live --zip 70115 --input path/to/points.csv
```

Show baked benchmarks:

```bash
tree-counter benchmarks
tree-counter benchmarks --zip 70115
```

## Inventory comparison caveats

Street View sampling **under- and over-counts** relative to the 2019 field inventory:

1. **Occlusion** — cars, trucks, buildings, and dense canopy hide trunks/crowns.
2. **Private trees** — yard trees appear in imagery but are often outside street ROW inventory.
3. **2019 drift** — plantings, removals, and storms (e.g. Ida) change the urban forest.
4. **ROW vs parks** — the official summary includes both street easements and park trees.
5. **Detector limits** — the default OpenCV heuristic is intentionally simple for offline/CI use.
6. **Double counting** — multi-heading sweeps may still merge poorly across opposite views.

Reports always mark ZIP comparisons as **`sample≠census`**.

## Project layout

```
src/tree_counter/
  cli.py              # tree-counter entrypoint
  pipeline.py         # end-to-end run
  city_profile.py     # NOLA CityProfile (v1)
  streetview/         # Static API + fixtures
  sampling/           # CSV/GeoJSON points
  detection/          # opencv + optional vision
  inventory/          # GIS cache + comparison
data/
  inventory_summary.json
  fixtures/           # sample points + placeholder images
tests/
```

## Tests

```bash
pytest -q
```

Includes a dry-run e2e that uses bundled placeholder images.

## License

MIT

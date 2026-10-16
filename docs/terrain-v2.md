# Terrain susceptibility v2 (FABDEM + extra street features)

Improvements #10 (FABDEM) and #11 (extra features) of `docs/plans/2026-10-16-IMP-ml-data-street-improvements.md`.
Built by `scripts/fetch_fabdem.py`, `scripts/fetch_terrain_inputs.py`, `scripts/build_susceptibility.py`
(`floodready/gis/terrain.py`, `floodready/gis/features.py`). No flood labels are used anywhere.

## Data and licences

| Data | Use | Licence / credit |
|---|---|---|
| Copernicus GLO-30 | old DEM (kept for comparison) | (c) DLR/Airbus, provided under COPERNICUS by the EU and ESA |
| FABDEM V1-2, tile N03E101 | DEM with building and forest bias removed | (c) University of Bristol, Hawker et al. 2022, **CC BY-NC-SA 4.0 (non-commercial)**. Fine for the hackathon prototype; SDP needs the authors' permission for commercial use, and derived data must stay share-alike |
| ESA WorldCover 2021 v200, tile N03E099 | built-up share (class 50) | (c) ESA, CC BY 4.0 |
| OSM waterways (river, stream, canal, drain, ditch), 5 km around BBR | distance to nearest waterway | (c) OpenStreetMap contributors (ODbL) |

Credits were added to the resident app credit line (en and ms), `README.md`, `CLAUDE.md` and the build plan.
FABDEM is distributed only as 10 x 10 degree zips (556 MB); the fetch script reads the zip directory with HTTP range requests and downloads just the 1 x 1 degree tile (about 26 MB of the 556). The tile opens in rasterio as EPSG:4326, bounds 100.9999-101.9999 E / 3.0001-4.0001 N, 3600 x 3600 cells, elevation -63 to 1927 m (tile-wide; the negative minimum is not inside the BBR clip, which is why it was not investigated further).

## Features per street (all along the street, sampled every 10 m)

| Column | Meaning | More flood-prone when |
|---|---|---|
| `hand_m_mean` (`hand_m_min` kept) | height above nearest drainage, FABDEM | low |
| `twi_mean` (`twi_max` kept) | topographic wetness index | high |
| `water_dist_m` | mean distance to the nearest OSM waterway | small |
| `slope_deg_mean` | slope of FABDEM | small (flat ground drains slowly) |
| `built_share_100m` | share of 10 m WorldCover cells within 100 m that are built-up | high (impervious runoff) |

Score = equal-weight mean of the five percentile ranks across the township's streets (`features.combine_ranks`), then split into fifths (`features.fifths`, class 5 = most flood-prone, each class about 20%). Equal weights were fixed before looking at the memorandum streets; they are not fitted. `susceptibility_v1` keeps the original GLO-30 class for reference. `score_mean` is the shipped score (0 to 1 for v2).

## GLO-30 vs FABDEM over BBR (8 km clip, 267,806 cells)

GLO-30 minus FABDEM: mean +2.43 m, median 1.5 m, 95th percentile 8.6 m.

| Cells | mean | median | 95th pct |
|---|---|---|---|
| built-up share over 50% | 1.87 m | 1.39 m | 5.8 m |
| built-up share under 5% | 3.24 m | 1.90 m | 12.6 m |

The expectation "building-dense areas drop by several metres" is only partly met: dense built-up cells drop by about 1.9 m on average (median 1.4 m), i.e. 1-2 m, which fits low-rise houses at 30 m. The biggest corrections (mean 3.2 m, p95 12.6 m) are in non-built cells, which is where forest and plantation canopy is removed. So most of the change comes from vegetation, not buildings.

## Evaluation on the memorandum streets

Held-out check, never used to fit or weight anything: 4 named streets, 61 street segments (Jalan Makyong 38, Jalan Sumazau 20, Persiaran Sungai Keramat 1, Persiaran Batu Belah 2). Share of those segments in classes 4-5 (about 40% expected by chance, because classes are fifths) and the median percentile of their score among all 943 streets (0.50 by chance):

| Variant | Hit rate (classes 4-5) | Median percentile | Segments per class 1/2/3/4/5 |
|---|---|---|---|
| GLO-30, old score (HAND + TWI) | 62.3% | 0.699 | 1/7/15/19/19 |
| FABDEM, old score | 70.5% | 0.688 | 0/7/11/30/13 |
| **FABDEM + new features (shipped)** | **78.7%** | **0.755** | 0/7/6/28/20 |

The best variant by this check is FABDEM + new features and that is what ships in `assets/geo/bbr_streets.geojson`.

Single-feature view (information only; not used to choose weights): HAND 68.9%, TWI 63.9%, slope 65.6%, distance to waterway 86.9% (median percentile 0.773), built-up share 26.2% (median percentile 0.41, i.e. the memorandum streets are somewhat less built-up than average, the opposite of the assumed direction). The equal-weight combination therefore gains from the waterway distance and loses a little from the built-up share. The direction of the built-up share is physically argued and was kept; dropping or reweighting it because of this result would be fitting to the check.

## Limits

- The check has only 4 named streets (61 segments, 38 of them one street, Jalan Makyong). One street dominates the hit rate; a difference of a few points is noise. The ranking FABDEM+new > FABDEM > GLO-30 is consistent with expectation but not statistical proof.
- OSM drains and ditches are only as complete as the volunteers mapped them (612 segments within 5 km: 324 drain, 250 ditch, 31 stream, 7 river). Streets in poorly mapped areas look farther from water than they are.
- HAND and TWI are computed on the FABDEM clip with the same stream threshold (500 cells) as before; the per-cell index raster (`data/interim/susceptibility_bbr_v2.tif`) is the HAND + TWI index on FABDEM only. The new features are per street, so the raster does not show them.
- Tides, drainage capacity and culverts are not modelled. This is a ranking of streets, not a depth forecast.
- FABDEM is non-commercial (CC BY-NC-SA 4.0).

## Reproduce

```bash
python scripts/fetch_fabdem.py
python scripts/fetch_terrain_inputs.py --township BBR
python scripts/build_susceptibility.py --township BBR   # prints all variants, ships the best by the memorandum check
```

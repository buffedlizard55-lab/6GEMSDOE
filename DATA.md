# Data — what it is, where it came from, and how it is verified

## Official files

The competition supplies its data on a **login-gated** page:
<https://www.drivendata.org/competitions/306/competition-doe-gems/data/> —
unauthenticated requests redirect to `/accounts/login/` (re-verified 2026-09-25 and 2026-09-26).
The filenames as published on that page are the middle column below; the competition
prose calls them `training_features.tif`, `labels.tif` and `sample_submission.tif`,
which is why both names appear throughout this repo.

| File in this repo | Official filename | Bytes | sha256 (verified here) |
|---|---|---|---|
| `data/training_features.tif` | `gems-geodawn-numerical-features.tif` | 418,912,844 | `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5` |
| `data/labels.tif` | `existing_faults.tif` | 425,830 | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` |
| `data/sample_submission.tif` | `example_submission.tif` | 1,599,597 | `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` |

## Provenance chain

1. The official bytes were mirrored from the DrivenData data tab and recorded in a
   pinned manifest (`data/bridge/manifest.json`, generated 2026-09-17 by
   `scripts/make_data_bridge.py` in the transport repository).
2. Because GitHub rejects blobs ≥ 100 MB, the 419 MB feature stack is transported as
   **five concatenated parts** (94,371,840 B × 4 plus 41,425,484 B). Each part's
   sha256 is pinned separately in `src/gems/spec.py`.
3. `scripts/fetch_and_verify_data.py` re-verifies each part, concatenates, and
   re-verifies the whole-file sha256 **before** placing anything in `data/`. A mismatch
   aborts and deletes the partial file. It also refuses a manifest whose hashes
   disagree with `src/gems/spec.py` — so the transport repo is trusted only insofar as
   its bytes hash correctly.

**Independently re-verified on 2026-09-25 and 2026-09-26**: all five parts (size + sha256), the
reassembled 418,912,844-byte file, and both small files. All eight hashes matched (2026-09-26: `scripts/fetch_and_verify_data.py` 3/3 OK, `scripts/validate_submission.py` 13/13 PASS).

The 419 MB stack is deliberately **not committed** to git (`data/training_features.tif`
is in `.gitignore`); it is fetched and hash-verified on demand. The two small files
are committed because the format gate needs the authoritative footprint to compare
against, and it verifies their sha256 before using them.

## What is actually inside (measured, not quoted)

**`training_features.tif`** — 19 bands, float32, 3730 × 3292, EPSG:32611, 100 m,
origin (243350, 4508550), nodata sentinel `-3.4028234663852886e+38` (the most
negative float32 — *not* NaN), LZW, uncompressed-block layout `(1, 3292)`.

The band descriptions, read from the file's own TIFF tags:

| # | Band | Meaning (from the file's own tag) |
|---|---|---|
| 1 | `mag_anom` | Magnetic anomaly — deviation from expected Earth's magnetic field |
| 2 | `rtp` | Reduced to pole magnetic data |
| 3 | `tmi_hg` | Total magnetic intensity horizontal gradient |
| 4 | `geod_2ndinv` | Geodetic second invariant (strain-rate tensor magnitude) |
| 5 | `iso_grav_anom_slope` | Isostatic gravity anomaly slope |
| 6 | `tc` | "Tilt angle **or** total curvature — magnetic field derivative for edge detection" (ambiguous by its own wording) |
| 7 | `geod_shearrate` | Geodetic shear rate |
| 8 | `geod_dilaterate` | Geodetic dilatation rate |
| 9 | `tmi_vg` | Total magnetic intensity vertical gradient |
| 10 | `deq_n100a15` | Distance to earthquake |
| 11 | `iso_grav_anom_vg` | Isostatic gravity anomaly vertical gradient |
| 12 | `det_elev` | Detrended elevation |
| 13 | `iso_grav_anom` | Isostatic gravity anomaly |
| 14 | `tmi` | Total magnetic intensity |
| 15 | `depth_to_base_surf` | Depth to basement surface |
| 16 | `ieq_n100a15` | Earthquake intensity/density |
| 17 | `cond_surf` | Conductivity surface |
| 18 | `iso_grav_anom_hg` | Isostatic gravity anomaly horizontal gradient |
| 19 | `det_elev_slope` | Detrended elevation slope |

**`labels.tif`** — int8, 1 band, nodata `-1`. Values: `-1` at 7,111,787 px, `0` at
5,106,385 px, `1` at 60,988 px. **No positive pixel lies outside the footprint.**

**`sample_submission.tif`** — float32, nodata NaN, 5,167,373 finite pixels. It is
**not** an all-zero file, despite the problem page describing it as "a sample
submission that predicts total fault absence": it contains `0.0` at 5,106,385 pixels
and `1.0` at exactly the 60,988 catalogue fault pixels. It is a copy of the label
raster in submission format. Its NaN mask is byte-identical to the labels' nodata
mask, which is what makes it the authoritative definition of "inside the footprint".

## Feet on the ground

| Quantity | Value | Derivation |
|---|---|---|
| Grid | 3730 × 3292 = 12,279,160 px | measured |
| Scored footprint | 5,167,373 px (42.08%) | finite pixels in the sample submission |
| All-19-band-valid | 5,165,840 px (42.07%) | measured; 1,533 px *smaller* than the submission footprint |
| Fault pixels | 60,988 | labels == 1 |
| Fault coverage | **1.18% of the footprint**, 0.50% of the grid | 60,988 / 5,167,373 and / 12,279,160 |
| Kernel | 300 m = exactly 3.0 px | 300 / 100 |

## External data (allowed, and part of the research plan)

External data is explicitly encouraged "provided you or your team possess the
necessary licenses" ([competition home](https://www.drivendata.org/competitions/306/competition-doe-gems/),
"Use of external data"). The sources this project's plan relies on, all free and public:

| Source | What it gives | Link |
|---|---|---|
| GeoDAWN airborne magnetic + radiometric surveys | the feature backbone | <https://doi.org/10.5066/P93LGLVQ> |
| INGENIOUS Great Basin Regional Dataset Compilation | the training labels | <https://doi.org/10.15121/1881483> |
| USGS 3DEP 1 m DEM tiles | scarp-scale topography (not yet used) | bucket `prd-tnm.s3.amazonaws.com`, prefix `StagedProducts/Elevation/1m/Projects/` (verified 2026-09-25 and re-verified 2026-09-26 — still blocked in this sandbox, so not fetched here); the newer seamless 1 m collection is the cleaner authoritative source to re-derive the tile list from: <https://doi.org/10.5066/P13LJKFS> |
| USGS Quaternary Fault and Fold Database | label provenance | <https://earthquake.usgs.gov/hazards/qfaults/> |
| Competition-cited prior art | Mattéo et al. 2021; Hermant et al. 2025 | see `research.html` on the site |

## 1 m DEM — status and the honest caveat

The DEM is distributed as a link list inside a PDF, not as data. That PDF **has no
text layer**, so any extraction is OCR-based and must be re-verified against the USGS
bucket listing rather than trusted. A prior session reported (not independently
re-verified here): 722 (project, tile) pairs parsed, 867 http strings, URLs resolved
against the authoritative S3 listing, project variants `NV_WestCentral_EarthMRI_2020_D20`,
`NV_EastCentral_2021_D21`, `CA_SierraNevada_B22`, `NV_EastCentral_2621_D21`,
`NV_Humboldt_2021_D21`, plus documented irregularities in the source list (duplicate
rows, path/filename project mismatches, garbled hostnames). Treat those numbers as
"reported upstream, needs re-derivation" — they are **not** used in any score here.

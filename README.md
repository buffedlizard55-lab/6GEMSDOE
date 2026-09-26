# 6GEMSDOE — the single canonical entry for the DOE GEMS Prize

**Competition:** The Geologic Enhanced Mapping System (GEMS) Prize Challenge,
U.S. Department of Energy Office of Geothermal, run on DrivenData.
<https://www.drivendata.org/competitions/306/competition-doe-gems/>

**Task:** predict, per pixel, the probability that a *geological fault* is present
across the GeoDAWN region of northwestern Nevada and adjacent eastern California, as
a single-band float32 GeoTIFF on a 100 m grid in EPSG:32611.

**Prize structure:** $300,000 total. Phase 1 — $50,000 split equally across the top
five, scored on a private expert-labelled fault set. Phase 2 — $250,000
($100k/$70k/$40k/$25k/$15k), re-scoring **the same one submission** against a label
set expanded from expert review of every team's predictions.

**Metric:** distance-weighted Tversky index, alpha = 0.2 (false positives),
beta = 0.8 (false negatives), 300 m triangular kernel.

**Ends:** Dec. 3, 2026, 11:59 p.m. UTC.

> ### ⚠ One account, one repo, one site — currently VIOLATED upstream
> The hosting account holds **11** GEMS-named repositories, five of them complete
> copies of this project, and GitHub Pages is enabled and built on **all 11**. This
> repository is designated the single canonical
> entry; nothing here creates a second registration, site or entry. The full audit,
> the rule citations and the remediation steps are in
> **[ACCOUNT_STATUS.md](ACCOUNT_STATUS.md)**. Read it before uploading anything.

---

## Start here

| If you want to… | Read |
|---|---|
| **Submit to the competition** | **[EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)** — the download-to-upload path |
| See the published site | <https://buffedlizard55-lab.github.io/6GEMSDOE/> |
| Check a claim against its source | **[VERIFICATION.md](VERIFICATION.md)** |
| Know what the data is and how it was verified | **[DATA.md](DATA.md)** |
| Know what we cannot do yet | **[LIMITATIONS.md](LIMITATIONS.md)** |
| Know what to do next | **[NEXT_STEPS.md](NEXT_STEPS.md)** |
| Understand the audit finding | **[ACCOUNT_STATUS.md](ACCOUNT_STATUS.md)** |

## The submission file

The file to upload is built by `scripts/build_submission.py`, published in
`downloads/`, and gated by `scripts/validate_submission.py` — which **exits non-zero**
on any format violation. In particular it refuses a file containing a NaN inside the
scored footprint: that is the exact condition which makes the DrivenData form answer
*"Predicted values must be in range [0, 1]"* even when every finite value is in range.
`tests/test_gate.py` builds that broken file and asserts it is rejected.

## Repository layout

```
src/gems/metric.py      distance-weighted Tversky index, from the published formula
src/gems/spec.py        pinned grid constants + sha256 pins of the official files
src/gems/raster.py      submission IO and the hard format gate
src/gems/features.py    derived structural features (edges, curvature, lineaments)
src/gems/placement.py   metric-aware placement, with the break-even derivation
src/gems/cv.py          spatially blocked, buffered cross-validation

scripts/fetch_and_verify_data.py   place the official rasters, verify every sha256
scripts/validate_submission.py     THE HARD GATE (run before any upload)
scripts/build_rank_tables.py       global percentile-rank LUTs (agreement channels)
scripts/build_features.py          105-channel derived feature stack (disk-backed)
scripts/analysis.py                baselines, band-identity tests, blocked CV
scripts/experiment.py              controlled A/B: does a change raise the score?
scripts/build_submission.py        train + predict + place + gate the GeoTIFF
scripts/candidate_writeup.py       per-candidate Phase-2 record from the shipped file
scripts/build_site.py              regenerate the published site from evidence

tests/                  metric vs the official worked example; gate incident tests
data/                   pinned official labels + template (small); big raster fetched
downloads/              the submission file(s)
```

## Reproduce everything

```bash
pip install --break-system-packages numpy scipy rasterio scikit-learn tifffile pillow pytest
python scripts/fetch_and_verify_data.py       # official rasters, every sha256 verified
python scripts/analysis.py --only spec,baselines,bands
python scripts/build_rank_tables.py           # rank LUTs (~2 min)
python scripts/build_features.py              # 105-channel stack (~15 min)
python scripts/analysis.py --only cv
python scripts/experiment.py --configs baseline,extended,agreement   # controlled comparison
python scripts/build_submission.py --tag hgb88-topk03 \
       --strategy "topk_hard@0.03" --n-channels 88 --save-prob
python -m pytest tests/ -q
python scripts/build_site.py
```

## Honest status

Every score in this repository is a **proxy** measured against the public catalogue
of known faults. Both prize rounds are scored against *private, newly identified*
faults, so no number here is a leaderboard prediction, and we state that wherever a
number appears. The model shipped here is a gradient-boosting classifier over sampled
pixels — not the reference solution's ResNet-18 U-Net — because this host has 2 CPUs,
4 GB of RAM and no GPU. See [LIMITATIONS.md](LIMITATIONS.md).

**Blocked-CV proxy for the shipped file: 0.1698 mean DTI** against the public
catalogue, versus 0.1119 for the placement used previously. Both are proxies measured
on held-out spatial blocks; neither is a leaderboard value. See
[EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) for how that improvement was obtained
and why it does not change the fact that the real test set is unmapped faults.

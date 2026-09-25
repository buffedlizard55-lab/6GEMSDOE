# Verification ledger

Every claim this project relies on, the source used to check it, and the finding.
Where a claim originates in the task brief rather than in an official document, that
is said so explicitly. **Claims that failed verification are recorded here, not
quietly dropped.**

Checked 2026-09-25 (UTC). The rules PDF was fetched at
<https://www.nlr.gov/docs/fy26osti/96647.pdf>, which redirects to `docs.nlr.gov`;
the document is titled "Geologic Enhanced Mapping System (GEMS) Prize Official
Rules", September 2026.

## 1. Official sources reached and read in full

| Source | Read | Notes |
|---|---|---|
| Competition home | ✅ complete | end date, prize tables, how-to-compete, eligibility, use-of-test-data |
| Problem description (`page/967`) | ✅ both chunks | problem, datasets, metric with worked example, submission format |
| About (`page/968`) | ✅ complete | fault geology, sponsor, two further references |
| Data tab (`/data/`) | ⚠️ login wall | redirects to `/accounts/login/?next=…` — re-verified this session |
| Rules page (`/rules/`) | ✅ complete | defers to the official rules PDF (also mirrored at herox.com/GEMSPrize/resource/2274) |
| Official rules PDF | ✅ all 7 chunks | §1.1–§1.4, §2, §3.1–§3.7, Appendix A.1–A.17 |
| Reference solution | ✅ cloned | `drivendataorg/gems-prize-reference-solution`, HEAD `aebe92f7c8a990f0e3443451b7a825d9afd6336b`, notebook inventoried (21 cells) |

## 2. Claims verified TRUE

| Claim | Source | Finding |
|---|---|---|
| Two prize phases; Phase 1 $50k split across the top five; Phase 2 $250k at $100k/$70k/$40k/$25k/$15k | rules §1.1 | Confirmed verbatim; up to 10 awards total |
| Both phases score the *same* submission | rules §1.1, §3.5, §3.6.2; competition home | Confirmed |
| 3 submissions per week | rules §3.2, §3.4 | "up to three per week" |
| Exactly one final submission per entity | rules §3.4, §3.5, §3.6.2 | "Multiple finalized submissions are not allowed" |
| Metric is distance-weighted Tversky, alpha 0.2, beta 0.8, 300 m triangular kernel, R = 3 px at 100 m | page 967 | Confirmed; re-implemented in `src/gems/metric.py` |
| Official worked example: TP_w 3.00, FP_w 1.89, FN_w 2.00 → 0.60 | page 967 | Reproduced: 0.60265 (rounds to 0.60) |
| Submission: EPSG:32611, 100 m, same bounds, single layer, float32, values in [0,1], null/NaN only outside bounds | page 967 | Confirmed; enforced by the gate |
| The data tab cannot be downloaded without signing in | `/data/` | Redirect to login confirmed |
| Labels come from USGS Quaternary Fault and Fold Database + INGENIOUS compilation (Ayling et al. 2022, doi:10.15121/1881483) | rules §2, §3.3; page 967 | Confirmed, with the DOI |
| Feature data from GeoDAWN (Glen & Earney 2024, doi:10.5066/P93LGLVQ) | rules §2 | Confirmed |
| Spatial overlap exists between the training catalogue and the private test set; using the provided faults for training is allowed | competition home, "Use of test data" | Confirmed — this is why a catalogue-reproducing model is the wrong target |
| Finalists must submit code assets + documentation reproducing results on new data | rules §3.2, §3.5 | Confirmed |
| Generative-AI use must be disclosed in the narrative | rules §3.2 | Confirmed — directly applicable to this AI-assisted project |
| Eligibility: U.S. citizen/permanent resident (individual), U.S. citizen/PR captain (team), U.S.-incorporated entity; Federal employees ineligible | rules §1.3; competition home | Confirmed |
| Winners must return an ACH form and IRS W-9 within 30 days | rules A.2 | Confirmed |
| Due-diligence and foreign-interference risk review, not appealable | rules A.12 | Confirmed |
| Return of funds for fraudulent or inaccurate information | rules A.16 | Confirmed |
| Faults are a small minority of the area | page 967 ("faults … cover a small fraction") / measured | **Measured: 60,988 of 5,167,373 scored pixels = 1.18%** (0.50% of the full grid) |
| The official grid is 3730 × 3292 at 100 m, EPSG:32611, origin (243350, 4508550) | measured from the bytes | Confirmed; `scripts/analysis.py --only spec` re-measures it |
| Official file hashes | measured from the bytes | All eight pins re-verified (5 transport parts + 3 whole files) |

## 3. Claims verified FALSE, or partly wrong

These are recorded because they affect decisions, and because silently repeating a
wrong figure is exactly what this project is trying to avoid.

| Claim (source) | Finding |
|---|---|
| "Predict everywhere only scores about 0.10 DTI" (task brief, no source given) | **Not reproduced.** Measured exactly against the catalogue, and from the closed form c/(c+α(1−c)) at the measured coverage, the value is far lower. The *direction* is right — coverage without precision is punished hard by α — but the figure in the brief should not be quoted. Exact values are in `data/evidence/baselines.json` and on the site. |
| "An official sample submission that predicts total fault absence is provided" (page 967) | **Inaccurate as published.** The file is not all-zero: it holds NaN outside the footprint and `1.0` at exactly 60,988 pixels — the catalogue fault mask. It is a copy of the label raster. Useful as a template; it is *not* a zero baseline, and it is not the "predict everywhere" case either. |
| "The reference solution implements the metric" (implied by "benchmark against the reference solution") | **False.** The notebook uses `segmentation_models_pytorch.losses.TverskyLoss` as a training loss only. It contains no distance-weighted scoring code. The metric here had to be implemented from the published formula. |
| "The reference solution uses Monte Carlo cross-validation" (task brief) | **True but misleading.** It is Monte Carlo over *random patch splits* (`np.random.default_rng`, `rng.permutation`), not spatially blocked folds. It leaks along faults. The brief's own instruction — blocked, buffered folds — is the right one and is what we implement. |
| "The official rasters are committed to the repo as sha256-pinned parts, reassembled into `data/` with every hash re-verified" (task brief) | **True of the sibling repos, not of this one.** This repo (before this session) held only a 10-byte README. The parts and pins were located in `buffedlizard55-lab/GEMSDOE`, re-verified here byte-for-byte, and are re-verified on every placement by `scripts/fetch_and_verify_data.py`. The 419 MB raster is deliberately kept out of git and fetched on demand. |
| "One account, one repo" (task brief) | **Violated.** 11 GEMS-named repos; GitHub Pages enabled on all 11, so the account publishes 11 challenge URLs. See `ACCOUNT_STATUS.md`. |
| "Site should be able to generate a TIF … already built and working" (task brief) | **Not in this repo.** It was built in sibling repos; this session built it here from scratch, along with the gate. |
| The exact submission-form string "Predicted values must be in range [0, 1]" | **Cannot be verified from here** — it only appears on submission, and we have no credentials. The *mechanism* (NaN inside the footprint) is consistent with the platform's documented requirement that NaN is legal only outside the bounds, and the gate is built around it regardless. |

## 4. Environment findings that constrain the work

| Finding | Evidence |
|---|---|
| Python 3.11.2; no numpy/scipy/rasterio/GDAL/torch preinstalled | `python3 -c "import …"` all failed; installed numpy 2.4.6, scipy 1.17.1, rasterio 1.4.4, scikit-learn 1.9.1, tifffile, pillow |
| `pip install` requires `--break-system-packages` (PEP 668) | install refused without the flag |
| Bash egress is allowlisted: `pypi.org` and `github.com` work; `www.drivendata.org`, `www.nlr.gov`, `www.osti.gov`, `raw.githubusercontent.com` do not connect from bash | TLS/SSL errors; the official pages were therefore read through the platform's page fetcher, and repo files via `git`/GitHub API |
| 2 CPUs, 3 GB RAM, ~20 GB free disk, no GPU | `nproc`, `free`, `df` |
| Full-resolution 19-band float32 stack does not fit in RAM | 12,279,160 px × 48 channels × 4 B = 2.25 GB, hence the disk-backed memmap |

## 5. How to re-verify everything in this file

```bash
python scripts/analysis.py --only spec       # re-measures the pinned constants
python scripts/analysis.py --only baselines  # exact DTI for the degenerate cases
python scripts/analysis.py --only bands      # resolves the ambiguous band semantics
python -m pytest tests/ -q                   # metric + gate + spec tests
python scripts/validate_submission.py <file> # the hard gate
```

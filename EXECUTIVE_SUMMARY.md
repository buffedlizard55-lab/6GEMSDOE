# Executive summary — generating a competition submission

**The whole point of this repository is the one file you upload.** This page is the
shortest path to it, followed by what has and has not been verified.

## 1. Get the file (one download, one upload)

1. **Download** the submission GeoTIFF from the published site
   (<https://buffedlizard55-lab.github.io/6GEMSDOE/>) — the download button is the
   first thing on the page — or from `downloads/` in this repository.
2. **Sign in** to DrivenData and open the competition:
   <https://www.drivendata.org/competitions/306/competition-doe-gems/>
3. Click **Submit** → **Make new submission** (the competition home page documents
   this exact flow under "How to compete", step 6).
4. **Upload the file** and paste the methodology note shown on the site (the file
   name is content-addressed — the current file is `gems6_hgb48-thr030_01be9644f2.tif`
   (sha256 `01be9644f2ec0df9…`) — so it can be told apart from earlier attempts later.
5. That is also the file to select as the **single final submission** for both prize
   rounds. Only one selection is allowed, and it must be made without knowing the
   private scores.

**Budget note.** Each entity gets up to three scored submissions per week (§3.4) and
exactly one final submission across both rounds (§3.5, §3.6.2). Do not spend a slot
until the file has passed `scripts/validate_submission.py` locally.

## 2. What the file must satisfy (all rules quoted from the official pages)

| Rule | Requirement | Source |
|---|---|---|
| CRS | same projected CRS as the training data — UTM 11N, EPSG:32611 | problem description, "Submission format" |
| Resolution | 100 m | same |
| Bounds | same bounds as the training data; outside the bounds is null or NaN | same |
| Layers | a single layer | same |
| Datatype | 32-bit float | same |
| Values | between 0 and 1, higher = higher fault probability | same |
| Size | one GeoTIFF for the whole GeoDAWN study area | rules §3.2 |

## 3. What the shipped file is, and what it measured

Built by `scripts/build_submission.py --strategy threshold --threshold 0.30`
(deterministic: rebuilding reproduces the same sha256):

| Property | Value |
|---|---|
| File | `downloads/gems6_hgb48-thr030_01be9644f2.tif` |
| Bytes | 3,214,769 |
| sha256 | `01be9644f2ec0df9324cfd36ef516bd35a3456b9164b30995ba66e9e1c63be43` |
| Gate | **PASS**, all 13 checks including NaN-inside-footprint |
| Training | 60,988 catalogue fault pixels + 400,000 sampled negatives, 48 channels |
| Model | `HistGradientBoostingClassifier(max_iter=300, lr=0.08, max_leaf_nodes=31, min_samples_leaf=40)` |

Measured on **spatially blocked, buffered folds** (4×4 blocks, 300 m buffer), scored
against the public catalogue — a proxy, not a leaderboard value:

| Placement | mean blocked DTI |
|---|---|
| **binary at 0.30 (shipped)** | **0.1119** |
| binary at 0.40 | 0.1055 |
| raw probability surface | 0.0763 |
| skeleton (thinned to one pixel) | 0.0829 |
| skeleton thinned to every 4th px (the brief's rule) | 0.0621 |
| predict 1 everywhere inside the footprint (no model) | 0.0580 |

So the shipped placement improves on the raw surface by about
47%, and the brief's
4–5 px spacing rule would have given up about
44% of the
achievable score. The threshold was chosen by this sweep, not by taste.

## 4. What is verified in this repository

* **The official bytes are hash-verified.** `data/training_features.tif`
  (418,912,844 B, sha256 `4371c82e…`), `data/labels.tif` (425,830 B, sha256
  `7ba308cc…`) and `data/sample_submission.tif` (1,599,597 B, sha256 `2176d08e…`)
  were reassembled from sha256-pinned transport parts and every hash re-computed
  here. `src/gems/spec.py` holds the pins; `scripts/fetch_and_verify_data.py`
  re-verifies them and refuses to place a mismatch.
* **The grid constants are measured, not assumed** — 3730 × 3292, EPSG:32611, 100 m,
  origin (243350, 4508550), footprint 5,167,373 pixels. Re-measured by
  `scripts/analysis.py --only spec` and compared against the pins.
* **The metric is implemented from the published formula** in
  `src/gems/metric.py`, and unit-tested against the competition page's own worked
  example (TP_w = 3.00, FP_w = 1.89, FN_w = 2.00 → 0.60) plus hand-computable cases.
* **The format gate is a hard gate.** `scripts/validate_submission.py` exits non-zero
  on any violation, and it specifically refuses a file with a NaN inside the scored
  footprint — the condition that makes the submission form answer *"Predicted values
  must be in range [0, 1]"* even though every finite value is legal.
  `tests/test_gate.py` proves it rejects exactly that file.

## 5. What is NOT claimed

* **No leaderboard score is claimed or predicted.** The competition is scored against
  private expert labels; we do not have them, and we have not uploaded anything.
  Every score in this repo is explicitly labelled a proxy against the public
  catalogue.
* **The model here is not the reference solution's model.** The reference is a
  ResNet-18 U-Net trained over five Monte-Carlo folds. This host has 2 CPUs, 3 GB of
  RAM and no GPU, so the shipped model is a histogram gradient-boosting classifier on
  sampled pixels over 48 feature channels. It is weaker, and it is labelled as such.
* **The 1 m DEM is not incorporated.** See `LIMITATIONS.md`.

## 6. The single outstanding risk to eligibility

The hosting account holds **eleven** GEMS-named repositories and has **GitHub Pages
enabled on all eleven** for this one challenge. That is a rules-relevant duplication, and it is
audited in `ACCOUNT_STATUS.md`. Until the other copies are archived or deleted, this
entry is exposed to an Appendix A.12 due-diligence finding. This repository is the
designated single entry; nothing here creates a second registration, site or entry.

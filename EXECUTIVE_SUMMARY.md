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
4. **Upload the file** and paste the methodology note shown on the site. The file
   name is content-addressed — the current file is
   `gems6_hgb88-topk03_33cec71ff0.tif` (sha256 `33cec71ff0…`) — so it can be told
   apart from earlier attempts later.
5. That is also the file to select as the **single final submission** for both prize
   rounds. Only one selection is allowed, and it must be made without knowing the
   private scores.

**Budget note.** Each entity gets up to three scored submissions per week (§3.4) and
exactly one final submission across both rounds (§3.5, §3.6.2). Do not spend a slot
until the file has passed `scripts/validate_submission.py` locally.

## 2. What the file must satisfy (all rules quoted from the official pages)

Re-fetched and re-checked on 2026-09-25 and **re-verified 2026-09-26 00:20 UTC and again 01:19 UTC** from
<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> (both chunks fetched via platform fetcher; submission format, metric, and worked example re-confirmed; gate 13/13 PASS, hashes 3/3 OK — `data/evidence/session_reverification_2026-09-26T0119Z.json`).

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

Built by

```bash
python scripts/build_submission.py --tag hgb88-topk03 \
       --strategy "topk_hard@0.03" --n-channels 88 --max-neg 400000 --iters 300
```

| Property | Value |
|---|---|
| File | `downloads/gems6_hgb88-topk03_33cec71ff0.tif` |
| Bytes | 1,652,883 |
| sha256 | `33cec71ff00b3f32d0d59c81c156f3f1488ffef46baa4b6499094e24ea1875ab` |
| Gate | **PASS**, all 13 checks including NaN-inside-footprint |
| Values | exactly two distinct values: `0.0` and `1.0` |
| Predicted pixels | 155,021 = 3.00% of the 5,167,373-pixel footprint |
| Training | 60,988 catalogue fault pixels + 400,000 sampled negatives, 88 channels |
| Model | `HistGradientBoostingClassifier(max_iter=300, lr=0.08, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0)` |

### Why this file rather than the previous one

Two changes, both measured on **spatially blocked, buffered folds** (same folds, same
training budget, same evaluation code — `scripts/experiment.py`), not asserted:

| Change | Blocked-CV mean DTI | vs previous |
|---|---|---|
| previous file: fractional probabilities, threshold 0.30 | 0.1119 | — |
| write `1.0` instead of the model probability, same threshold | 0.1520–0.1668 | **+36% to +49%** |
| **shipped: top 3% of the footprint by probability, written as `1.0`** | **0.1698** | **+52%** |

The first change follows from an algebraic identity of the published metric. Writing
`FN_w = n_gt − TP_w` (which is what the definitions on page 967 give) reduces the
score to

```
DTI = TP_w / ( beta * n_gt + alpha * FP_w + (1 - beta) * TP_w )
```

and the `beta * n_gt` term does **not** scale with the predicted probability, so DTI
is strictly increasing under `p → λ·p` for any λ up to the cap at 1. A submission
that carries fractional confidence values is donating score to nobody.

The second change is a budget choice. `FP_w` is an absolute sum over predicted
pixels while `TP_w`/`FN_w` are per-ground-truth-pixel sums, so the right amount to
predict depends on how many fault pixels the (unseen) test set contains. Measured
against the public catalogue the nominal optimum is a 5% budget (0.1750), but the
private set is *new* faults, almost certainly fewer than the 60,988 catalogue
pixels. Re-scoring the identical predictions against ground truth thinned to whole
fault traces gives:

| Budget | full catalogue GT | 50% of traces | 25% of traces | worst-case loss |
|---|---|---|---|---|
| 2% | 0.1589 | 0.1292 | 0.0643 | −9.2% |
| **3% (shipped)** | **0.1698** | **0.1278** | **0.0631** | **−5.0%** |
| 5% | 0.1750 | 0.1184 | 0.0580 | −12.7% |

3% is the minimax-regret choice: it gives up 3% in the best case to avoid a 13% loss
in the worst.

### What did NOT work (recorded so it is not retried)

* **40 extra multi-scale channels** — horizontal-gradient magnitude at σ = 1.5/3/6 px
  on five surfaces, tilt and analytic-signal amplitude at matched scales, multi-scale
  curvature, local texture, structure-tensor lineaments on conductivity and RTP.
  Blocked-CV at the shipped hyperparameters: 0.1698 with them vs 0.1628 without
  (a real but small gain); at the round-1 hyperparameters the two were identical
  (0.1729 vs 0.1730). Kept, because it is never worse — but it is not the win.
* **Lineament post-processing** (max over straight segments of 3/5/9 px in 8
  orientations, and 50/50 mixes): best variant 0.1637 vs 0.1750 without. The filter
  raises isolated pixels that happen to lie on a line, which costs false positives
  for the same budget.
* **More training capacity** (400,000 negatives and 300 iterations vs 200,000 and
  200): no gain at the 5% budget (0.1694 vs 0.1730). Kept anyway because the final
  model is trained on all four blocks rather than three.
* **17 cross-family agreement channels + agreement-gated placement** (the explicit
  form of the brief's third research priority, added this session): 0.1670 vs 0.1698
  at the shipped 3% budget on the full catalogue, and 0.112–0.116 for the gated
  placement in every configuration, on identical blocked folds
  (`data/evidence/experiments_agreement.json`). The channels help the hard
  trace-removed simulation (+1% at a 2% budget) but are not strictly better on the
  shipping axis, so the 88-channel file stands. Full audit and reasoning:
  `RESEARCH.md` §9 and the site's experiments card.
* **PU-style down-weighting of long catalogue traces** (`--pos-weight itrace`,
  positives weighted 1/√trace-length): 0.1650 (88ch) / 0.1631 (105ch) at 3% vs
  0.1698 / 0.1670 unweighted, lower in every robustness column
  (`data/evidence/experiments_itrace.json`). The long mapped traces are cleaner
  examples of the same physics, not a different target — down-weighting them
  removes the anchor of the probability surface.

## 4. What is verified in this repository

* **The official bytes are hash-verified.** `data/training_features.tif`
  (418,912,844 B, sha256 `4371c82e…`), `data/labels.tif` (425,830 B, sha256
  `7ba308cc…`) and `data/sample_submission.tif` (1,599,597 B, sha256 `2176d08e…`)
  were reassembled from sha256-pinned transport parts and re-verified on 2026-09-26 (3/3 hashes OK; `scripts/fetch_and_verify_data.py` OK) and every hash re-computed here. `src/gems/spec.py` holds the pins;
  `scripts/fetch_and_verify_data.py` re-verifies them and refuses to place a
  mismatch.
* **The grid constants are measured, not assumed** — 3730 × 3292, EPSG:32611, 100 m,
  origin (243350, 4508550), footprint 5,167,373 pixels. Re-measured by
  `scripts/analysis.py --only spec` and compared against the pins.
* **The metric is implemented from the published formula** in `src/gems/metric.py`,
  and unit-tested against the competition page's own worked example
  (TP_w = 3.00, FP_w = 1.89, FN_w = 2.00 → 0.60) plus hand-computable cases, a
  brute-force re-derivation, and the `TP_w + FN_w = n_gt` identity.
* **The format gate is a hard gate.** `scripts/validate_submission.py` exits non-zero
  on any violation, and it specifically refuses a file with a NaN inside the scored
  footprint — the condition that makes the submission form answer *"Predicted values
  must be in range [0, 1]"* even though every finite value is legal.
  `tests/test_gate.py` proves it rejects exactly that file. Re-run on the shipped file 2026-09-26: 13/13 PASS (`scripts/validate_submission.py`).
* **The new harness reproduces the old number exactly.** `scripts/experiment.py` on
  the baseline 48-channel model gives `soft@0.3` = 0.1119 / min 0.0933 / max 0.1253 —
  identical to the value the previous submission was chosen on. So the improvements
  above are measured against the same yardstick, not a new one.

## 5. What is NOT claimed

* **No leaderboard score is claimed or predicted.** The competition is scored against
  private expert labels; we do not have them, and we have not uploaded anything.
  Every score in this repo is explicitly labelled a proxy against the public
  catalogue on held-out blocks.
* **The catalogue is the wrong target and we know it.** Both rounds score faults
  MISSING from the catalogue (the competition home page confirms the test set is
  "newly identified faults" with spatial overlap to the training faults). Our proxy
  measures rediscovery of *known* faults from held-out blocks, which is easier than
  the real task. The true score will be lower than 0.1698; we do not know by how
  much.
* **The model here is not the reference solution's model.** The reference is a
  ResNet-18 U-Net trained over five Monte-Carlo folds. This host has 2 CPUs, 4 GB of
  RAM and no GPU, so the shipped model is a histogram gradient-boosting classifier on
  sampled pixels over 88 feature channels. It is weaker, and it is labelled as such.
* **The 1 m DEM is not incorporated.** See `LIMITATIONS.md`.

## 6. The single outstanding risk to eligibility

The hosting account holds **eleven** GEMS-named repositories and has **GitHub Pages
enabled on all eleven** for this one challenge — five of them complete copies with
their own sites and data. That is a rules-relevant duplication, re-verified and
audited in `ACCOUNT_STATUS.md`. Until the other copies are archived or deleted, this
entry is exposed to an Appendix A.12 due-diligence finding. This repository is the
designated single entry; nothing here creates a second registration, site or entry.

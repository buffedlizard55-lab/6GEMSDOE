# Submission guide and the one-entry record

## The two-click path

1. **Download** `downloads/gems6_hgb88-topk03_33cec71ff0.tif` (the link is the first
   thing on <https://buffedlizard55-lab.github.io/6GEMSDOE/>).
2. **Upload** it at <https://www.drivendata.org/competitions/306/competition-doe-gems/>
   → *Submit* → *Make new submission*, pasting the methodology note below.

Before either step, run the gate locally:

```bash
python scripts/validate_submission.py downloads/gems6_hgb88-topk03_33cec71ff0.tif
```

Exit code 0 means the file satisfies every published format rule. Non-zero means do
**not** upload it. Re-run in this checkout on **2026-09-26 01:19 UTC: PASS, 13/13**
(also 2026-09-26 00:20 and 2026-09-25 — all 13 checks including NAN-INSIDE-FOOTPRINT;
see `data/evidence/session_reverification_2026-09-26T0119Z.json`).

## Why the file must pass the gate first

Each entity gets **three scored submissions per week** (rules §3.4) and exactly **one
final submission** across both rounds (§3.5, §3.6.2). A malformed upload wastes a
slot. The gate checks, in order:

1. readable single-band GeoTIFF
2. dtype `float32`
3. CRS `EPSG:32611`
4. 100 m pixels in both axes
5. 3292 × 3730
6. exact origin/geotransform (bounds equality)
7. all finite values within [0, 1]
8. no `+inf`/`-inf`
9. **no NaN inside the scored footprint** ← the incident this gate exists for
10. the finite mask equals the official footprint (relaxable only for experiments)
11. the declared nodata is NaN

Check 9 is the one that matters. When a NaN sits inside the footprint, the platform
answers *"Predicted values must be in range [0, 1]"* even though every finite value is
legal, because its range test trips on the NaN. `tests/test_gate.py` constructs exactly
that file and asserts it is rejected, while `values-in-0-1` still passes — so the
gate is provably catching the right condition rather than a proxy for it.

## Naming and the comment field

Files are content-addressed: `gems6_<strategy>_<sha256[:10]>.tif`. The strategy tag
records the placement rule, so attempts can be told apart later without opening them.

| Field | Value |
|---|---|
| Current file | `downloads/gems6_hgb88-topk03_33cec71ff0.tif` |
| sha256 | `33cec71ff00b3f32d0d59c81c156f3f1488ffef46baa4b6499094e24ea1875ab` |
| Bytes | 1,652,883 |
| Strategy tag | `hgb88-topk03` = HistGradientBoosting, 88 channels, top 3% of the footprint written as 1.0 |
| Predicted pixels | 155,021 (3.00% of the 5,167,373-px footprint) |
| Distinct values | exactly `0.0` and `1.0` |
| Superseded file | `gems6_hgb48-thr030_01be9644f2.tif`, sha256 `01be9644f2ec0df9324cfd36ef516bd35a3456b9164b30995ba66e9e1c63be43` — 0.1119 blocked-CV, removed from `downloads/` so only one file is offered |

**Suggested comment** (this is the one to paste — it describes our single chosen
candidate, not a batch):

> One entry. Probability surface from HistGradientBoosting over 88 channels — the 19
> official GeoDAWN/USGS bands plus derived horizontal-gradient magnitude,
> analytic-signal amplitude, tilt derivative, multi-scale curvature, break-in-slope
> and structure-tensor lineament features — trained on all catalogue fault pixels plus
> 400k sampled negatives, validated on spatially blocked, buffered folds (300 m
> buffer). The submission keeps the top 3% of the footprint by predicted probability
> and writes 1.0 on those pixels: the published metric reduces to
> DTI = TP_w/(0.8·n_gt + 0.2·FP_w + 0.2·TP_w), which is strictly increasing in the
> predicted value, so fractional confidence gives score away. The budget is the
> minimax-regret choice across ground-truth sizes (worst-case loss 5% vs 13% for the
> 5% budget that leads on the full catalogue). Blocked-CV proxy DTI 0.1698 against
> the public catalogue — a proxy, not a leaderboard value. Format verified by
> scripts/validate_submission.py (13/13 checks incl. NaN-inside-footprint), file
> sha256 `33cec71ff0…`.

## The one-entry record — FILL THIS IN (human, with credentials)

> This is the single place where the canonical facts are recorded. It is deliberately
> blank: this sandbox has no DrivenData session, and inventing values here would be
> worse than leaving it empty.

| Field | Value |
|---|---|
| DrivenData account that is our official entry | `_to be filled by the account holder_` |
| Submissions already used this week / total | `_unknown from this sandbox_` |
| File selected as the single final submission | `_pending_` |
| Date/time selected (UTC) | `_pending_` |
| Generative-AI disclosure statement written? | `_pending — required by rules §3.2_` |
| Winning Model Documentation Template completed? | `_pending — required for finalists, §3.5_` |
| Eligibility confirmed (rules §1.3)? | `_pending — U.S. citizen/permanent resident, not a Federal employee_` |

## Reminder on the duplication flag

Do not upload from any other repository or site. The hosting account currently holds
eleven GEMS-named repositories with GitHub Pages enabled on all of them, five of them
complete copies of this project; see `ACCOUNT_STATUS.md`. This repository is the
designated single entry, and the rules' due-diligence and return-of-funds terms
(A.12, A.16) are the reason the duplication must be cleaned up rather than left in
place.

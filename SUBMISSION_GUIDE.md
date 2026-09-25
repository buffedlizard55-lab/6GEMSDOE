# Submission guide and the one-entry record

## The two-click path

1. **Download** `downloads/gems6_*.tif` (the newest file is linked from the first
   card on <https://buffedlizard55-lab.github.io/6GEMSDOE/>).
2. **Upload** it at <https://www.drivendata.org/competitions/306/competition-doe-gems/>
   → *Submit* → *Make new submission*, pasting the methodology comment shown on the
   site.

Before either step, run the gate locally:

```bash
python scripts/validate_submission.py downloads/<file>.tif
```

Exit code 0 means the file satisfies every published format rule. Non-zero means do
**not** upload it.

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
records the placement rule (currently `hgb48-thr030`), so attempts can be told apart
later without opening them. The submission comment should describe **our single best
chosen candidate**, not a batch of parallel arms — the rules allow only one final
submission, and the comment is what a reviewer reads.

Suggested comment (regenerate from `data/evidence/submission_report.json` if the file
changes):

> One entry. HistGradientBoosting on 48 channels (19 official GeoDAWN/USGS bands plus
> derived horizontal-gradient, tilt, analytic-signal, curvature, break-in-slope and
> structure-tensor lineament features), trained on all catalogue fault pixels plus a
> sampled negative pool, > scored with spatially blocked and buffered folds (300 m
> buffer). Placement chosen by measured blocked-CV sweep: the probability surface is
> binarised at the CV-optimal threshold of 0.30 (blocked mean DTI
> 0.1119 against the public catalogue, a proxy — the real
> test set is private). Thinning predictions to the brief's 4-5 px spacing scored
> worst (0.0621) and is not used. File sha256
> `01be9644f2ec0df9…`; format verified by scripts/validate_submission.py.

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

## Reminder on the duplication flag

Do not upload from any other repository or site. The hosting account currently holds
eleven GEMS-named repositories with GitHub Pages enabled on all of them, for this
one competition; see `ACCOUNT_STATUS.md`. This repository is the designated single entry,
and the rules' due-diligence and return-of-funds terms (A.12, A.16) are the reason the
duplication must be cleaned up rather than left in place.

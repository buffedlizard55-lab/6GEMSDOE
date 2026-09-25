# Next steps — ordered by expected effect on P(win)

The single remaining blocker to a better score is **model quality and target
alignment**, not data placement or format. Format is solved and gated; the score is
not.

## P0 — do these before spending any submission slot

1. **Confirm the eligibility of the registered competitor** (rules §1.3): U.S. citizen
   or permanent resident, or a U.S.-incorporated entity with such a captain; not a
   Federal employee. An ineligible winner is disqualified regardless of the model.
   Owner: the account holder. Nothing in this repo can check it.
2. **Resolve the duplication flag in `ACCOUNT_STATUS.md`.** One entry, one repo, one
   site. Archive or delete the other ten GEMS repositories and the surplus Pages
   sites, and record which DrivenData account is the entry.
3. **Record the state of the weekly submission allowance** (three per week, §3.4) once
   somebody with credentials can read the submission history, and write the chosen
   final submission into `SUBMISSION_GUIDE.md`.

## P1 — the accuracy work (this is where the score is)

4. **Add the 1 m DEM.** The biggest untapped signal. The link list is OCR-derived from
   a PDF without a text layer, so the extraction must be re-verified against the USGS
   3DEP bucket listing (the authoritative source) rather than trusted. Then derive
   scarp-scale curvature, aspect breaks and roughness from 1 m elevation and
   down-sample to the 100 m scored grid as *features*, never as targets. Needs an
   unrestricted-egress host and a few hundred GB of scratch space; out of scope for
   this sandbox.
5. **Train the reference architecture for real.** A ResNet-18 U-Net with the actual
   Tversky loss (alpha 0.2, beta 0.8) on the 48-channel stack, on a GPU host, using
   **our** blocked folds rather than the reference's random patch split. Compare
   against the gradient-boosting baseline with the same folds and the same gate; only
   promote it if the blocked-CV DTI improves. Then fine-tune the distance-weighted
   quantity directly, not plain Tversky — the loss the reference uses and the metric
   the competition scores are *not* the same function.
6. **Attack the actual target: unmapped faults.** Everything here scores against the
   catalogue. Better proxies for the real target:
   - score only on held-out blocks with the catalogue fault pixels *removed*
     (`gap score`), so credit can only come from structural evidence;
   - hold out whole known fault systems and measure whether the model rediscovers
     them from geophysics alone;
   - use the 2021/2025 deep-learning fault-mapping literature the competition's own
     About page cites as competing baselines.
7. **Write the geological reasoning per candidate.** Phase 2 pays five times Phase 1
   and is graded by geologists reviewing what we flagged. For each high-confidence
   lineament, record: trend relative to Walker Lane / Basin-and-Range kinematics, the
   independent signals that agree (magnetics, gravity, strain rate, seismicity,
   conductivity), and its confidence. A pixel mask alone is not a Phase 2 submission.
8. **Calibrate the probability surface.** The metric rewards calibrated confidence
   near faults and punishes confident predictions far from them. Consider isotonic or
   Platt calibration on held-out blocks, then re-derive placement from the calibrated
   surface.

## P2 — robustness and compliance

9. Fill in the DrivenData **Winning Model Documentation Template** (§3.5 requirement
   for finalists) and write the **generative-AI disclosure** required by §3.2.
10. **Verify the model reproduces on a clean machine**: `scripts/fetch_and_verify_data.py`
    → `build_features.py` → `build_submission.py` → `validate_submission.py` →
    `pytest`. The file's sha256 must be stable for a fixed seed, or the seed must be
    recorded.
11. Extend `tests/` to cover: feature invariance under tile boundaries (the streaming
    builder must equal the full-grid computation — currently argued from the halo
    width, not tested), the blocked-fold buffer geometry, and CV determinism.
12. Re-check the band-identity experiments whenever the official rasters are re-fetched:
    a hash change invalidates every conclusion drawn here.

## Known-good, do not redo

* `scripts/validate_submission.py` is the hard gate and catches the reported
  "Predicted values must be in range [0, 1]" condition. It is tested both ways.
* `src/gems/metric.py` matches the official worked example and brute-force checks.
* The eight sha256 pins and the grid constants are re-verified on every placement.

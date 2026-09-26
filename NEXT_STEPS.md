# Next steps — ordered by expected effect on P(win)

Status 2026-09-25. Data placement is solved (all three official rasters placed and
hash-verified this session). Format is solved and gated. The remaining work is model
quality against the *unmapped-fault* target, and the compliance items.

## P0 — do these before spending any submission slot

1. **Confirm the eligibility of the registered competitor** (rules §1.3): U.S. citizen
   or permanent resident, or a U.S.-incorporated entity with such a captain; not a
   Federal employee, not under 18, not in a Malign Foreign Talent Recruitment Program.
   An ineligible winner is disqualified regardless of the model. Owner: the account
   holder. Nothing in this repo can check it.
2. **Resolve the duplication flag in `ACCOUNT_STATUS.md`.** One entry, one repo, one
   site. Before archiving the other ten, first replace the data path: the pinned bridge
   currently resolves through `buffedlizard55-lab/GEMSDOE` over codeload. Either copy
   the bridge parts into this repo or download the three files from the official data
   tab while signed in — then archive the duplicates.
3. **Record the state of the weekly submission allowance** (three per week, §3.4) once
   somebody with credentials can read the submission history, and write the chosen
   final submission into `SUBMISSION_GUIDE.md`.
4. **Fill in the two mandatory narratives**: the generative-AI disclosure (§3.2 — this
   project is produced with an AI agent, so it is not optional) and, if we are
   finalists, the Winning Model Documentation Template (§3.5).

## P1 — the accuracy work, in the order the evidence suggests

5. **Read the public leaderboard before spending the second and third slot.** The
   competition splits the new-fault set into a public and a private test set and shows
   public-test performance during the competition (page 967, "Competition structure";
   §3.6.1). That is the only real feedback channel available and it costs one of the
   three weekly slots — spend slot 1 on the current file, read the number, then decide.
   Do not read it as the private score: §3.6.2 requires the final choice to be made
   without knowledge of private performance, and the page warns that public scores
   "may not be the same as the final scores on the private leaderboard".
6. **Attack the actual target instead of the catalogue.** Everything here is trained to
   reproduce faults that are already mapped, and both rounds score faults that are
   not. Two of the three candidates are now **measured, both losing**:
   - *PU-style down-weighting of easy (long) catalogue traces* — `--pos-weight itrace`,
     run at the shipped scale on 88 and 105 channels: 0.1650 / 0.1631 at a 3% budget
     vs 0.1698 / 0.1670 unweighted, and lower on every robustness column
     (`data/evidence/experiments_itrace.json`). The hypothesis (the private set is
     short unmapped traces, so long mapped ones should be de-emphasised) did not
     survive contact with the folds: the easiest positives carry the cleanest signal
     of the physical mechanisms, and down-weighting them weakens the anchor of the
     whole probability surface. Do not retry.
   - *Explicit cross-family agreement channels and an agreement-gated placement* —
     `data/evidence/experiments_agreement.json`. The channels are a wash-to-negative
     on the shipping axis (+1% only on the hard trace-removed simulation at 2%);
     the gate loses decisively (0.112–0.116). Do not retry at this budget; the
     machinery stays in the repo as Phase-2 evidence tooling.
   Still open:
   - build a semi-supervised target: the model's own high-confidence predictions in
     held-out blocks, verified against independent signals (magnetics + gravity +
     strain + seismicity agreeing), used as additional positives for a second pass;
   - hold out whole fault *systems* (`--trace-holdout` exists for the diagnostic
     form; whole-system holdout is not yet implemented).
7. **Add the 1 m DEM.** The largest untapped signal and the sharpest expression of
   fault scarps. The link list is OCR-derived from a PDF with no text layer, so it must
   be re-derived from the authoritative USGS 3DEP bucket listing, not trusted. Needs an
   unrestricted-egress host and a few hundred GB of scratch; out of scope for this
   sandbox (egress to the bucket is blocked here — verified 2026-09-25).
8. **Train the reference architecture for real.** A ResNet-18 U-Net with the actual
   Tversky loss (alpha 0.2, beta 0.8) on the 88-channel stack, on a GPU host, with
   **our** blocked folds rather than the reference's random patch split. Only promote
   it if blocked-CV DTI beats 0.1698 using `scripts/experiment.py` unchanged. Then
   optimise the distance-weighted quantity directly — the reference's loss and the
   competition's metric are not the same function.
9. **Write the geological reasoning per candidate.** Phase 2 pays five times Phase 1
   and is graded by geologists reviewing what we flagged. For each high-confidence
   lineament, record: trend relative to Walker Lane / Basin-and-Range kinematics, the
   independent signals that agree (magnetics, gravity, strain rate, seismicity,
   conductivity), its depth estimate from tilt-depth, and a confidence. A pixel mask
   alone is not a Phase 2 submission.

## P2 — robustness and compliance

10. **Verify the model reproduces on a clean machine**: `fetch_and_verify_data.py` →
    `build_features.py` → `experiment.py` → `build_submission.py` →
    `validate_submission.py` → `pytest`. The submission sha256 must be stable for a
    fixed seed, or the seed must be recorded (the seed is 7 in
    `scripts/build_submission.py`).
11. Extend `tests/` to cover: feature invariance under tile boundaries (the streaming
    builder must equal the full-grid computation — currently argued from the halo
    width, not tested), the blocked-fold buffer geometry at block counts other than 4,
    and CV determinism.
12. Re-check the band-identity experiments whenever the official rasters are re-fetched:
    a hash change invalidates every conclusion drawn here.

## Known-good, do not redo

* `scripts/validate_submission.py` is the hard gate and catches the reported
  "Predicted values must be in range [0, 1]" condition. Tested both ways.
* `src/gems/metric.py` matches the official worked example, brute-force checks, and
  the `TP_w + FN_w = n_gt` identity.
* The eight sha256 pins and the grid constants are re-verified on every placement.
* `scripts/experiment.py` reproduces the previous CV numbers exactly (`soft@0.3` =
  0.1119 = the old `binary@0.3`), so it is a safe yardstick for future changes.

## Measured dead ends — do not spend time on these again

* **Lineament post-processing** of the probability surface (max over straight segments
  of 3/5/9 px in 8 orientations, and 50/50 mixes): best variant 0.1637 vs 0.1750
  without it.
* **More training capacity** (400k negatives / 300 iterations vs 200k / 200): no gain.
* **Choosing the budget by its score on the full catalogue.** The nominal optimum
  shifts from 5% to 2% as the ground-truth set shrinks; 3% is the minimax-regret
  choice on both the 4×4 and the 6×6 blocking.
* **Gated top-k placement** (`topk_gate@<frac>` with the cross-family agreement
  gate): 0.112–0.116 vs 0.167–0.170 for the ungated top-k in every channel
  configuration (`data/evidence/experiments_agreement.json`). The gate excludes
  catalogue faults the model already scores well; a budget spent on a stricter,
  less-likely set cannot beat the probability order.
* **The 17 cross-family agreement channels at the shipped budget**: 0.1670 (105ch)
  vs 0.1698 (88ch) at 3% on the full catalogue; the hard (trace-removed) simulation
  moves the other way (+1% at 2%). Not strictly better on the shipping axis — the
  88-channel file stays. The machinery (rank tables, `famrank_*`/`n_agree_*`
  channels, `gated_topk`) is kept in the repo for the Phase-2 evidence record
  (`scripts/candidate_writeup.py` uses the same family ranks).
* **PU-style inverse-trace-length positive weights** (`--pos-weight itrace`):
  0.1650 (88ch) / 0.1631 (105ch) at 3% vs 0.1698 / 0.1670 unweighted — lower on
  every robustness column too (`data/evidence/experiments_itrace.json`). The
  easiest catalogue traces carry the cleanest physical signal; down-weighting
  them weakens the anchor of the probability surface.

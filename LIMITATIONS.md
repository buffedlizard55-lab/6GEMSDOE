# Limitations — what this project cannot do yet, and why

Stated plainly, because a plan that hides its constraints is a plan that fails late.

## 1. Every score in this repository is a proxy (the big one)

Both prize rounds are scored against **private, newly identified faults** that are
absent from the public catalogue, and the rules confirm the test set is expert-labelled
and partly overlaps the catalogue spatially. Our only labels are the catalogue itself.
So a DTI measured here answers:

> "How well does this reproduce the faults that are already known?"

which is explicitly **not** the competition target. A model tuned to maximise that
number can lose the competition while looking excellent locally. Every score in this
repo is therefore labelled a proxy, and the blocked-CV tables report the *gap* case
(held-out blocks, no catalogue-neighbour leakage) alongside it as the honest analogue.

**Consequence:** we cannot know whether the shipped file is competitive. We can only
know that it is well-formed, reproducible, and built on the right target.

## 2. No leaderboard feedback is available from here

A feedback channel *exists* — the competition splits the new-fault set into a public
and a private test set and shows public-test performance on the leaderboard while the
competition runs (page 967; §3.6.1) — but it needs a DrivenData session, and this
sandbox has none (verified: `/data/` redirects to `/accounts/login/`). We therefore
cannot see prior submissions, remaining weekly allowance, or any public score. The
rules also require the final submission to be chosen *without* knowledge of private
scores (§3.6.2), and the problem page warns that public scores "may not be the same as
the final scores on the private leaderboard", so public feedback is a weak signal at
best. It does mean we are flying blind on relative performance.

## 3. Compute: no GPU, 2 CPUs, 4 GB RAM

* The reference solution is a ResNet-18 U-Net trained over 5 Monte-Carlo folds on
  128 × 128 patches. That is not trainable here: PyTorch is not installed, there is no
  GPU, and a full-resolution 19-band float32 stack (933 MB) plus derived channels
  (≈4.9 GB for the 105-channel stack) already exceeds RAM — hence the
  tile-streaming feature builder and the disk-backed feature memmap.
* The shipped model is `HistGradientBoostingClassifier` over **sampled** pixels
  (all 60,988 positives plus a 400,000-negative sample) on 88 channels. It is
  honest, reproducible and fast; it is also weaker than a full U-Net, and the class
  imbalance is handled by sampling rather than by a loss function.
* Training at full capacity needs an external GPU host (or a GitHub Actions runner
  with more memory and a cached official dataset). Nothing in this repo prevents that:
  `scripts/build_submission.py` takes the same feature stack and the same gate.

## 4. The 1 m DEM is not incorporated

The competition distributes the high-resolution DEM as a link list, not as data. The
list is derived from a PDF with no text layer (the extraction had to be done by OCR),
and the tiles are individual ~100 MB objects across a region spanning terabytes. Two
further obstacles: the links point at the USGS 3DEP bucket, which this sandbox's
egress policy blocks, and the downloads would not fit the workspace.

**Impact:** a genuine topographic signal at 1 m — the sharpest expression of fault
scarps — is missing. The 100 m detrended-elevation curvature features partially
compensate but cannot replace it. This is probably the single largest untapped
accuracy lever available. (Re-verified 2026-09-25 and 2026-09-26: egress to `prd-tnm.s3.amazonaws.com`
and to `www.sciencebase.gov` is blocked from this sandbox, so it cannot be fetched
here at all; it needs a different host.)

## 5. Magnetic/gravity edge products partly duplicate what is provided

The provided stack already contains a horizontal gradient of TMI (`tmi_hg`), a
vertical gradient (`tmi_vg`), an isostatic-gravity horizontal gradient, and a band
`tc` described as "tilt angle **or** total curvature". Where a derived product turns
out to be numerically identical to a provided band, it adds a column without adding
information. `scripts/analysis.py --only bands` measures this empirically (correlation
and median absolute difference per candidate pair) so the redundancy is documented
rather than assumed.

**Measured consequence (2026-09-25).** Appending forty genuinely new multi-scale
channels — horizontal-gradient magnitude at σ = 1.5/3/6 px on five surfaces,
analytic-signal amplitude and tilt derivative at matched scales, multi-scale
curvature, local texture, structure tensor on conductivity and RTP — moved blocked-CV
DTI by essentially nothing at the round-1 hyperparameters (0.1729 with them vs 0.1730
without, on identical folds). They are kept because they were never worse and are
slightly better at the shipped hyperparameters, but the honest reading is that on this
100 m grid the score is limited by the label set, not by the number of derivative
channels.

The same pattern repeats for the 17 cross-family **agreement** channels appended
this session (per-family max percentile rank, family-count and rank-product
channels — the explicit form of the task brief's third research priority):
0.1670 vs 0.1698 at the shipped 3% budget, 0.1706 vs 0.1750 at 5%, on identical
blocked folds (`data/evidence/experiments_agreement.json`). They help the hard
trace-removed simulation (+1% at 2%) but not the full-catalogue axis we ship by,
and the agreement-gated placement is decisively worse (0.112–0.116). The reading
does not change: at 100 m, the gradient-boosting model already forms the
cross-family conjunctions from the raw bands; adding them explicitly does not buy
precision.

## 6. Placement is measured only against the catalogue

The metric-aware argument in `src/gems/placement.py` is derived from the published
formula and is exact *given* a probability surface. Whether densifying beats thinning
*in practice* is measured on the catalogue, where the model has an easier job than it
will on unmapped faults. The geometry result (a 300 m kernel does not imply 4–5 px
spacing) is metric algebra and holds regardless.

The value and budget results are stronger than that, because they are algebra plus
measurement rather than measurement alone:

* writing `1.0` instead of the model probability is *provably* better (DTI is strictly
  increasing under `p → λ·p`, because the `β·n_gt` term does not scale), and it
  measured +36% to +49% depending on the threshold;
* the budget choice is hedged against the unknown size of the private test set by
  re-scoring identical predictions against ground truth thinned to whole fault traces.
  The 3% budget is the minimax-regret choice on two independent blockings (4×4 and
  6×6), giving up 3% in the best case to hold the worst case to 5%.

One placement variant that looked plausible — spending the top-k budget on pixels
where several independent physical families agree first (the cross-signal gate,
`topk_gate@<frac>` in `src/gems/placement.py`) — is now measured and loses
decisively: 0.112–0.116 vs 0.167–0.170 ungated, in all channel configurations, all
four folds. The intuition it encoded (independent signals agreeing is strong
evidence) is correct; the mechanism is wrong, because the gate filters by a
property of the *features* while the probability already ranks the *fault evidence*,
and the intersection is a set the model itself would have ranked below its top 3%.

What is *not* hedged is the harder thing: the private faults are genuinely unmapped,
so our per-fault recall on them will be lower than on catalogue faults, and no amount
of placement algebra fixes that.

## 7. Phase 2 deliverables are only partly done

Phase 2 ($250k, five times Phase 1) is judged on what geologists see in our
predictions, and the rules require finalists to supply complete code assets and
documentation (documents describing resources, reproducing results, generating
predictions on new data — §3.5, consistent with DrivenData's Winning Model
Documentation Template). This repo now has the code assets, the reproduction path,
the evidence, and a **deterministic per-candidate generator**:
`scripts/candidate_writeup.py` takes the exact shipped GeoTIFF and the saved
probability surface and writes `CANDIDATES.md` + `data/evidence/candidates.json`
(per-component WGS84 geometry, PCA azimuth, length, probability statistics,
per-family evidence ranks, cross-family agreement, distance to the nearest
catalogue pixel, and the regional kinematic frame — 260 new-to-catalogue
candidates, 466 km of line, for the current file). What is still missing: the
hand narrative that ranks and interprets those candidates for the judge, and the
Winning Model Documentation Template itself. Tracked in `NEXT_STEPS.md`.

## 8. Eligibility is unverified on our side

Rules §1.3 requires the individual competitor to be a U.S. citizen or permanent
resident (or the team captain to be), and excludes Federal employees and several other
categories. Nothing in this repository can verify that, and an ineligible winner is
disqualified however strong the model. This needs a human confirmation and is recorded
as an open item in `ACCOUNT_STATUS.md`.

## 9. Generative-AI disclosure is mandatory

Rules §3.2 requires the narrative to indicate the extent of generative-AI use and how
it was used. This project is produced with an AI agent, so the disclosure is not
optional: it must be written into the finalist narrative. That is an action item, not
a limitation, but it is easy to forget at submission time — so it is listed here.

## 10. Data redistribution

The two small official rasters (`labels.tif`, `sample_submission.tif`, ~2 MB) are
committed because the on-site gate needs the authoritative footprint to compare
against. The 419 MB feature stack is **not** committed; it is fetched and hash-verified
by script. If the sponsor's terms are read as prohibiting redistribution of the
provided rasters in a public repository, the small committed copies should be replaced
with the hash-only manifest — the gate degrades gracefully (it reports that it cannot
verify the footprint rather than silently passing).

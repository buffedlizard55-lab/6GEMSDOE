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

The data tab and the submit form require a DrivenData session; this sandbox has none
(verified: `/data/` redirects to `/accounts/login/`). We therefore cannot see prior
submissions, remaining weekly allowance, or any public score. The rules also require
the final submission to be chosen *without* knowledge of private scores (§3.6.2), so
this is not a blocker for correctness — but it does mean we are flying blind on
relative performance.

## 3. Compute: no GPU, 2 CPUs, 3 GB RAM

* The reference solution is a ResNet-18 U-Net trained over 5 Monte-Carlo folds on
  128 × 128 patches. That is not trainable here: PyTorch is not installed, there is no
  GPU, and a full-resolution 19-band float32 stack (933 MB) plus derived channels
  (2.25 GB total) already exceeds RAM — hence the tile-streaming feature builder and
  the disk-backed feature memmap.
* The shipped model is `HistGradientBoostingClassifier` over **sampled** pixels
  (all positives in the fold plus a sampled negative pool) on 48 channels. It is
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
accuracy lever available.

## 5. Magnetic/gravity edge products partly duplicate what is provided

The provided stack already contains a horizontal gradient of TMI (`tmi_hg`), a
vertical gradient (`tmi_vg`), an isostatic-gravity horizontal gradient, and a band
`tc` described as "tilt angle **or** total curvature". Where a derived product turns
out to be numerically identical to a provided band, it adds a column without adding
information. `scripts/analysis.py --only bands` measures this empirically (correlation
and median absolute difference per candidate pair) so the redundancy is documented
rather than assumed.

## 6. Placement is measured only against the catalogue

The metric-aware argument in `src/gems/placement.py` is derived from the published
formula and is exact *given* a probability surface. Whether densifying beats thinning
*in practice* is measured on the catalogue, where the model has an easier job than it
will on unmapped faults. The geometry result (a 300 m kernel does not imply 4–5 px
spacing) is metric algebra and holds regardless.

## 7. Phase 2 deliverables are only partly done

Phase 2 ($250k, five times Phase 1) is judged on what geologists see in our
predictions, and the rules require finalists to supply complete code assets and
documentation (documents describing resources, reproducing results, generating
predictions on new data — §3.5, consistent with DrivenData's Winning Model
Documentation Template). This repo has the code assets, the reproduction path and the
evidence; it does **not** yet have a per-candidate geological write-up (the "why this
lineament is a fault" narrative) or the Winning Model Documentation Template filled
in. Those are tracked in `NEXT_STEPS.md`.

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

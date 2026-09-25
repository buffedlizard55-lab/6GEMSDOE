# Account and repository status — AUDIT RESULT: FLAGGED

**Audited 2026-09-25 (UTC) via the GitHub API, immediately before any other work.**

## The rule being audited

The official rules cap each entity at **three submissions per week** and **exactly
one final submission**, and that single submission is the one scored in **both**
prize rounds:

| Constraint | Citation | Verbatim |
|---|---|---|
| 3 submissions/week | rules §3.4 Feedback | "each participating entity may submit more than one set of predictions for automated scoring on the competition platform up to three per week" |
| One final submission | rules §3.5 What To Submit | "Before the end of the competition, you must choose only one submission for evaluation across both prize rounds." |
| Chosen blind | rules §3.6.2 | "You must choose only one submission to use for scoring across both prize rounds, and you must make your decision without knowledge of your scores on the private test set." |
| Single-entity award | rules A.3 | "The prize administrator will award a single dollar amount to the designated primary submitter" |
| Due diligence | rules A.12 | "All applications submitted to DOE are subject to a due diligence review." … "risk review … for potential risks of foreign interference … An elimination based on a risk review is not appealable." |
| Return of funds | rules A.16 | "if the prize was made based on fraudulent or inaccurate information provided by the competitor to DOE, DOE has the right to demand that any prize funds … be returned" |

Source (verified reachable from this environment on 2026-09-25, redirects to
`docs.nlr.gov`): <https://www.nlr.gov/docs/fy26osti/96647.pdf>

The landing page the DrivenData rules page points at is
<https://www.herox.com/GEMSPrize/resource/2274>.

## What the audit found

One GitHub account, `buffedlizard55-lab`, owns **eleven** repositories named after
this one competition:

| Repository | Commits | Last push (UTC) | Size (diskUsage) | Substantive? |
|---|---|---|---|---|
| `GEMSDOE` | 30 | 2026-09-24T23:07:17Z | 400,811 KB | yes |
| `GEMSDOE2` | 22 | 2026-09-25T17:32:05Z | 421,640 KB | yes |
| `GEMSDOE3` | 25 | 2026-09-25T17:36:00Z | 24,765 KB | yes |
| `5GEMSDOE` | 15 | 2026-09-25T19:17:46Z | 0 KB | yes |
| `6GEMSDOE` | 1 | 2026-09-25T18:21:38Z | 0 KB | **this repo (was an empty stub)** |
| `GEMSDOE4`, `7GEMSDOE`, `8GEMSDOE`, `GEMSDOE9`, `GEMSDOE10`, `11GEMSDOE` | 1 each | 2026-09-25 | 0 KB | stubs (README only) |

**GitHub Pages is enabled on all eleven repositories**, so this one account
publishes eleven challenge URLs under `buffedlizard55-lab.github.io/` (the four
substantive repos have live, built sites; the stubs serve a README-only page). (`GEMSDOE`, `GEMSDOE2`, `GEMSDOE3`, `5GEMSDOE`, `6GEMSDOE`, and one
further Pages-enabled repo). Each of the four substantive repos carries its own
`data/bridge` copy of the official rasters and its own set of generated
`submission.tif` files under `data/evidence/runs/`.

Reproduction (read-only, no writes):

```bash
gh repo list buffedlizard55-lab --limit 100 --json name,pushedAt,diskUsage
gh repo view buffedlizard55-lab/6GEMSDOE --json createdAt,pushedAt,defaultBranchRef
gh api repos/buffedlizard55-lab/GEMSDOE3/contents/data --jq '.[].name'
gh api repos/buffedlizard55-lab/6GEMSDOE/pages
```

## Why this is flagged rather than ignored

Duplicating one project across many repositories and site copies is, in form,
exactly the pattern the eligibility and anti-fraud terms exist to catch: several
sites, several leaderboard identities, one test. The risk is not theoretical — an
A.12 risk review or an A.16 clawback does not require intent, only the appearance
of duplicated or misrepresented entry, and an elimination on those grounds is **not
appealable**.

Two specific hazards:

1. **Score contamination.** A leaderboard score obtained from another registration
   or another repo copy is not our data. Adopting it (or using it as an "arm" of a
   comparison) would misrepresent our single entry's performance.
2. **Submission multiplication.** Submitting the same underlying test from more than
   one site multiplies the three-per-week allowance, which is precisely what the
   limit forbids.

## Decision and actions

* **`6GEMSDOE` is designated the single canonical repository and the single
  published site** for this entry.
* **No second registration, no second site, and no second entry** are created by
  this session.
* **No hypothesis will be tested against any other repository**, and no submission
  is to be uploaded from any other copy.
* **No live submission is made by this session.** See "Unknowns" below.
* This repository contains no pointer that treats another repo as authoritative: the
  data transport is a *sha256-pinned* bridge (each part hash pinned in
  `src/gems/spec.py` and re-verified on placement), which means the bytes are
  trusted because of their hash, **not** because of which repo served them.

## Unknowns that require a human decision (not resolvable from this sandbox)

1. **Which DrivenData registration is the official entry**, and whether any
   submission has already been uploaded from it. This sandbox has no DrivenData
   credentials — the data tab redirects to `/accounts/login/` (re-verified
   2026-09-25), so the answer cannot be read from here.
2. **Whether the weekly allowance has already been consumed this week**, and with
   which files. The submission history is only visible when signed in.
3. **Confirmation that the account holder is eligible** under rules §1.3 — a U.S.
   citizen or permanent resident (or a U.S.-incorporated entity with a
   U.S.-citizen/permanent-resident captain). Nothing else in this repo can be
   completed honestly without that confirmation, because an ineligible winner is
   disqualified however good the model is.

## Recommended remediation

1. Keep `6GEMSDOE` (this repo) as the only entry and the only published site.
2. **Archive** the other ten repositories, then delete them once the pinned data
   bridge and the evidence files have been copied here (the bridge parts and
   `data/evidence/` evidence are the only irreplaceable content; the 419 MB official
   raster is reproducible from the pinned mirror by
   `scripts/fetch_and_verify_data.py`).
3. Record, in one place, which DrivenData account is the entry and which submission
   is selected as final — this repo's `SUBMISSION_GUIDE.md` has the fixed slot for
   that record.

# Account and repository status — AUDIT RESULT: STILL FLAGGED

**Re-audited 2026-09-26 (UTC) via the GitHub API, before any other work this
session.** Every number below was produced by a read-only `gh` call in this
session; nothing is carried over from memory. Re-verified the submission gate and the official rasters in the same session (see `data/evidence/data_verification.json` and `scripts/validate_submission.py` 13/13 PASS).

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

Sources, both re-fetched this session:
<https://www.nlr.gov/docs/fy26osti/96647.pdf> (the official rules PDF) and
<https://www.drivendata.org/competitions/306/competition-doe-gems/> (the
competition home page, which confirms **Competition End Date: Dec. 3, 2026,
11:59 p.m. UTC** and the prize split: Initial round $50,000 across the top five,
Final round $250,000 as $100k/$70k/$40k/$25k/$15k).

Eligibility (rules §1.3, re-read this session) is worth restating because it is a
hard gate, not a formality: an individual competitor "must be a U.S. citizen or
permanent resident"; a team needs a U.S.-citizen/permanent-resident captain;
"Non-DOE Federal entities and Federal employees are not eligible"; and
individuals "under 18 years of age" are not eligible.

## What the audit found (re-verified this session)

One GitHub account, `buffedlizard55-lab`, owns **eleven** repositories named after
this one competition, and **GitHub Pages is enabled and built on all eleven**.

| Repository | Contents (top-level, this session) | Pages status | Disk (KB) | Last push (UTC) |
|---|---|---|---|---|
| `GEMSDOE` | full site + `data/` + `scripts/` + `src/` | built | 400,811 | 2026-09-24T23:07:17Z |
| `GEMSDOE2` | full site + `data/` + `scripts/` + `src/` | built | 421,640 | 2026-09-25T17:32:05Z |
| `GEMSDOE3` | full site + `data/` + `evidence/` + `scripts/` + `src/` | built | 24,765 | 2026-09-25T17:36:01Z |
| `GEMSDOE4` | full site + `data/` + `scripts/` + `src/` + `docs/` (promoted from a README stub to a full copy on 2026-09-25T21:03Z) | built | 55,484 | 2026-09-26T00:36:16Z |
| `5GEMSDOE` | full site + `data/` + `scripts/` + `src/` | built | 460,609 | 2026-09-25T23:44:33Z |
| **`6GEMSDOE`** | **this repository — the designated single entry** | built | 3,194 | 2026-09-26T00:41:09Z |
| `7GEMSDOE` | `README.md` only | built | 0 | 2026-09-25T18:22:03Z |
| `8GEMSDOE` | `README.md` only | built | 0 | 2026-09-25T18:22:23Z |
| `GEMSDOE9` | `README.md` only | built | 0 | 2026-09-25T18:31:02Z |
| `GEMSDOE10` | `README.md` only | built | 0 | 2026-09-25T18:31:25Z |
| `11GEMSDOE` | `README.md` only | built | 0 | 2026-09-25T18:33:58Z |

Reproduce (read-only):

```bash
gh repo list buffedlizard55-lab --limit 100 --json name,pushedAt,diskUsage
gh api repos/buffedlizard55-lab/<repo>/pages --jq '.html_url, .status'
gh api repos/buffedlizard55-lab/<repo>/contents/ --jq '[.[].name] | join(" ")'
```

Note the shape of the finding: **five** of the eleven are complete, independent
copies of the same project (site, data bridge, code), and the remaining five are
`README.md`-only stubs that nevertheless publish a Pages URL. That is eleven
published URLs for one challenge.

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

## One dependency to be aware of before deleting anything

This repository's official rasters are **sha256-pinned** and re-verified on every
placement (`scripts/fetch_and_verify_data.py`). The pinned transport currently
resolves through `buffedlizard55-lab/GEMSDOE`, one of the duplicate repositories
(`--source codeload`). That is a **byte transport, not a second entry**: the parts
are trusted because each one's sha256 matches the pin in `src/gems/spec.py`, not
because of which repository served them, and the reassembled file's hash is
re-checked before it is written into `data/`. Verified this session — the 418,912,844-byte
`training_features.tif` was placed and its sha256 confirmed as
`4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5`.

**Practical consequence:** if the duplicate repositories are deleted, this data
path must be replaced first — either by downloading the three files from the
official data tab while signed in to DrivenData, or by keeping a first-party copy
of the pinned parts. Do not delete the duplicates and then discover the bytes are
gone.

## Decision and actions

* **`6GEMSDOE` is designated the single canonical repository and the single
  published site** for this entry. GitHub Pages: `source = main`, `status = built`,
  <https://buffedlizard55-lab.github.io/6GEMSDOE/>.
* **No second registration, no second site, and no second entry** was created by
  this session, and none will be.
* **No hypothesis is tested against any other repository**, and no submission is
  uploaded from any other copy. Every number on the site and in
  `data/evidence/*.json` was produced inside this repository.
* **No live submission is made from this sandbox.** It has no DrivenData session;
  the data tab redirects to `/accounts/login/`.
* This session's improvement work (see `data/evidence/experiments*.json`) is
  cross-validated inside this repo on our own held-out blocks. It is one model
  line, not a set of parallel arms across registrations.

## Unknowns that require a human decision (not resolvable from this sandbox)

1. **Which DrivenData registration is the official entry**, and whether any
   submission has already been uploaded from it.
2. **Whether the weekly allowance has already been consumed this week**, and with
   which files. The submission history is only visible when signed in.
3. **Confirmation that the account holder is eligible** under rules §1.3.
4. **How many of the eleven repositories are deliberate** and which are artefacts
   of earlier sessions. Only the account holder can say; this audit reports the
   state, it does not guess intent.

## Recommended remediation

1. Keep `6GEMSDOE` (this repo) as the only entry and the only published site.
2. Move a first-party copy of the pinned data bridge into this repo (or download
   the three official files from the data tab while signed in), **then** archive
   the other ten repositories and delete them once the data path is confirmed.
3. Record, in `SUBMISSION_GUIDE.md`, which DrivenData account is the entry and
   which submission file is selected as final.

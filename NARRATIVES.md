# Narratives — drafts required by the rules (human review needed)

Status: **DRAFT, written 2026-09-26.** Nothing here has been submitted anywhere.
The account holder must read, correct, and approve every line before any of it
is used — see `ACCOUNT_STATUS.md` for the items only a human can resolve.

## 1. What the rules require (quoted verbatim, re-verified 2026-09-26)

Rules §3.2, "Indication of use of generative artificial intelligence (AI)
technology, if applicable" (<https://www.nlr.gov/docs/fy26osti/96647.pdf>):

> "Using generative AI technology in the development of your prize submission is
> allowed. However, you must **indicate in the narrative** (not included in the
> word count) the extent to which, if any, you used generative AI technology and
> how you used it to develop your submission (including all submission elements
> described in this official rules document). You are responsible for the
> accuracy, authenticity, and authorship representations of your submission
> under consideration, including content developed with generative AI tools.
> Relying on generative AI may introduce significant risks, including but not
> limited to, research misconduct resulting from fabrication, falsification, or
> plagiarism when proposing, performing, or reviewing research or in reporting
> research results."

Finalists additionally owe, per §3.2 "Solution verification and delivery" and
§3.5: the solution's **complete code assets and documentation**, including a
description of the resources required to build and run the solution, sufficient
to **reproduce the winning results and generate predictions on new data
samples**, with documentation consistent with DrivenData's Winning Model
Documentation Template.

## 2. Draft generative-AI disclosure (paste into the narrative)

> **Generative-AI use disclosure.** This submission was developed with the
> assistance of an AI coding agent operating inside the entry's single code
> repository (`6GEMSDOE`), under the direction of the competitor. The agent
> drafted analysis code, the trained-model pipeline, the submission-format gate,
> the verification site, and the accompanying documentation. Every numeric claim
> about data, scores, and file formats in the repository is produced by
> executing code against the competition's published files — the official
> rasters are verified by sha256 before use, the metric is unit-tested against
> the competition page's own worked example, and the submission file passes a
> 13-check format gate — rather than asserted from model memory. All
> bibliographic citations were resolved by hand against the published record,
> and three citations that initially carried wrong DOIs were corrected and
> recorded in the audit log (`RESEARCH.md` §7). The competitor reviewed the
> repository, ran the verification steps, and takes responsibility for the
> accuracy, authenticity, and authorship of the submission, including the
> AI-assisted content. No AI-generated content is presented as measured where
> it was not: every reported score is labelled a proxy against the public
> catalogue of known faults, not a prediction of leaderboard performance.

Why each sentence is safe to sign:

| Sentence | Evidence in this repo |
|---|---|
| single code repository | `ACCOUNT_STATUS.md` designates `6GEMSDOE` the canonical entry |
| agent drafted code/pipeline/gate/site/docs | true by construction; session re-verification records (`data/evidence/session_reverification_*.json`) document the AI-assisted working process |
| numeric claims produced by executing code | `scripts/*` + `data/evidence/*.json`; the site renders only from evidence (`scripts/build_site.py`) |
| rasters verified by sha256 | `src/gems/spec.py` pins; `scripts/fetch_and_verify_data.py` |
| metric tested vs worked example | `tests/test_metric.py` (TP_w 3.00, FP_w 1.89, FN_w 2.00 → 0.60) |
| 13-check gate | `scripts/validate_submission.py`; `tests/test_gate.py` |
| citations resolved; 3 wrong DOIs corrected | `RESEARCH.md` §7; `VERIFICATION.md` §2 |
| scores labelled proxies | `EXECUTIVE_SUMMARY.md` §5; `LIMITATIONS.md` §1 |

## 3. Finalist-delivery checklist (§3.2 / §3.5)

| Required item | State in this repo |
|---|---|
| Complete code assets | `src/`, `scripts/`, `tests/`, `pyproject.toml` — present |
| Description of resources to build/run | `README.md` (reproduce block) + `VERIFICATION.md` §4 + `LIMITATIONS.md` §3 — present |
| Reproduces the winning results | deterministic seed (`scripts/build_submission.py`, seed 7); full chain re-runnable — **clean-machine rerun not yet done** (`NEXT_STEPS.md` P2-10) |
| Generates predictions on new data | `scripts/build_submission.py` takes the feature stack as input — present, untested on non-GeoDAWN grids |
| Documentation per Winning Model Documentation Template | **not yet written** — template to be obtained from DrivenData at finalist stage |
| Narrative in English, Word/PDF-readable | this draft is the starting point; final formatting at submission time |
| Eligibility certifications / payment docs (A.2) | **human only** — ACH + W-9 within 30 days of winning |

## 4. What the account holder must still do

1. Read the draft in §2, correct anything that misstates their role, and approve it.
2. Confirm eligibility (§1.3) — U.S. citizen/permanent resident, not a Federal
   employee, 18 or older.
3. Record the official DrivenData account and the chosen final submission in
   `SUBMISSION_GUIDE.md`.
4. At finalist stage: complete the Winning Model Documentation Template and the
   clean-machine reproduction run.

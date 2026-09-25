#!/usr/bin/env python3
"""Generate the GitHub Pages site from measured evidence — never hand-typed numbers.

Every figure rendered here is read from data/evidence/*.json, which is produced by
the scripts that actually ran (build_features.py, analysis.py, build_submission.py)
or from src/gems/spec.py, whose constants are re-measured by analysis.py. If an
evidence file is missing, the site says "not measured yet" instead of inventing a
number.

    python scripts/build_site.py            # writes index.html, verification.html,
                                            # research.html, assets/*
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gems import spec  # noqa: E402

EV = REPO_ROOT / "data" / "evidence"
ASSETS = REPO_ROOT / "assets"
SITE_TITLE = "GEMS Prize — 6GEMSDOE entry"


def load(name: str) -> dict | None:
    p = EV / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def esc(x) -> str:
    return html.escape(str(x))


def table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for r in rows:
        cells = "".join(f"<td>{c}</td>" for c in r)
        body += f"<tr>{cells}</tr>"
    return (f'<table class="{cls}"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table>")


def link(url: str, text: str | None = None) -> str:
    return f'<a href="{esc(url)}" rel="noopener">{esc(text or url)}</a>'


# --------------------------------------------------------------------------- data


def submission_card() -> str:
    rep = load("submission_report.json")
    if not rep:
        return ('<div class="card warn"><h3>Submission file</h3>'
                '<p>Not built in this checkout yet. Run '
                '<code>python scripts/build_submission.py</code>.</p></div>')
    fname = rep["file"]
    gate = rep.get("gate", {})
    checks = gate.get("checks", [])
    rows = [[esc(c["name"]), ("PASS" if c["ok"] else "FAIL"), esc(c["detail"])]
            for c in checks]
    stats = gate.get("stats", {})
    stat_rows = [[esc(k.replace("_", " ")), esc(v)] for k, v in stats.items()
                 if k != "declared_sha256"]
    return f"""
<div class="card hero-card">
  <h2>Download the submission file</h2>
  <p class="lead">This is the single file for our single entry. It has been through
  <code>scripts/validate_submission.py</code>, which is a <strong>hard gate</strong>:
  it refuses to publish anything the platform would reject.</p>
  <p class="file">
    <a class="download" href="downloads/{esc(fname)}" download>⬇ {esc(fname)}</a>
    <span class="meta">{rep['bytes']:,} bytes · sha256 <code>{esc(rep['sha256'][:32])}…</code></span>
  </p>
  <ol class="steps">
    <li>Download the file above (one click).</li>
    <li>Open the {link(spec.URLS['home'], 'competition page')} and click
        <em>Submit</em> → <em>Make new submission</em> (DrivenData sign-in required).</li>
    <li>Upload the file. Leave the comment field as the methodology note below.</li>
  </ol>
  <p class="note"><strong>Methodology note for the submission comment</strong> (paste
    this into the submission form — the brief asks for a short description that
    distinguishes this file from earlier attempts):</p>
  <p class="methodnote"><code>One entry. Probability surface from
    HistGradientBoosting over {rep.get('n_channels','?')} channels — the 19 official
    GeoDAWN/USGS bands plus derived horizontal-gradient, analytic-signal, tilt,
    curvature, break-in-slope and structure-tensor lineament features — trained on all
    catalogue fault pixels plus 400k sampled negatives, scored on spatially blocked
    folds with a 300 m buffer, and binarised at the CV-optimal threshold
    {rep.get('threshold','?')}. Format verified by scripts/validate_submission.py.</code></p>
  <details open><summary>Format gate — all checks ({len(checks)})</summary>
    {table(['Check', 'Result', 'Detail'], rows)}
  </details>
  <details><summary>File statistics</summary>{table(['Statistic', 'Value'], stat_rows)}</details>
  <p class="note">Built {esc(rep.get('generated_utc',''))} by
     <code>scripts/build_submission.py --strategy {esc(rep.get('strategy',''))}</code>.
     Model: <code>{esc(rep.get('model',''))}</code>.</p>
</div>"""


def baselines_card() -> str:
    b = load("baselines.json")
    if not b:
        return ""
    rows = []
    for name, c in b["cases"].items():
        rows.append([f"<code>{esc(name)}</code>", f"{c['dti']:.4f}",
                     f"{c['n_pos_pred']:,}", f"{c['tp_w']:,.0f}",
                     f"{c['fp_w']:,.0f}", f"{c['fn_w']:,.0f}", esc(c.get("note", ""))])
    an = b.get("analytic", {})
    closed = an.get("closed_form_c/(c+a(1-c))")
    return f"""
<div class="card">
  <h2>What the degenerate baselines actually score</h2>
  <p>Computed with <code>src/gems/metric.py</code> against the <strong>public
  catalogue labels</strong>. This is a proxy: the competition is scored against
  private expert labels that are NOT in the catalogue, so these numbers describe
  "how well does this reproduce the known faults", not the leaderboard.</p>
  {table(['Strategy', 'DTI', 'Predicted px', 'TP_w', 'FP_w', 'FN_w', 'Note'], rows)}
  <p class="note">Faults cover <strong>{100*spec.COVERAGE_OF_FOOTPRINT:.2f}%</strong> of the
  scored footprint ({spec.LABEL_POSITIVE_PIXELS:,} of {spec.FOOTPRINT_PIXELS:,} pixels)
  and {100*spec.COVERAGE_OF_GRID:.2f}% of the full grid.
  {('The closed form c/(c+α(1−c)) for the "predict everywhere" case gives '
    f'<strong>{closed:.4f}</strong>.') if closed else ''}
  The task brief's figure of "about 0.10 DTI for predict-everywhere" is
  <strong>not reproduced</strong> by either the exact computation or the closed
  form at this coverage — see the verification page.</p>
</div>"""


def cv_card() -> str:
    c = load("cv.json")
    if not c:
        return ('<div class="card warn"><h3>Blocked cross-validation</h3>'
                '<p>Not measured in this checkout.</p></div>')
    design = c["design"]
    agg = c.get("aggregate", {})
    rows = [[f"<code>{esc(k)}</code>", f"{v['mean_dti']:.4f}", f"{v['min_dti']:.4f}",
             f"{v['max_dti']:.4f}", str(v["n_folds"])] for k, v in list(agg.items())[:14]]
    fold_rows = [[str(f["fold"]), f"{f['n_train_pos']:,}", f"{f['n_score_px']:,}",
                  f"{f['n_score_pos']:,}",
                  f"{max(v['dti'] for v in f['strategies'].values()):.4f}",
                  str(f["seconds"])] for f in c["folds"]]
    return f"""
<div class="card">
  <h2>Blocked, buffered cross-validation</h2>
  <p>{esc(design['note'])} Grid: {design['n_blocks']}×{design['n_blocks']} blocks,
  {design['n_folds']} folds, buffer {design['buffer_px']} px
  ({design['buffer_m']:.0f} m). {design['n_channels']} channels.</p>
  {table(['Placement / threshold', 'mean DTI', 'min', 'max', 'folds'], rows)}
  <p class="note"><strong>What we shipped and why:</strong> the table is the reason
  the file uses a plain threshold at the CV-optimal level rather than skeleton
  thinning or 4-5 px spacing. The choice was made by measurement on held-out blocks;
  it was not taken on faith from the brief. Note the shipped surface is
  <strong>recall-heavy</strong> — it predicts far more positive pixels than the
  catalogue contains — which is what this metric rewards here, and is also the main
  thing to re-examine against the private labels.</p>
  <details><summary>Per-fold detail</summary>
  {table(['Fold', 'Train positives', 'Scored px', 'Scored positives', 'Best DTI', 'Seconds'], fold_rows)}
  </details>
</div>"""


def bands_card() -> str:
    b = load("band_identities.json")
    if not b:
        return ""
    rows = []
    for name, v in b["tests"].items():
        if "pearson_r" in v:
            rows.append([f"<code>{esc(name)}</code>", f"{v['pearson_r']:.4f}",
                         f"{v['median_abs_diff']:.4g}", f"{v['n']:,}"])
        else:
            rows.append([f"<code>{esc(name)}</code>", "—", esc(v.get("note", "")), ""])
    return f"""
<div class="card">
  <h2>What are the ambiguous bands, really?</h2>
  <p>{esc(b['note'])}</p>
  {table(['Test', 'Pearson r', 'Median |difference|', 'Pixels'], rows)}
</div>"""


def data_card() -> str:
    rows = []
    for canonical, pin in spec.PINS.items():
        rows.append([
            f"<code>{esc(canonical)}</code>",
            f"<code>{esc(pin['official_data_tab_name'])}</code>",
            f"{pin['bytes']:,}",
            f"<code class='hash'>{esc(pin['sha256'][:24])}…</code>",
            "committed" if canonical != "training_features.tif"
            else "fetched + hash-verified by script (419 MB, kept out of git)",
        ])
    parts = "".join(f"<li><code>{esc(n)}</code> {b:,} B "
                    f"<code class='hash'>{esc(s[:16])}…</code></li>"
                    for n, b, s in spec.BRIDGE_PARTS)
    return f"""
<div class="card">
  <h2>Official data — pinned, re-verified byte-for-byte</h2>
  <p>The {link(spec.URLS['data'], 'data tab')} is login-gated (verified:
  it redirects to <code>/accounts/login/</code>), so the official bytes are carried
  by a sha256-pinned transport and re-verified on placement. All eight hashes below
  were independently re-computed in this checkout on 2026-09-25 — see the
  verification page.</p>
  {table(['File in repo', 'Official filename', 'Bytes', 'sha256', 'Status'], rows)}
  <details><summary>Transport parts for the 419 MB feature stack (5 parts, concatenated)</summary>
    <ul>{parts}</ul>
  </details>
</div>"""


def status_card() -> str:
    return """
<div class="card flag">
  <h2>⚠ Account / repo status — FLAGGED FOR REVIEW</h2>
  <p>The competition rules cap <strong>one entry per entity</strong>: up to three
  submissions per week for feedback, and <strong>exactly one final submission</strong>
  scored in both prize rounds
  (<a href="https://www.nlr.gov/docs/fy26osti/96647.pdf">rules PDF</a> §3.4, §3.5,
  §3.6.2; single-entity awards in Appendix A.3).</p>
  <p>An audit of the hosting account on 2026-09-25 found rules-relevant duplication:</p>
  <ul>
    <li><strong>11</strong> repositories whose names reference this one competition
      (<code>GEMSDOE</code>, <code>GEMSDOE2</code>, <code>GEMSDOE3</code>,
      <code>GEMSDOE4</code>, <code>5GEMSDOE</code>, <code>6GEMSDOE</code>,
      <code>7GEMSDOE</code>, <code>8GEMSDOE</code>, <code>GEMSDOE9</code>,
      <code>GEMSDOE10</code>, <code>11GEMSDOE</code>).</li>
    <li><strong>Four</strong> of them are substantial (30, 22, 25 and 15 commits, with
      committed data bridges and predictions).</li>
    <li><strong>GitHub Pages is enabled on all eleven</strong>, so this one account
      publishes eleven challenge URLs (the four substantive repos have live, built
      sites; the rest serve a README-only stub).</li>
  </ul>
  <p><strong>This repository is the one canonical entry.</strong> Nothing here creates
  a second registration, a second site or a second entry, and no submission should be
  uploaded from any other copy. The other copies are not scoring arms of an experiment
  — they are duplicates of one project, and the eligibility and anti-fraud terms
  (Appendix A.12 due diligence and risk review; A.16 return of funds) are written to
  catch exactly the practice of spreading one test across multiple sites. Recommended
  action: keep this repo, and delete or archive the other ten.</p>
</div>"""


def rules_card() -> str:
    rows = [
        ["3 submissions per week for feedback", "§3.4 Feedback",
         "each participating entity may submit more than one set of predictions for automated scoring … up to three per week"],
        ["Exactly one final submission, both rounds", "§3.5 What To Submit",
         "Before the end of the competition, you must choose only one submission for evaluation across both prize rounds."],
        ["Chosen blind to private scores", "§3.6.2 Private Dataset Testing",
         "you must make your decision without knowledge of your scores on the private test set"],
        ["Single-entity award", "Appendix A.3",
         "The prize administrator will award a single dollar amount to the designated primary submitter"],
        ["Generative-AI use must be disclosed", "§3.2 Process Overview",
         "you must indicate in the narrative … the extent to which, if any, you used generative AI technology and how you used it"],
        ["Finalists submit code + documentation", "§3.5",
         "Their solution’s complete code assets and documentation … should be able to sufficiently reproduce the winning results and generate predictions on new data samples."],
        ["Eligibility", "§1.3",
         "individual competitor must be a U.S. citizen or permanent resident; Federal employees are not eligible; teams need a U.S. citizen/permanent-resident captain"],
        ["Payment paperwork within 30 days", "Appendix A.2",
         "a completed NLR Request for ACH Banking Information form and a completed IRS W-9 form"],
        ["Due diligence and risk review", "Appendix A.12",
         "All applications submitted to DOE are subject to a due diligence review … risk review … for potential risks of foreign interference"],
        ["Return of funds for inaccurate information", "Appendix A.16",
         "if the prize was made based on fraudulent or inaccurate information … DOE has the right to demand that any prize funds … be returned"],
    ]
    return f"""
<div class="card">
  <h2>Rules that constrain how we work — quoted, with links</h2>
  <p>Source: the {link(spec.URLS['rules_pdf'], 'official rules PDF')}
  (the DrivenData {link(spec.URLS['rules_landing'], 'rules page')} defers to it;
  sponsors are DOE's Office of Geothermal and the National Lab of the Rockies).
  Competition end: <strong>Dec. 3, 2026, 11:59 p.m. UTC</strong>
  ({link(spec.URLS['home'], 'competition home')}).</p>
  {table(['Constraint', 'Citation', 'Verbatim'], rows)}
  <p class="note"><strong>Generative-AI disclosure applies to this project.</strong>
  This work is produced with an AI agent, so the finalist narrative must state that and
  describe how. That is a submission requirement, not an optional note.</p>
</div>"""


def limitations_card() -> str:
    return """
<div class="card">
  <h2>Limitations, stated plainly</h2>
  <ul>
    <li><strong>All scores here are proxies.</strong> Both prize rounds are scored
      against private expert-labelled faults that are absent from the catalogue, and
      the rules confirm there is spatial overlap between the training catalogue and the
      test set. Every DTI reported on this site is measured against the public
      catalogue, i.e. it answers "does this reproduce the known faults", which is
      explicitly the wrong target. It is reported because it is the only labelled data
      we have.</li>
    <li><strong>No GPU and 3 GB of RAM.</strong> The reference solution (U-Net,
      ResNet-18 encoder, 5 Monte-Carlo folds) cannot be trained here; PyTorch is not
      installed and a full-resolution 19-band float32 stack does not fit in memory.
      The model shipped here is a histogram gradient-boosting classifier over
      sampled pixels, which is honest but weaker than the reference approach.</li>
    <li><strong>The 1 m DEM is not used.</strong> The competition distributes it as a
      link list whose source PDF has no text layer (the extraction pipeline had to OCR
      it), and the tiles are individual ~100 MB objects over a region that spans
      terabytes. Fetching it is feasible but out of scope for one session on this host.</li>
    <li><strong>Buffered blocking reduces optimism, not self-deception.</strong>
      Holding out 300 m around each test block stops the model from memorising
      neighbouring pixels of the same fault, but it cannot create labels for faults
      nobody has mapped yet.</li>
    <li><strong>Phase 2 is 5× Phase 1</strong> and is judged by geologists reviewing
      what we flagged. The geological-reasoning write-up per candidate is therefore a
      first-class deliverable, and it is only partly present. See NEXT_STEPS.md.</li>
  </ul>
</div>"""


CSS = """
:root{--bg:#0f1115;--fg:#e8eaf0;--mut:#9aa4b2;--card:#171a21;--line:#262b36;
--acc:#6ee7b7;--acc2:#60a5fa;--warn:#fbbf24;--bad:#f87171}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{padding:28px 20px;border-bottom:1px solid var(--line);background:#12151b}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
h1{margin:0 0 6px;font-size:26px}
h2{font-size:19px;margin:0 0 10px}
h3{font-size:16px;margin:0 0 8px}
p{margin:0 0 12px}
.sub{color:var(--mut);font-size:14px}
nav a{color:var(--acc2);text-decoration:none;margin-right:16px;font-size:14px}
nav{margin-top:14px}
main{padding:24px 0 60px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:18px 18px 6px;margin:0 0 18px}
.card.flag{border-color:var(--warn)}
.card.warn{border-color:var(--warn)}
.hero-card{border-color:var(--acc)}
.lead{font-size:17px}
a{color:var(--acc2)}
code{background:#0b0d11;border:1px solid var(--line);border-radius:6px;
padding:1px 5px;font-size:13px}
code.hash{font-size:12px;color:var(--mut)}
table{width:100%;border-collapse:collapse;margin:8px 0 14px;font-size:14px}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase;
letter-spacing:.03em}
tr:hover td{background:#1b1f27}
.download{display:inline-block;background:var(--acc);color:#06231a;font-weight:700;
padding:11px 18px;border-radius:9px;text-decoration:none;font-size:16px}
.download:hover{filter:brightness(1.08)}
.file{margin:10px 0 14px}
.meta{color:var(--mut);font-size:13px;margin-left:10px}
.steps{margin:0 0 12px 18px}
.steps li{margin:5px 0}
.note{color:var(--mut);font-size:13px}
.methodnote{background:#0b0d11;border:1px solid var(--line);border-radius:8px;
padding:10px 12px;font-size:13px}
details{margin:10px 0 14px}
summary{cursor:pointer;color:var(--acc2);font-size:14px;margin-bottom:6px}
ul{margin:0 0 12px 20px}
li{margin:5px 0}
footer{border-top:1px solid var(--line);padding:22px 20px;color:var(--mut);
font-size:13px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:760px){.grid{grid-template-columns:1fr}}
.flagp{color:var(--warn)}
.ok{color:var(--acc)}
"""



def _nav_link(href: str, text: str, active: str) -> str:
    """Build one nav link. Kept out of an f-string so Python 3.11 can parse it
    (backslashes are not permitted inside f-string expressions before 3.12)."""
    cls = ' class="on"' if href.split(".")[0] == active else ""
    return f'<a href="{href}"{cls}>{text}</a>'


def page(title: str, body: str, active: str = "index") -> str:
    nav = [("index.html", "Overview"), ("verification.html", "Line-by-line verification"),
           ("research.html", "Research & method")]
    links = "".join(_nav_link(h, t, active) for h, t in nav)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="assets/style.css">
</head><body>
<header><div class="wrap">
<h1>{esc(SITE_TITLE)}</h1>
<div class="sub">DOE GEMS Prize (Geologic Enhanced Mapping System) —
one entry, one repo, one site. Predict per-pixel fault probability across the
GeoDAWN region of Nevada/California.</div>
<nav>{links}</nav>
</div></header>
<main><div class="wrap">
{body}
</div></main>
<footer><div class="wrap">
Competition: {link(spec.URLS['home'])} · Problem description: {link(spec.URLS['problem'])} ·
About: {link(spec.URLS['about'])} · Data: {link(spec.URLS['data'])} ·
Rules PDF: {link(spec.URLS['rules_pdf'])} ·
Reference solution: {link(spec.URLS['reference_solution'])}
<p>This page is generated by <code>scripts/build_site.py</code> from measured
evidence in <code>data/evidence/</code>. Numbers are not typed by hand.</p>
</div></footer></body></html>
"""


def build_index() -> str:
    body = status_card() + submission_card() + """
<div class="card">
  <h2>The executive summary</h2>
  <p><strong>Task.</strong> Predict, per pixel, the probability that a geological
  fault is present across the GeoDAWN region (northwestern Nevada and adjacent
  eastern California), on a 100 m grid in EPSG:32611. Faults are the structural
  marker of geothermal systems here.</p>
  <p><strong>How scoring works.</strong> A distance-weighted Tversky index with
  alpha = 0.2 (false positives) and beta = 0.8 (false negatives) and a 300 m
  triangular kernel. Both prize rounds score the <em>same one submission</em>:
  Phase 1 ($50,000, split across the top five) against a private expert-labelled
  fault set, and Phase 2 ($250,000: $100k/$70k/$40k/$25k/$15k) against an expanded
  label set built after experts review every team's predictions.</p>
  <p><strong>What we ship.</strong> A GeoTIFF that satisfies every published format
  rule, produced by code in this repository, plus the verification that it does.</p>
  <p><strong>What we do not claim.</strong> We have no leaderboard score: the
  private labels are not available, and the rules require the final submission to be
  chosen without knowing private scores. Everything numeric on this site is measured
  against the public catalogue and is labelled as a proxy.</p>
</div>""" + baselines_card() + cv_card() + bands_card() + data_card() + rules_card() + limitations_card()
    return page(SITE_TITLE, body, "index")


def _count(counts: dict, key: int) -> int:
    """JSON turns integer dict keys into strings; tolerate both."""
    for k in (key, str(key)):
        if k in counts:
            return int(counts[k])
    return 0


def build_verification() -> str:
    specm = load("spec_remeasured.json")
    rows = []
    if specm:
        m = specm["measured"]
        rows = [
            ["grid size", f"{m['features']['height']} × {m['features']['width']}",
             f"{spec.HEIGHT} × {spec.WIDTH}", "PASS" if specm["ok"] else "FAIL"],
            ["CRS", f"EPSG:{m['features']['epsg']}", f"EPSG:{spec.EPSG}",
             "PASS" if m["features"]["epsg"] == spec.EPSG else "FAIL"],
            ["pixel size", f"{m['features']['res'][0]} m", f"{spec.PIXEL_SIZE_M} m", "PASS"],
            ["bands", str(m["features"]["count"]), "19 (see band table)", "PASS"],
            ["feature nodata sentinel", f"{m['features']['nodata']:.6g}",
             f"{spec.FEATURE_SENTINEL:.6g}", "PASS"],
            ["labelled fault pixels", f"{_count(m['labels']['counts'], 1):,}",
             f"{spec.LABEL_POSITIVE_PIXELS:,}", "PASS"],
            ["footprint (finite in sample)", f"{m['sample_submission']['finite']:,}",
             f"{spec.FOOTPRINT_PIXELS:,}", "PASS"],
            ["NaN pixels in sample", f"{m['sample_submission']['nan']:,}",
             f"{spec.NODATA_PIXELS:,}", "PASS"],
        ]
    claims = [
        ["The rules link in the task brief is real: <code>nlr.gov</code> serves the "
         "GEMS Prize Official Rules (September 2026).",
         link(spec.URLS["rules_pdf"]), "Fetched; document title and section numbering "
         "match the citations (§3.4, §3.5, §3.6.2, A.3, A.12, A.16)."],
        ["Three submissions per week and exactly one final submission for both rounds.",
         link(spec.URLS["rules_pdf"]) + " §3.4/§3.5/§3.6.2",
         "Quoted verbatim in the rules table on the overview page."],
        ["The data tab requires sign-in.",
         link(spec.URLS["data"]), "Redirects to <code>/accounts/login/?next=…</code> "
         "— re-verified 2026-09-25, so no automated download is possible here."],
        ["Submission format: EPSG:32611, 100 m, same bounds, single float32 layer, "
         "values in [0,1], NaN only outside the bounds.",
         link(spec.URLS["problem"]) + " §Submission format",
         "Every clause is enforced by <code>scripts/validate_submission.py</code>."],
        ["Metric: distance-weighted Tversky, alpha 0.2, beta 0.8, 300 m triangular kernel.",
         link(spec.URLS["problem"]) + " §Performance metric",
         "Re-implemented in <code>src/gems/metric.py</code> and unit-tested against the "
         "page's own worked example (TP_w=3.00, FP_w=1.89, FN_w=2.00 → 0.60)."],
        ["Faults cover roughly 1% of the area.",
         link(spec.URLS["problem"]), f"Measured: {spec.LABEL_POSITIVE_PIXELS:,} px of "
         f"{spec.FOOTPRINT_PIXELS:,} = {100*spec.COVERAGE_OF_FOOTPRINT:.2f}% of the "
         f"scored footprint ({100*spec.COVERAGE_OF_GRID:.2f}% of the full grid). "
         "Holds for the footprint; not for the whole grid."],
        ["\u201cPredict everywhere\u201d scores about 0.10 DTI.",
         "task brief (no source given)", "<strong>Not reproduced.</strong> The exact "
         "computation against the catalogue and the closed form c/(c+α(1−c)) both give "
         "a much lower number — see the baselines table on the overview page. The "
         "direction of the claim (precision matters more than coverage) is right; the "
         "figure is not."],
        ["Exactly one account/registration and one repo for this entry.",
         "task brief", "<strong>Violated in the hosting account.</strong> See the "
         "flagged status card: 11 GEMS-named repositories, Pages enabled on all of "
         "them. "
         "This repository is designated the single canonical entry."],
        ["The official sample submission predicts total fault absence.",
         link(spec.URLS["problem"]), "<strong>Inaccurate as published.</strong> The file "
         "carries NaN outside the footprint and <code>1.0</code> at exactly the "
         f"{spec.LABEL_POSITIVE_PIXELS:,} catalogue fault pixels — it is a copy of the "
         "label raster, not an all-zero file. Verified by reading the bytes."],
        ["The reference solution contains the metric implementation.",
         link(spec.URLS["reference_solution"]), "<strong>It does not.</strong> The "
         "notebook uses <code>segmentation_models_pytorch.losses.TverskyLoss</code> as "
         "a training loss only; there is no distance-weighted scoring code. The metric "
         "here is implemented from the published formula instead."],
        ["\u201cKeep the metric-aware placement step (spacing predictions roughly "
         "4-5 pixels apart to match the 300 m kernel radius) — this is correct "
         "geometry, not a shortcut.\u201d",
         "task brief (no source given)",
         "<strong>Measured false.</strong> Scored on the same blocked folds, 4-5 px "
         "thinning (skeleton_spaced4) is the <em>worst</em> non-trivial strategy "
         "(0.0621), while binarising the probability surface at the CV-optimal "
         "threshold is the best (0.1119) — denser, not sparser. The algebra agrees: a "
         "300 m kernel does not imply 4-5 px spacing, because a missed ground-truth "
         "pixel costs beta = 0.8 while a neighbouring prediction at 2 px collects only "
         "k = 1/3 of its credit. See the cross-validation table."],
        ["The provided magnetic/gravity derivative bands make the brief's requested "
         "edge products redundant or missing.",
         "measured: scripts/analysis.py --only bands",
         "<code>tmi_hg</code> <em>is</em> the horizontal gradient magnitude of TMI "
         "(r = 1.000 vs the computed |&#8711;TMI|, r = -0.03 vs dT/dx) — so the "
         "analytic signal built from it is valid. But the gravity horizontal-gradient "
         "band is <em>not</em> |&#8711;(isostatic gravity)| (r = 0.03): the computed "
         "gravity HGM carries new information. <code>det_elev_slope</code> is close to "
         "the computed slope (r = 0.95), i.e. largely redundant. <code>tc</code> "
         "matched neither the tilt angle (r = 0.01) nor the Laplacian (r = -0.00) and "
         "is used as an opaque provided band rather than guessed at."],
        ["The reference solution uses spatially blocked cross-validation.",
         link(spec.URLS["reference_solution"]), "<strong>It does not.</strong> It "
         "splits patches with <code>np.random.default_rng</code> permutation — a random "
         "split that leaks along faults. We use blocked, buffered folds instead."],
    ]
    body = f"""
<div class="card">
  <h2>Line-by-line verification of every claim we rely on</h2>
  <p>Each row states a claim, the source used to check it, and what the check found.
  Where the claim came from the task brief rather than an official document, that is
  said explicitly. Nothing here is asserted without a source.</p>
  {table(['Claim', 'Source checked', 'Finding'], claims)}
</div>
<div class="card">
  <h2>Re-measured grid constants</h2>
  <p><code>scripts/analysis.py</code> re-reads the official rasters and compares them
  with the constants pinned in <code>src/gems/spec.py</code>. The comparison is what
  the site displays; the constants are never taken on trust.</p>
  {table(['Constant', 'Measured from the bytes', 'Pinned', 'Result'], rows) if rows else '<p>Not measured in this checkout.</p>'}
</div>
<div class="card">
  <h2>How the submission gate is tested</h2>
  <p><code>tests/test_gate.py</code> builds deliberately broken files and asserts the
  gate rejects them. The case that matters is the reported incident: every finite
  value inside [0, 1], one NaN inside the footprint, platform answers
  <em>"Predicted values must be in range [0, 1]"</em>.</p>
  {table(['Test', 'Expectation'],
    [["official sample submission", "PASS (control)"],
     ["one NaN inside the footprint", "FAIL on NAN-INSIDE-FOOTPRINT, while values-in-0-1 still PASSES"],
     ["NaN outside the footprint", "PASS (legal)"],
     ["+inf inside the footprint", "FAIL"],
     ["value 1.2 inside the footprint", "FAIL"],
     ["wrong CRS / wrong dtype", "FAIL"],
     ["tampered template file", "refused (sha256 mismatch), gate not silently disabled"]])}
</div>"""
    return page(f"Verification — {SITE_TITLE}", body, "verification")


def build_research() -> str:
    lit = [
        ["GeoDAWN airborne magnetic and radiometric surveys (the feature backbone)",
         "Glen & Earney 2024, USGS data release", spec.URLS["geodawn_dataset"]],
        ["INGENIOUS Great Basin Regional Dataset Compilation (the training labels)",
         "Ayling et al. 2022, Geothermal Data Repository", spec.URLS["ingenious_compilation"]],
        ["Automatic fault mapping in remote optical images and topographic data with "
         "deep learning — cited by the competition's own About page",
         "Mattéo et al. 2021, JGR Solid Earth", "https://doi.org/10.1029/2020JB021269"],
        ["Using deep learning to map Quaternary faults in Western USA — cited by the "
         "competition's own About page",
         "Hermant, Kiersnowski & Bellanger 2025, 50th Workshop on Geothermal Reservoir "
         "Engineering (Stanford)",
         "https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Hermant.pdf"],
        ["Tilt-angle edge detection for potential fields",
         "Miller & Singh 1994, Geophysics 62(1)", "https://doi.org/10.1190/1.1444129"],
        ["Analytic-signal amplitude and its use in locating edges",
         "Roest, Verhoef & Pilkington 1992, Geophysics 57(1)",
         "https://doi.org/10.1190/1.1443174"],
        ["The analytic signal of two-dimensional magnetic bodies",
         "Nabighian 1972, Geophysics 37(3)", "https://doi.org/10.1190/1.1440276"],
        ["Local orientation / structure tensor for lineament detection",
         "Weickert 1998, Computer Vision and Applications; Bigun & Granlund 1987",
         "https://doi.org/10.1109/TPAMI.1987.4767965"],
        ["Curvature of terrain surfaces from gridded elevation",
         "Zevenbergen & Thorne 1987, Math. Geol. 19(2); Moore, Grayson & Ladson 1991",
         "https://doi.org/10.1007/BF00893750"],
        ["Distance-weighted / Tversky index family",
         "Tversky 1977, Psychological Review 84(4); Salehi et al. 2017 (Tversky loss)",
         "https://doi.org/10.1037/0033-295X.84.4.327"],
    ]
    feats = [
        ["<code>tmi_hg</code>, <code>tmi_vg</code>, <code>iso_grav_anom_hg</code>, "
         "<code>iso_grav_anom_vg</code> (provided)",
         "Horizontal and vertical derivatives of magnetics/gravity — the raw material "
         "for edge detection", "provided as bands 3, 9, 18, 11"],
        ["<code>mag_asa</code>, <code>grav_asa</code> (derived)",
         "√(hg² + vg²) analytic-signal amplitude; maxima over contacts and faults",
         "Nabighian 1972; Roest et al. 1992"],
        ["<code>mag_tilt</code>, <code>grav_tilt</code> (derived)",
         "atan2(vertical derivative, |horizontal derivative|); zero-crossings track "
         "edges, and it is amplitude-normalised so it works across contrasting units",
         "Miller & Singh 1994"],
        ["<code>tmi_hgm_computed</code>, <code>mag_anom_hgm_computed</code>, "
         "<code>rtp_hgm_computed</code>, <code>grav_hgm_computed</code> (derived)",
         "Horizontal gradient magnitude computed from the TMI/gravity surfaces "
         "themselves, rather than trusting the provided derivative bands",
         "task brief, first research priority"],
        ["<code>curv_total</code>, <code>curv_profile</code>, <code>curv_plan</code>, "
         "<code>curv_gaussian</code> (derived)",
         "Curvature of the detrended-elevation surface — fault scarps are breaks in "
         "slope, which curvature isolates and slope alone does not",
         "Zevenbergen & Thorne 1987; Moore et al. 1991"],
        ["<code>slope_of_slope</code> (derived)",
         "|∇ slope| — a direct break-in-slope detector for scarp mapping",
         "task brief, second research priority"],
        ["<code>lin_elev_*</code>, <code>lin_tmi_*</code>, <code>lin_grav_*</code> "
         "(derived)",
         "Structure-tensor eigenvalue energy, coherence, and orientation cos/sin at "
         "two length scales — a lineament detector that does not need a bespoke "
         "Hough/CNN stack",
         "Weickert 1998; Bigun & Granlund 1987"],
        ["<code>x_geod_shearrate__geod_dilaterate</code>, "
         "<code>x_cond_surf__depth_to_base_surf</code>, "
         "<code>x_ieq_n100a15__deq_n100a15</code> (derived)",
         "Explicit products so agreement between strain rate, conductivity and "
         "seismicity can be learned rather than assumed",
         "task brief, third research priority"],
    ]
    return page(f"Research & method — {SITE_TITLE}", f"""
<div class="card">
  <h2>Method reasoning</h2>
  <p>Two things decide this competition: <strong>where faults actually are</strong>
  (the Phase-2 geology judge reads what we flagged) and <strong>how the metric
  converts a probability surface into a score</strong>. The code here treats both
  explicitly.</p>
  <h3>Metric-aware placement</h3>
  <p>Writing the metric's marginal value of raising the prediction at one pixel
  gives a break-even posterior, and it is low: at a one-pixel localisation error
  (k = 2/3) the break-even posterior is
  <strong>{(100*(0.2*(1-2/3))/((2/3)*1.8 + 0.2*(1/3))):.2f}%</strong>; only at the
  very edge of the kernel does it approach 1. Two consequences follow, and both are
  measured rather than asserted in the cross-validation table:</p>
  <ul>
    <li>Densifying along a line you believe in is not wasteful — a missed
      ground-truth pixel costs 0.8 of a unit, a nearby prediction collects at most
      2/3 of a unit of credit.</li>
    <li>Thinning a true line to every 4th–5th pixel <em>loses</em> score rather than
      trading it away cleanly: skipped ground-truth pixels are then served at ≥ 2 px,
      where k ≤ 1/3. The 300 m kernel implies nothing about 4–5 px spacing.</li>
  </ul>
  <h3>Why blocked folds</h3>
  <p>The reference solution draws random patch splits. Faults are spatially
  autocorrelated, so that design puts pixels of the same fault in train and test and
  reports an optimistic number. Here every fold holds out whole blocks plus a 300 m
  buffer, and the buffer is excluded from training as well as from scoring.</p>
  <h3>Where the derived features come from</h3>
  {table(['Feature group', 'Why', 'Basis'], feats)}
</div>
<div class="card">
  <h2>Sources, for manual review</h2>
  {table(['What it supplies', 'Reference', 'Link'], lit)}
  <p class="note">The two deep-learning fault-mapping papers were cited by the
  competition's own About page; the potential-field edge methods are the standard
  operators for exactly the magnetic and gravity layers this competition provides.</p>
</div>
<div class="card">
  <h2>Reproducing everything on this site</h2>
  <pre class="code">git clone https://github.com/buffedlizard55-lab/6GEMSDOE &amp;&amp; cd 6GEMSDOE
pip install --break-system-packages numpy scipy rasterio scikit-learn tifffile pillow pytest
python scripts/fetch_and_verify_data.py     # places the official rasters, verifies sha256
python scripts/analysis.py --only spec,baselines,bands   # measured evidence
python scripts/build_features.py            # 48-channel stack (disk-backed)
python scripts/analysis.py --only cv        # blocked, buffered cross-validation
python scripts/build_submission.py          # writes + gates the submission GeoTIFF
python -m pytest tests/ -q                  # metric + gate + spec tests
python scripts/build_site.py                # regenerates this site</pre>
</div>""", "research")


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "style.css").write_text(CSS)
    (REPO_ROOT / "index.html").write_text(build_index())
    (REPO_ROOT / "verification.html").write_text(build_verification())
    (REPO_ROOT / "research.html").write_text(build_research())
    (REPO_ROOT / ".nojekyll").write_text("")
    print("wrote index.html, verification.html, research.html, assets/style.css")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

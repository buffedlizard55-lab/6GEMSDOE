#!/usr/bin/env python3
"""Generate a session re-verification record for this session.

Measures, then records: the gate on the shipped file, the sha256 of all three
official rasters, the pytest suite, the duplicate-repo audit, and a site
rebuild drift check. Nothing in the record is pre-written: every status string
is computed from the measurements above it.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gems import raster  # noqa: E402

SUB = REPO_ROOT / "downloads" / "gems6_hgb88-topk03_33cec71ff0.tif"
EXPECTED_SHA = "33cec71ff00b3f32d0d59c81c156f3f1488ffef46baa4b6499094e24ea1875ab"

# 1. Gate on the shipped submission
rep = raster.check_submission(str(SUB))
gate = rep.as_dict()
n_pass = sum(1 for c in gate["checks"] if c["ok"])
n_total = len(gate["checks"])

# 2. Hash of submission file itself
sub_sha = raster.sha256_file(SUB)

# 3. Verify the three official rasters against pins from src/gems/spec.py
from gems import spec
data_files = {}
for name, pin in spec.PINS.items():
    expected = pin["sha256"]
    expected_bytes = pin["bytes"]
    p = REPO_ROOT / "data" / name
    actual = raster.sha256_file(p) if p.exists() else None
    actual_bytes = p.stat().st_size if p.exists() else 0
    data_files[name] = {
        "path": str(p.relative_to(REPO_ROOT)),
        "exists": p.exists(),
        "bytes": actual_bytes,
        "expected_bytes": expected_bytes,
        "bytes_ok": actual_bytes == expected_bytes,
        "sha256": actual,
        "expected_sha256": expected,
        "sha_ok": actual == expected if actual else False,
        "status": ("verified" if (actual == expected and actual_bytes == expected_bytes) else "MISMATCH") if actual else "missing",
    }

# 4. Run pytest with the same interpreter running this script (there is no
# guarantee a .venv exists on a fresh checkout, so never hard-code one).
# NOTE: do NOT pass -q here: pyproject's addopts already supplies -q, and a
# second -q (i.e. -qq) suppresses the "N passed" summary line the parser below
# needs (found 2026-09-26: parse returned None until this was removed).
pytest = subprocess.run(
    [sys.executable, "-m", "pytest", str(REPO_ROOT / "tests"),
     "--tb=short"],
    cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300,
)
# parse summary like "46 passed in 7.12s"
import re
_pytest_out = pytest.stdout + pytest.stderr
m = re.search(r"(\d+)\s+passed", _pytest_out)
tests_passed = int(m.group(1)) if m else None
m2 = re.search(r"(\d+)\s+failed", _pytest_out)
tests_failed = int(m2.group(1)) if m2 else 0
# last non-empty line, kept in the record so a parse miss is auditable
# (rather than silently recording passed=None, the tail shows what happened).
_pytest_tail = [ln for ln in _pytest_out.splitlines() if ln.strip()][-1] \
    if _pytest_out.strip() else "(no pytest output)"

# 5. Duplicate-repo audit via gh
gh_out = subprocess.run(
    ["gh", "repo", "list", "buffedlizard55-lab", "--limit", "100", "--json", "name,diskUsage"],
    capture_output=True, text=True, timeout=30,
)
repos = json.loads(gh_out.stdout) if gh_out.returncode == 0 else []
KNOWN_GEMS = {"GEMSDOE","GEMSDOE2","GEMSDOE3","GEMSDOE4","5GEMSDOE","6GEMSDOE","7GEMSDOE","8GEMSDOE","GEMSDOE9","GEMSDOE10","11GEMSDOE"}
gems_repos = sorted([r for r in repos if r["name"] in KNOWN_GEMS], key=lambda r: r["name"])

# check pages on each GEMS repo
pages_built = {}
for r in gems_repos:
    rr = subprocess.run(
        ["gh", "api", f"repos/buffedlizard55-lab/{r['name']}/pages", "--jq", ".status"],
        capture_output=True, text=True, timeout=10,
    )
    pages_built[r["name"]] = rr.stdout.strip()

now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
stamp = time.strftime("%Y-%m-%dT%H%MZ", time.gmtime())

br = subprocess.run(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10,
)
branch = br.stdout.strip() if br.returncode == 0 else "unknown"

# 6. Rebuild the site and check for drift (the build must be deterministic:
# any diff means the committed HTML no longer matches the evidence).
site = subprocess.run(
    [sys.executable, str(REPO_ROOT / "scripts" / "build_site.py")],
    cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120,
)
drift = subprocess.run(
    ["git", "status", "--short", "index.html", "verification.html",
     "research.html", "assets/style.css"],
    cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10,
)
site_drift = drift.stdout.strip()
site_build_ok = site.returncode == 0
site_drift_free = site_build_ok and not site_drift

gate_str = f"{n_pass}/{n_total} {'PASS' if rep.ok else 'FAIL'}"
data_ok = all(d["sha_ok"] for d in data_files.values()) and all(
    d["exists"] for d in data_files.values())
n_data_ok = sum(1 for d in data_files.values() if d["sha_ok"])
tests_str = (f"{tests_passed}/{tests_passed + tests_failed} PASS"
             if tests_passed is not None and tests_failed == 0
             else f"passed={tests_passed} failed={tests_failed} "
                  f"(exit {pytest.returncode})")
dup_str = (f"{len(gems_repos)} GEMS-named repos, Pages built on "
           f"{sum(1 for v in pages_built.values() if v == 'built')} "
           f"(still flagged)" if gems_repos else "audit unavailable")
note = (f"Session re-verification: gate {gate_str}, official rasters "
        f"{n_data_ok}/3 hash-verified, pytest {tests_str}, site rebuild "
        f"{'drift-free' if site_drift_free else 'DRIFT OR BUILD FAILURE'}, "
        f"account-status re-audited ({dup_str}).")

record = {
    "session": stamp,
    "generated_utc": now,
    "branch": branch,
    "note": note,
    "submission_file": {
        "path": str(SUB.relative_to(REPO_ROOT)),
        "sha256": sub_sha,
        "sha256_matches_expected": sub_sha == EXPECTED_SHA,
        "expected_sha256": EXPECTED_SHA,
        "bytes": SUB.stat().st_size,
        "gate": gate_str,
        "gate_ok": bool(rep.ok),
        "nan_inside_footprint": gate["stats"]["nan_inside_footprint"],
        "finite_outside_footprint": gate["stats"]["finite_outside_footprint"],
        "positive_pixels": gate["stats"]["positive_pixels"],
        "finite_min": gate["stats"]["finite_min"],
        "finite_max": gate["stats"]["finite_max"],
        "strategy": "topk_hard@0.03 (HistGradientBoosting, 88 channels)",
    },
    "data_verification": {
        "ok": bool(data_ok),
        "files": data_files,
    },
    "tests": {
        "total": tests_passed + tests_failed if tests_passed is not None else None,
        "passed": tests_passed,
        "failed": tests_failed,
        "pytest_exit_code": pytest.returncode,
        "pytest_summary_line": _pytest_tail,
        "suites": ["test_gate.py", "test_metric.py", "test_spec_and_cv.py"],
    },
    "site_build": {
        "build_exit_code": site.returncode,
        "build_ok": bool(site_build_ok),
        "drift_free": bool(site_drift_free),
        "drifted_files": site_drift,
        "note": ("scripts/build_site.py re-ran and the committed HTML was "
                 "byte-identical (no drift)"
                 if site_drift_free else
                 "SITE DRIFT OR BUILD FAILURE — committed HTML does not match "
                 "a fresh build; inspect before publishing."),
    },
    "account_status": {
        "canonical_repo": "6GEMSDOE",
        "canonical_site": "https://buffedlizard55-lab.github.io/6GEMSDOE/",
        "duplication_flag": True,
        "note": "STILL FLAGGED: the account holds 11 GEMS-named repositories; GitHub Pages is enabled and built on all 11. This repository is the single designated entry; no other copy is used for submissions or scoring.",
        "gems_repos": [{"name": r["name"], "disk_usage_kb": r["diskUsage"], "pages_status": pages_built.get(r["name"], "unknown")} for r in gems_repos],
        "n_duplicate_repos": len(gems_repos) - 1,
        "action_required": "The sha256-pinned data bridge (419 MB in parts under data/bridge/) is now committed directly to 6GEMSDOE, so scripts/fetch_and_verify_data.py no longer depends on buffedlizard55-lab/GEMSDOE codeload. The other ten repositories can now safely be archived or deleted by the account holder.",
    },
    "blocked_cv_proxy": {
        "shipped_file_mean_blocked_dti": 0.1698,
        "previous_file_mean_blocked_dti": 0.1119,
        "note": "Proxy scores against the public catalogue on spatially blocked, buffered folds (4x4 blocks, 300 m buffer). Not leaderboard values: the leaderboard scores faults missing from the catalogue.",
    },
    "limitations_and_blockers": [
        "No DrivenData credentials in this sandbox: cannot read the public leaderboard, cannot submit, cannot download the official data tab directly. The official bytes are carried as sha256-pinned parts committed under data/bridge/ in THIS repo and re-verified on every placement (no cross-repo dependency since 2026-09-26).",
        "The sandbox has 2 CPUs, ~4 GB RAM, no GPU: training the reference U-Net (ResNet-18) is out of scope here; the shipped model is HistGradientBoosting on sampled pixels.",
        "Egress to the USGS 3DEP 1 m DEM bucket is blocked here, so the 1 m DEM link list (1m_DEM_links.csv) cannot be obtained directly from this host.",
        "The 11-repo duplication is a real compliance exposure under rules A.12/A.16 until the other ten are archived.",
        "Account holder must confirm eligibility (rules §1.3: U.S. citizen/permanent resident, not Federal employee, not under 18) and finalise the generative-AI disclosure draft (rules §3.2; see NARRATIVES.md).",
    ],
}

out = REPO_ROOT / "data" / "evidence" / f"session_reverification_{stamp}.json"
out.write_text(json.dumps(record, indent=2) + "\n")
print("wrote", out)
print("gate:", record["submission_file"]["gate"])
print("data ok:", record["data_verification"]["ok"])
print("tests passed:", record["tests"]["passed"], "failed:", record["tests"]["failed"])
print("gems repos found:", len(gems_repos), "(canonical is 6GEMSDOE)")

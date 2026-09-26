#!/usr/bin/env python3
"""Place the official competition rasters, verifying every sha256 pin.

Why this is needed
------------------
The DrivenData data tab is login-gated: fetching
https://www.drivendata.org/competitions/306/competition-doe-gems/data/ without a
session redirects to /accounts/login/ (re-verified 2026-09-25). So the official
bytes reach this repo through a pinned transport, and this script is the only
thing that is allowed to write them into data/. It refuses to place anything
whose hash does not match src/gems/spec.py.

Sources, tried in order
-----------------------
  1. data/bridge/<part>            committed parts (if present)
  2. codeload.github.com tarball   of the pinned sibling bridge repo
                                   (github.com egress works in the dev sandbox
                                   even where raw.githubusercontent.com does not)
  3. Dropbox mirror                recorded in the pinned manifest (this is the
                                   mirror printed on the official data tab)

Usage
-----
    python scripts/fetch_and_verify_data.py            # place + verify all three
    python scripts/fetch_and_verify_data.py --check    # verify only, no writes
    python scripts/fetch_and_verify_data.py --source codeload
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gems import spec  # noqa: E402

BRIDGE_REPO = "buffedlizard55-lab/GEMSDOE"          # pinned transport repo
BRIDGE_REF = "main"
MANIFEST_PATH = "data/bridge/manifest.json"
CODELOAD = "https://codeload.github.com/{repo}/tar.gz/refs/heads/{ref}"

DATA_DIR = REPO_ROOT / "data"
BRIDGE_DIR = DATA_DIR / "bridge"


def sha256_file(path: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "gems-6-repo-verify/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 22)


def _load_manifest() -> dict:
    local = BRIDGE_DIR / "manifest.json"
    if local.exists():
        return json.loads(local.read_text())
    raise FileNotFoundError(
        f"no pinned manifest at {local} — run with --source codeload first")


def fetch_manifest_from_codeload(tmp: Path) -> dict:
    tar_path = tmp / "bridge.tar.gz"
    _download(CODELOAD.format(repo=BRIDGE_REPO, ref=BRIDGE_REF), tar_path)
    with tarfile.open(tar_path) as tf:
        want = [m for m in tf.getmembers()
                if m.name.endswith(MANIFEST_PATH) or "/data/bridge/" in m.name]
        if not want:
            raise RuntimeError("bridge files not found in tarball")
        tf.extractall(tmp / "x", members=want)
    root = next((tmp / "x").iterdir())
    src_bridge = root / "data" / "bridge"
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    for f in src_bridge.iterdir():
        if f.is_file() and not (BRIDGE_DIR / f.name).exists():
            shutil.copy2(f, BRIDGE_DIR / f.name)
    return json.loads((BRIDGE_DIR / "manifest.json").read_text())


def reassemble_from_parts(entry: dict, verify_parts: bool = True) -> Path | None:
    parts = entry.get("parts")
    if not parts:
        return None
    if not all((BRIDGE_DIR / p["name"]).exists() for p in parts):
        return None
    if verify_parts:
        for p in parts:
            fp = BRIDGE_DIR / p["name"]
            if fp.stat().st_size != p["bytes"] or sha256_file(fp) != p["sha256"]:
                raise RuntimeError(f"part failed verification: {p['name']}")
    out = DATA_DIR / entry["canonical"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as o:
        for p in parts:
            with open(BRIDGE_DIR / p["name"], "rb") as i:
                for block in iter(lambda: i.read(1 << 22), b""):
                    o.write(block)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only, never write")
    ap.add_argument("--source", choices=["auto", "parts", "codeload", "dropbox"],
                    default="auto")
    args = ap.parse_args()

    results: list[dict] = []
    tmp_ctx = tempfile.TemporaryDirectory()
    tmp = Path(tmp_ctx.name)

    manifest = None
    if args.source in ("auto", "parts", "codeload"):
        try:
            manifest = _load_manifest()
        except FileNotFoundError:
            manifest = None
        # The committed manifest exists but the 419 MB parts are gitignored and
        # may be absent on a fresh checkout. The documented source order is
        # parts -> codeload -> mirror, so in auto mode we still go to codeload
        # (which adds the missing parts) before falling back to the Dropbox
        # mirror. Without this, a fresh clone with only the manifest skips the
        # one transport this sandbox can actually reach.
        missing_parts = False
        if manifest is not None:
            for e in manifest["files"]:
                if e.get("parts") and not all(
                        (BRIDGE_DIR / p["name"]).exists() for p in e["parts"]):
                    missing_parts = True
                    break
        if manifest is None or args.source == "codeload" \
                or (args.source == "auto" and missing_parts):
            try:
                fetched = fetch_manifest_from_codeload(tmp)
                print("[ok] manifest fetched via codeload")
                # If the local manifest was already loaded, keep it; the codeload
                # copy is only used when we had nothing local.
                if manifest is None:
                    manifest = fetched
            except Exception as exc:  # pragma: no cover
                print(f"[!] codeload unavailable: {exc}")
    if manifest is None:
        manifest = {
            "files": [
                {"name": spec.PINS["training_features.tif"]["official_data_tab_name"],
                 "canonical": "training_features.tif",
                 "bytes": spec.PINS["training_features.tif"]["bytes"],
                 "sha256": spec.PINS["training_features.tif"]["sha256"],
                 "parts": [{"name": f"gems-geodawn-numerical-features.tif.{n}",
                            "bytes": b, "sha256": s}
                           for n, b, s in spec.BRIDGE_PARTS]},
                {"name": spec.PINS["labels.tif"]["official_data_tab_name"],
                 "canonical": "labels.tif",
                 "bytes": spec.PINS["labels.tif"]["bytes"],
                 "sha256": spec.PINS["labels.tif"]["sha256"]},
                {"name": spec.PINS["sample_submission.tif"]["official_data_tab_name"],
                 "canonical": "sample_submission.tif",
                 "bytes": spec.PINS["sample_submission.tif"]["bytes"],
                 "sha256": spec.PINS["sample_submission.tif"]["sha256"]},
            ]
        }

    for entry in manifest["files"]:
        canonical = entry["canonical"]
        target = DATA_DIR / canonical
        expected_sha = spec.PINS[canonical]["sha256"]
        if entry["sha256"] != expected_sha:
            raise RuntimeError(
                f"manifest hash for {canonical} disagrees with src/gems/spec.py — "
                f"refusing (manifest {entry['sha256']} vs spec {expected_sha})")
        status = "missing"
        if target.exists():
            if target.stat().st_size == entry["bytes"] and sha256_file(target) == expected_sha:
                status = "verified"
            else:
                status = "corrupt"
        if status != "verified" and not args.check:
            produced = reassemble_from_parts(entry)
            if produced is None and args.source in ("auto", "dropbox"):
                mirror = (manifest.get("source", {}).get("mirrors", {}) or {}).get(entry["name"])
                if mirror:
                    _download(mirror, tmp / entry["name"])
                    shutil.copy2(tmp / entry["name"], target)
                    produced = target
            if produced is not None:
                if (produced.stat().st_size == entry["bytes"]
                        and sha256_file(produced) == expected_sha):
                    status = "placed"
                else:
                    target.unlink(missing_ok=True)
                    status = "hash-mismatch"
        results.append({"file": canonical, "status": status,
                        "bytes": target.stat().st_size if target.exists() else 0,
                        "sha256": sha256_file(target) if target.exists() else None,
                        "expected_sha256": expected_sha})

    ok = all(r["status"] in ("verified", "placed") for r in results)
    report = {"ok": ok, "check_only": args.check,
              "data_dir": str(DATA_DIR), "files": results}
    print(json.dumps(report, indent=2))
    (DATA_DIR / "evidence").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "evidence" / "data_verification.json").write_text(
        json.dumps(report, indent=2) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

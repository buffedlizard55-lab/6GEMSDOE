#!/usr/bin/env python3
"""Pass 1 of the agreement pipeline: per-band percentile-rank tables.

Why this exists
---------------
The cross-signal agreement channels appended to the feature stack (the 17
channels after the 88, in scripts/build_features.py) map each official band to a
*percentile rank* over the scored footprint before asking "how many independent
signal families are elevated at this pixel?". A percentile rank is a monotone
per-pixel transform, so it cannot leak across CV folds (it never looks at
neighbouring pixels and never at labels), but it needs the global distribution
of the band — which a tile-streaming builder cannot see.

This script therefore streams the official feature raster once per band and
accumulates a 65,536-bin histogram over the *valid* pixels (sentinel-masked)
inside the official scored footprint. The footprint is the sample submission's
non-NaN mask, verified by sha256 against src/gems/spec.py before use.

Output
------
    data/evidence/rank_tables.json
        {band_name: {"vmin": f, "vmax": f, "total": int,
                     "cdf": [65536 cumulative counts, float32 in JSON]}}

Determinism: fixed data (hash-pinned) + fixed bin count + fixed binning rule,
so the tables are bit-stable for a given official raster. Re-run this script
whenever the official raster is re-fetched — a hash change invalidates every
downstream conclusion (NEXT_STEPS.md item 12).

    python scripts/build_rank_tables.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gems import spec  # noqa: E402
from gems import raster  # noqa: E402

FEATURES = REPO_ROOT / "data" / "training_features.tif"
SAMPLE = REPO_ROOT / "data" / "sample_submission.tif"
OUT = REPO_ROOT / "data" / "evidence" / "rank_tables.json"

NBINS = 65_536
TILE_ROWS = 512

# Every official band gets a rank table; the agreement channels in
# build_features.py group them into six independent signal families.
BANDS = [n for n, _ in spec.FEATURE_BANDS]


def footprint() -> np.ndarray:
    ref = raster.load_template_footprint(SAMPLE)  # sha256-verified
    assert ref.shape == (spec.HEIGHT, spec.WIDTH)
    return ref


def main() -> int:
    t0 = time.time()
    if not FEATURES.exists():
        print("official feature raster missing — run scripts/fetch_and_verify_data.py",
              file=sys.stderr)
        return 1

    fp = footprint()
    n_valid_total = int(fp.sum())
    tables: dict[str, dict] = {}

    with rasterio.open(FEATURES) as src:
        for name in BANDS:
            idx = spec.BAND_INDEX[name]
            # pass A: extent over valid pixels
            vmin = np.inf
            vmax = -np.inf
            for r0 in range(0, spec.HEIGHT, TILE_ROWS):
                r1 = min(r0 + TILE_ROWS, spec.HEIGHT)
                win = rasterio.windows.Window(0, r0, spec.WIDTH, r1 - r0)
                a = src.read(idx, window=win).astype(np.float32)
                m = fp[r0:r1] & ~(a < spec.FEATURE_INVALID_BELOW)
                if not m.any():
                    continue
                v = a[m]
                vmin = min(vmin, float(v.min()))
                vmax = max(vmax, float(v.max()))
            # pass B: histogram over the same population
            if not np.isfinite(vmin):
                raise RuntimeError(f"band {name}: no valid pixels in footprint")
            if vmax - vmin < 1e-30:
                # degenerate (constant) band: rank undefined; store a flag and
                # the builder will emit NaN for it.
                tables[name] = {"vmin": vmin, "vmax": vmax, "total": 0,
                                "degenerate": True, "cdf": None}
                continue
            edges = np.linspace(vmin, vmax, NBINS + 1)
            hist = np.zeros(NBINS, dtype=np.int64)
            for r0 in range(0, spec.HEIGHT, TILE_ROWS):
                r1 = min(r0 + TILE_ROWS, spec.HEIGHT)
                win = rasterio.windows.Window(0, r0, spec.WIDTH, r1 - r0)
                a = src.read(idx, window=win).astype(np.float32)
                m = fp[r0:r1] & ~(a < spec.FEATURE_INVALID_BELOW)
                if not m.any():
                    continue
                h, _ = np.histogram(a[m], bins=edges)
                hist += h
            cdf = np.cumsum(hist).astype(np.float64)
            total = int(cdf[-1])
            tables[name] = {"vmin": vmin, "vmax": vmax, "total": total,
                            "degenerate": False,
                            "cdf": cdf.tolist()}
            print(f"[{time.time()-t0:6.1f}s] {name:22s} range "
                  f"[{vmin:.6g}, {vmax:.6g}] n={total:,}", flush=True)

    payload = {
        "nbins": NBINS,
        "footprint_pixels": n_valid_total,
        "bin_rule": ("bin = clip(floor((v - vmin) * nbins / (vmax - vmin)), "
                     "0, nbins-1); rank = (cdf[bin] - 0.5*counts[bin]) / total "
                     "(bin midpoint), computed in build_features.py"),
        "sample_sha256": raster.sha256_file(SAMPLE),
        "features_sha256": raster.sha256_file(FEATURES),
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bands": tables,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload) + "\n")
    print(json.dumps({"out": str(OUT), "seconds": round(time.time() - t0, 1),
                      "bytes": OUT.stat().st_size}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

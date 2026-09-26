#!/usr/bin/env python3
"""Train the chosen model on all labelled pixels and write the submission file.

Pipeline
--------
  1. read the derived feature memmap (scripts/build_features.py) and the catalogue
     labels; restrict to the official scored footprint
  2. train the chosen classifier (HistGradientBoosting, the model that was scored
     in scripts/analysis.py on spatially blocked, buffered folds)
  3. predict a probability surface over the whole footprint, in row chunks
  4. apply the placement strategy that actually won in the blocked CV
  5. write the GeoTIFF with NaN outside the footprint and run validate_submission

The output name is content-addressed and carries the strategy + model tag so that
later attempts can be told apart (the brief asks for exactly that).

    python scripts/build_submission.py --tag hgb48-densified
    python scripts/build_submission.py --tag hgb105-topk03-g25 --n-channels 105 \\
        --strategy topk_gate@0.03 --gate g25_4 --pos-weight itrace --save-prob
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gems import metric, placement, raster, spec  # noqa: E402

LABELS = REPO_ROOT / "data" / "labels.tif"
SAMPLE = REPO_ROOT / "data" / "sample_submission.tif"
EV = REPO_ROOT / "data" / "evidence"
DOWNLOADS = REPO_ROOT / "downloads"


def load_truth():
    with rasterio.open(LABELS) as src:
        lab = src.read(1)
    with rasterio.open(SAMPLE) as src:
        footprint = np.isfinite(src.read(1))
    return (lab == 1), footprint


def itrace_weights(gt: np.ndarray) -> np.ndarray | None:
    """PU-style positive weights: 1/sqrt(trace length), normalised to mean 1.

    The catalogue over-represents long, thoroughly mapped faults (their pixels
    dominate the positive class) while both scored rounds contain faults that
    are MISSING from it — short, un-mapped segments. Down-weighting pixels on
    long traces (exactly the same rule scripts/experiment.py --pos-weight uses)
    keeps the classifier from memorising the catalogue's line density.
    """
    from scipy import ndimage
    trace_id, n_trace = ndimage.label(gt, structure=np.ones((3, 3), dtype=int))
    lens = np.bincount(trace_id.ravel(), minlength=n_trace + 1)
    raw = 1.0 / np.sqrt(lens[trace_id].astype(np.float64))
    # Background weight MUST be 1.0, not 0.0: sample_weight=0 drops a sample
    # from the fit entirely and would delete every negative pixel.
    w = np.ones(gt.shape, dtype=np.float32)
    w[gt] = raw[gt]
    w[gt] = w[gt] / w[gt].mean()
    return w


def build_gate(meta_channels: list[str], mm: np.ndarray, name: str) -> np.ndarray:
    """The cross-family agreement gate, identical to scripts/experiment.py."""
    if name == "g25_4":
        i = meta_channels.index("n_agree_top25")
        return np.asarray(mm[:, :, i] >= 4, dtype=bool)
    if name == "g10_4":
        i = meta_channels.index("n_agree_top10")
        return np.asarray(mm[:, :, i] >= 4, dtype=bool)
    raise ValueError(f"unknown gate {name!r} (expected g25_4 or g10_4)")


def train_model(mm_path: Path, n_channels: int, gt: np.ndarray,
                footprint: np.ndarray, max_neg: int, seed: int = 7,
                iters: int = 300, pos_weight: np.ndarray | None = None):
    from sklearn.ensemble import HistGradientBoostingClassifier

    mm = np.load(mm_path, mmap_mode="r")
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero((gt & footprint).ravel())
    neg_pool = np.flatnonzero((~gt & footprint).ravel())
    n_neg = min(neg_pool.size, max_neg)
    neg = rng.choice(neg_pool, size=n_neg, replace=False)
    sel = np.concatenate([pos, neg])
    rows, cols = np.unravel_index(sel, gt.shape)
    X = np.asarray(mm[rows, cols, :n_channels], dtype=np.float32)
    y = gt.ravel()[sel].astype(np.uint8)
    w = pos_weight[rows, cols].astype(np.float32) if pos_weight is not None else None
    model = HistGradientBoostingClassifier(
        max_iter=iters, learning_rate=0.08, max_leaf_nodes=31,
        min_samples_leaf=40, l2_regularization=1.0, random_state=seed,
        early_stopping=False)
    model.fit(X, y, sample_weight=w)
    return model, {"n_pos": int(pos.size), "n_neg": int(n_neg),
                   "n_features": int(X.shape[1]), "max_iter": int(iters),
                   "sample_weight": "itrace" if w is not None else "none"}


def predict_full(mm_path: Path, model, footprint: np.ndarray, n_channels: int,
                 chunk_rows: int = 256) -> np.ndarray:
    mm = np.load(mm_path, mmap_mode="r")
    h, w = footprint.shape
    out = np.zeros((h, w), dtype=np.float32)
    for r0 in range(0, h, chunk_rows):
        r1 = min(r0 + chunk_rows, h)
        block_fp = footprint[r0:r1]
        if not block_fp.any():
            continue
        rows, cols = np.nonzero(block_fp)
        X = np.asarray(mm[r0 + rows, cols, :n_channels], dtype=np.float32)
        out[r0 + rows, cols] = model.predict_proba(X)[:, 1].astype(np.float32)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="hgb48-densified")
    ap.add_argument("--features", default=str(EV / "features.f32.npy"))
    ap.add_argument("--features-meta", default=str(EV / "features_meta.json"))
    ap.add_argument("--max-neg", type=int, default=400_000)
    ap.add_argument("--iters", type=int, default=300)
    ap.add_argument("--n-channels", type=int, default=0,
                    help="use only the first N channels of the stack "
                         "(0 = all). The blocked-CV comparison found the extra "
                         "multi-scale channels did not improve the score, so the "
                         "shipped model uses the validated subset.")
    ap.add_argument("--threshold", type=float, default=0.10)
    ap.add_argument("--strategy", default="densified",
                    help="any name from src/gems/placement.py; the gated variant "
                         "is topk_gate@<frac> (requires --gate)")
    ap.add_argument("--gate", choices=["none", "g25_4", "g10_4"], default="none",
                    help="cross-family agreement gate for topk_gate@ strategies "
                         "(identical definitions to scripts/experiment.py)")
    ap.add_argument("--pos-weight", choices=["none", "itrace"], default="none",
                    help="itrace = PU-style 1/sqrt(trace length) positive weights "
                         "(same rule as scripts/experiment.py --pos-weight)")
    ap.add_argument("--save-prob", action="store_true",
                    help="also save the raw probability surface as float32 npy "
                         "(~49 MB, evidence-only, used by candidate_writeup.py)")
    ap.add_argument("--out-dir", default=str(DOWNLOADS))
    args = ap.parse_args()

    t0 = time.time()
    meta = json.loads(Path(args.features_meta).read_text())
    channels = meta["channels"]
    n_channels = args.n_channels if args.n_channels > 0 else len(channels)
    if n_channels > len(channels):
        raise SystemExit(f"--n-channels {n_channels} exceeds the stack "
                         f"({len(channels)} channels)")
    gt, footprint = load_truth()
    print(f"[{time.time()-t0:6.1f}s] footprint {int(footprint.sum())} px, "
          f"positives {int((gt & footprint).sum())}")

    pos_weight = None
    if args.pos_weight == "itrace":
        pos_weight = itrace_weights(gt)
        print("pos_weight=itrace (1/sqrt(trace length), normalised to mean 1)")

    gate = None
    if args.strategy.startswith("topk_gate@"):
        if args.gate == "none":
            raise SystemExit("--gate g25_4|g10_4 is required for topk_gate@ strategies")
        mm = np.load(args.features, mmap_mode="r")
        gate = build_gate(channels, mm, args.gate)
        print(f"gate={args.gate}: {int(gate.sum()):,} px")
        del mm
    elif args.gate != "none":
        print(f"note: --gate {args.gate} ignored (strategy {args.strategy!r} is not gated)")

    model, train_info = train_model(Path(args.features), n_channels, gt,
                                    footprint, args.max_neg, iters=args.iters,
                                    pos_weight=pos_weight)
    print(f"[{time.time()-t0:6.1f}s] trained on {train_info}")

    prob = predict_full(Path(args.features), model, footprint, n_channels)
    print(f"[{time.time()-t0:6.1f}s] predicted full footprint; "
          f"max={prob.max():.4f} mean_pos={prob[prob>0].mean():.4f}")

    if args.save_prob:
        EV.mkdir(parents=True, exist_ok=True)
        prob_path = EV / f"prob_{args.tag}.f32.npy"
        np.save(prob_path, prob.astype(np.float32))
        print(f"saved probability surface -> {prob_path} "
              f"({prob_path.stat().st_size / 1e6:.1f} MB)")

    placed = placement.get_strategy(args.strategy, prob, footprint,
                                    threshold=args.threshold, gate=gate)
    placed = np.where(footprint, placed, 0.0).astype(np.float32)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / f"_{args.tag}.tif"
    raster.write_submission(placed, tmp, SAMPLE, footprint=footprint)
    digest = raster.sha256_file(tmp)[:10]
    final = out_dir / f"gems6_{args.tag}_{digest}.tif"
    tmp.replace(final)

    report = raster.check_submission(final)
    print(report.text())
    (EV / "submission_report.json").write_text(json.dumps({
        "file": final.name,
        "sha256": raster.sha256_file(final),
        "bytes": final.stat().st_size,
        "gate_ok": report.ok,
        "gate": report.as_dict(),
        "strategy": args.strategy,
        "agreement_gate": args.gate if args.strategy.startswith("topk_gate@") else None,
        "threshold": args.threshold,
        "pos_weight": args.pos_weight,
        "prob_surface": (f"prob_{args.tag}.f32.npy" if args.save_prob else None),
        "model": (f"HistGradientBoostingClassifier(max_iter={args.iters}, "
                  "lr=0.08, max_leaf_nodes=31, min_samples_leaf=40, "
                  "l2_regularization=1.0)"),
        "train": {k: (v.item() if hasattr(v, "item") else v)
                  for k, v in train_info.items()},
        "n_channels": int(n_channels),
        "channels_available": len(channels),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2, default=str) + "\n")

    if not report.ok:
        print("REFUSING to publish a file that fails the gate.", file=sys.stderr)
        return 1
    print(f"[{time.time()-t0:6.1f}s] wrote {final}")
    print("positive pixels:", int((placed > 0).sum()))
    del gt, footprint, prob, placed
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

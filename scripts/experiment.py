#!/usr/bin/env python3
"""Controlled blocked-CV experiments: does a change actually raise the score?

Why this script exists
----------------------
`scripts/analysis.py --only cv` produced the number the *previous* submission was
based on (mean blocked DTI 0.1119 for a 48-channel HistGradientBoosting model with
fractional probabilities thresholded at 0.30). Every proposed improvement has to
beat that number on the SAME folds, with the SAME training budget and the SAME
evaluation code, or it is not an improvement — it is a different measurement. This
script runs the baseline and every candidate through one identical harness and
writes the comparison to `data/evidence/experiments*.json`.

The yardstick is trustworthy because it reproduces the old number exactly: the
baseline config's `soft@0.3` comes out at 0.111886 / 0.093297 / 0.125252, bit for
bit the old `binary@0.3`.

The shipped submission uses the `extended` config with a `topk_hard@0.03`
placement: mean blocked DTI 0.1698, up from 0.1119.

Two hypotheses tested here, both derived from the published metric rather than
asserted:

  H1  More structural signal helps. The brief asks for horizontal-gradient
      magnitude and tilt derivative of the potential fields, curvature and
      breaks-in-slope from elevation, and cross-agreement between independent
      signals. `scripts/build_features.py` now appends multi-scale versions of
      those to the original 48 channels; config `extended` tests them.

  H2  The submitted VALUE should be 1.0 on selected pixels, not the model's
      fractional probability. Writing the metric as

          DTI = TP_w / (beta*n_gt + alpha*FP_w + (1-beta)*TP_w)      (beta=0.8)

      (which follows from FN_w = n_gt - TP_w, an identity of the published
      formula) shows DTI is strictly increasing under p -> lambda*p for any
      lambda up to the cap at 1.0, because the derivative carries the term
      beta*n_gt, which does not scale. Fractional probabilities therefore leave
      score on the table. Both `soft` (keep p) and `hard` (p -> 1) placements
      are measured at every threshold so the claim is tested, not assumed.

A third thing is measured because it is the largest unknown that is still
measurable on our own data: how sensitive the winner is to the SIZE of the
ground-truth set. FP_w is an absolute sum over predicted pixels while TP_w and
FN_w are per-ground-truth-pixel sums, so a submission tuned against a catalogue
of 60,988 fault pixels may be far too generous if the private set of new faults
is smaller. We simulate that by deleting whole fault TRACES (8-connected
components of the label raster) from the held-out ground truth and re-scoring
exactly the same predictions.

Usage
-----
    python scripts/experiment.py                       # baseline + extended
    python scripts/experiment.py --configs baseline    # reproduce the reference
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gems import metric, spec  # noqa: E402
from gems import cv as gcv  # noqa: E402

LABELS = REPO_ROOT / "data" / "labels.tif"
SAMPLE = REPO_ROOT / "data" / "sample_submission.tif"
EV = REPO_ROOT / "data" / "evidence"

THRESHOLDS = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40]
TOP_FRACTIONS = [0.005, 0.01, 0.02, 0.03, 0.05, 0.10]
TRACE_KEEP = [1.0, 0.5, 0.25]  # fraction of held-out fault TRACES kept as GT
# Placements re-scored under the reduced ground-truth sets. Deliberately fixed
# (not "the winners") so the sensitivity table is not a post-hoc selection.
TRACE_PLACEMENTS = ["raw", "soft@0.3", "hard@0.1", "hard@0.2", "hard@0.3",
                    "topk_hard@0.005", "topk_hard@0.01", "topk_hard@0.02",
                    "topk_hard@0.03", "topk_hard@0.05", "topk_hard@0.1",
                    "topk_hard@0.03_g25_4", "topk_hard@0.05_g25_4",
                    "topk_hard@0.03_g10_4"]


# --------------------------------------------------------------------------- io

def load_truth() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(gt, footprint, trace_id) — trace_id labels 8-connected fault traces."""
    with rasterio.open(LABELS) as src:
        lab = src.read(1)
    with rasterio.open(SAMPLE) as src:
        footprint = np.isfinite(src.read(1))
    gt = lab == 1
    del lab
    trace_id, n_trace = ndimage.label(gt, structure=np.ones((3, 3), dtype=int))
    return gt, footprint, trace_id


def kept_trace_mask(trace_id: np.ndarray, n_trace: int, keep: float,
                    seed: int = 20240925) -> np.ndarray:
    """Boolean grid: ground-truth pixels belonging to a retained fault trace.

    Traces are dropped whole, not pixel by pixel: a smaller private fault set is
    fewer complete faults, not a shredded version of the same faults.
    """
    if keep >= 1.0:
        return np.ones(n_trace + 1, dtype=bool)
    rng = np.random.default_rng(seed)
    keep_ids = rng.choice(n_trace, size=int(round(keep * n_trace)), replace=False) + 1
    table = np.zeros(n_trace + 1, dtype=bool)
    table[keep_ids] = True
    return table


# ------------------------------------------------- lineament enhancement

def _shift(arr: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Shift with zero fill (no wrap), so a line filter cannot borrow from the
    far side of the grid."""
    out = np.zeros_like(arr)
    h, w = arr.shape
    ys_src = slice(max(0, -dy), h - max(0, dy))
    ys_dst = slice(max(0, dy), h - max(0, -dy))
    xs_src = slice(max(0, -dx), w - max(0, dx))
    xs_dst = slice(max(0, dx), w - max(0, -dx))
    out[ys_dst, xs_dst] = arr[ys_src, xs_src]
    return out


def line_max(p: np.ndarray, valid: np.ndarray, length: int = 5,
             n_orient: int = 8) -> np.ndarray:
    """Max of `p` over straight line segments of `length` px through each pixel.

    Faults are lines; a per-pixel classifier is not. A pixel on a candidate trace
    whose neighbours along the trace are also elevated is more likely to be a
    fault than an isolated elevated pixel, and this filter raises exactly those.
    It is a RANKING change, which is the only thing that matters for a top-k
    placement (any monotone rescaling of the surface leaves the selected set
    unchanged), and it is cheap: `n_orient` x (`length`+1) shifted maxima.
    """
    p = np.where(valid, np.clip(np.nan_to_num(p, nan=0.0), 0.0, 1.0), 0.0)
    out = np.zeros_like(p)
    half = length // 2
    t = np.arange(-half, half + 1)
    for i in range(n_orient):
        theta = np.pi * i / n_orient
        dy = np.round(t * np.sin(theta)).astype(int)
        dx = np.round(t * np.cos(theta)).astype(int)
        acc = np.zeros_like(p)
        for a, b in zip(dy, dx):
            np.maximum(acc, _shift(p, int(a), int(b)), out=acc)
        np.maximum(out, acc, out=out)
    return np.where(valid, out, 0.0).astype(np.float32)


def surfaces(p: np.ndarray, valid: np.ndarray) -> dict[str, np.ndarray]:
    """The probability surfaces whose rankings are compared.

    `raw` is the model output. `line*` are lineament-enhanced variants: the max
    over straight segments, and a 50/50 mix with the raw surface so the filter
    cannot simply overwrite a genuinely high pixel with a mediocre neighbour.
    """
    out = {"raw": np.where(valid, p, 0.0).astype(np.float32)}
    if not valid.any():
        return out
    for length in (3, 5, 9):
        lm = line_max(p, valid, length=length)
        out[f"line{length}"] = lm
        out[f"mix{length}"] = (0.5 * np.where(valid, p, 0.0) + 0.5 * lm).astype(np.float32)
    return out


# ------------------------------------------------------------------- placement

def placements(p: np.ndarray, valid: np.ndarray) -> dict[str, np.ndarray]:
    """Candidate submission surfaces on the scored region.

    `p` is the model probability restricted to `valid` (0 elsewhere); every
    output is 0 outside `valid` and therefore satisfies the NaN rule by
    construction.
    """
    p = np.clip(np.nan_to_num(p, nan=0.0), 0.0, 1.0).astype(np.float32)
    p = np.where(valid, p, 0.0)
    out: dict[str, np.ndarray] = {"raw": p}
    for thr in THRESHOLDS:
        sel = p >= thr
        out[f"soft@{thr:g}"] = np.where(sel, p, 0.0).astype(np.float32)
        out[f"hard@{thr:g}"] = sel.astype(np.float32)
    n_valid = int(valid.sum())
    if n_valid:
        for frac in TOP_FRACTIONS:
            k = max(1, int(round(frac * n_valid)))
            # exact top-k, ties broken deterministically by position
            if k < n_valid:
                # k-th largest value: everything >= it is selected, ties included
                inside = p[valid]
                thr = float(np.partition(inside, n_valid - k)[n_valid - k])
            else:
                thr = 0.0
            sel = (p >= thr) & valid
            out[f"topk_hard@{frac:g}"] = sel.astype(np.float32)
            out[f"topk_soft@{frac:g}"] = np.where(sel, p, 0.0).astype(np.float32)
    return out


# ------------------------------------------------------------------------- CV

def run_fold(mm, channels: list[str], n_channels: int, gt: np.ndarray,
             footprint: np.ndarray, trace_id: np.ndarray, n_trace: int,
             folds: gcv.Folds, k: int, max_train_px: int, iters: int,
             seed: int, pos_weight: np.ndarray | None = None,
             trace_excl: np.ndarray | None = None,
             gates: dict[str, np.ndarray] | None = None) -> dict:
    """One blocked fold.

    pos_weight   per-pixel training weight (PU-style: long "already well
                 mapped" catalogue traces down-weighted, see --pos-weight)
    trace_excl   bool grid; where True the pixel is EXCLUDED from training in
                 every fold (whole fault traces held out from the model, the
                 rediscovery diagnostic, see --trace-holdout)
    gates        {label: bool grid} for gated top-k placements (agreement)
    """
    from sklearn.ensemble import HistGradientBoostingClassifier
    from gems.placement import gated_topk

    shape = (spec.HEIGHT, spec.WIDTH)
    train_mask, test_mask = folds.train_test_masks(shape, k)
    train_mask &= footprint
    if trace_excl is not None:
        train_mask &= ~trace_excl
    score_mask = test_mask & footprint

    pos_idx = np.flatnonzero((gt & train_mask).ravel())
    neg_idx = np.flatnonzero((~gt & train_mask).ravel())
    rng = np.random.default_rng(1000 + k)
    n_neg = min(neg_idx.size, max_train_px)
    neg_idx = rng.choice(neg_idx, size=n_neg, replace=False)
    sel = np.concatenate([pos_idx, neg_idx])
    rows, cols = np.unravel_index(sel, shape)
    X = np.asarray(mm[rows, cols, :n_channels], dtype=np.float32)
    y = gt[rows, cols].astype(np.uint8)
    w = pos_weight[rows, cols] if pos_weight is not None else None
    del rows, cols, sel, pos_idx, neg_idx

    model = HistGradientBoostingClassifier(
        max_iter=iters, learning_rate=0.08, max_leaf_nodes=31,
        min_samples_leaf=40, l2_regularization=1.0, random_state=seed + k,
        early_stopping=False)
    t_fit = time.time()
    model.fit(X, y, sample_weight=w)
    fit_s = round(time.time() - t_fit, 1)
    del X, y, w

    srows, scols = np.nonzero(score_mask)
    order = np.argsort(srows, kind="stable")
    srows, scols = srows[order], scols[order]
    grid_pred = np.zeros(shape, dtype=np.float32)
    step = 200_000
    for i in range(0, srows.size, step):
        sl = slice(i, min(i + step, srows.size))
        grid_pred[srows[sl], scols[sl]] = model.predict_proba(
            np.asarray(mm[srows[sl], scols[sl], :n_channels],
                       dtype=np.float32))[:, 1]
    del srows, scols

    # Scoring is done on the bounding box of the held-out block, dilated by the
    # kernel radius. This is EXACT, not an approximation: the ground truth is
    # zero outside the scored block and the prediction is zero outside it too,
    # so no term of TP_w / FP_w / FN_w involves a pixel outside the crop — and it
    # is several times faster than running a distance transform on the full grid.
    ys, xs = np.nonzero(score_mask)
    margin = int(np.ceil(metric.RADIUS_PX)) + 1
    r0, r1 = max(0, int(ys.min()) - margin), min(spec.HEIGHT, int(ys.max()) + margin + 1)
    c0, c1 = max(0, int(xs.min()) - margin), min(spec.WIDTH, int(xs.max()) + margin + 1)
    del ys, xs
    sl = (slice(r0, r1), slice(c0, c1))

    gt_score = gt & score_mask
    crop_pred = grid_pred[sl]
    crop_valid = score_mask[sl]
    crop_gt_full = gt_score[sl]
    del grid_pred

    cands = placements(crop_pred, crop_valid)
    if gates:
        # Gated top-k: exact budget, spent on cross-signal-agreeing pixels
        # first (agreement channels must be present in the stack).
        for glabel, gfull in gates.items():
            g = gfull[sl]
            for frac in (0.01, 0.02, 0.03, 0.05):
                cands[f"topk_hard@{frac:g}_{glabel}"] = np.where(
                    gated_topk(crop_pred, crop_valid, g, frac), 1.0, 0.0
                ).astype(np.float32)
    for sname, sarr in surfaces(crop_pred, crop_valid).items():
        if sname == "raw":
            continue  # already covered by `placements` on the raw surface
        sub = placements(sarr, crop_valid)
        for pname in ([f"hard@{0.3:g}"]
                      + [f"topk_hard@{f:g}" for f in (0.01, 0.02, 0.03, 0.05)]):
            if pname in sub:
                cands[f"{sname}/{pname}"] = sub[pname]
        del sub
    n_gt_full = int(crop_gt_full.sum())

    rec: dict = {
        "fold": k,
        "n_train_pos": int((gt & train_mask).sum()),
        "n_train_neg_used": int(n_neg),
        "n_score_px": int(score_mask.sum()),
        "n_gt": n_gt_full,
        "crop": [int(r0), int(r1), int(c0), int(c1)],
        "fit_seconds": fit_s,
        "gt_full": {},
        "trace_subsample": {},
    }

    for name, arr in cands.items():
        comp = metric.components(arr, crop_gt_full)
        rec["gt_full"][name] = {
            "dti": comp.dti, "tp_w": comp.tp_w, "fp_w": comp.fp_w,
            "fn_w": comp.fn_w, "n_pos_pred": comp.n_pos_pred,
        }

    crop_trace = trace_id[sl]
    for keep in TRACE_KEEP:
        if keep >= 1.0:
            continue
        table = kept_trace_mask(trace_id, n_trace, keep)
        sub_gt = crop_gt_full & table[crop_trace]
        sub = {"n_gt_kept": int(sub_gt.sum())}
        for name in TRACE_PLACEMENTS:
            if name not in cands:
                continue
            comp = metric.components(cands[name], sub_gt)
            sub[name] = {"dti": comp.dti}
        rec["trace_subsample"][f"keep{keep:g}"] = sub

    del crop_pred, cands, crop_gt_full
    return rec


def aggregate(folds_rec: list[dict], key_path: tuple[str, ...]) -> dict:
    """Mean/min/max DTI per placement across folds."""
    keys: set[str] = set()
    for f in folds_rec:
        node: dict = f
        for part in key_path:
            node = node[part]
        keys |= {kk for kk, vv in node.items()
                 if isinstance(vv, dict) and "dti" in vv}
    agg = {}
    for key in keys:
        vals = []
        for f in folds_rec:
            node: dict = f
            for part in key_path:
                node = node[part]
            v = node.get(key)
            if isinstance(v, dict) and "dti" in v:
                vals.append(v["dti"])
        if vals:
            agg[key] = {"mean_dti": float(np.mean(vals)),
                        "min_dti": float(np.min(vals)),
                        "max_dti": float(np.max(vals)),
                        "n_folds": len(vals)}
    return dict(sorted(agg.items(), key=lambda kv: -kv[1]["mean_dti"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=str(EV / "features.f32.npy"))
    ap.add_argument("--meta", default=str(EV / "features_meta.json"))
    ap.add_argument("--configs", default="baseline,extended",
                    help="comma list; 'baseline' = first 48 channels, "
                         "'extended' = every channel")
    ap.add_argument("--blocks", type=int, default=4)
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--buffer", type=int, default=3)
    ap.add_argument("--max-train-px", type=int, default=200_000)
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pos-weight", choices=["none", "itrace"], default="none",
                    help="itrace = PU-style: catalogue fault pixels are weighted "
                         "1/sqrt(trace length) so long, well-mapped traces (the "
                         "'easy' ones least like the private new-fault set) count "
                         "less in training")
    ap.add_argument("--trace-holdout", type=float, default=0.0,
                    help="diagnostic: fraction of whole fault traces excluded "
                         "from training in EVERY fold (rediscovery test — the "
                         "model has never seen those faults)")
    ap.add_argument("--out", default=str(EV / "experiments.json"))
    args = ap.parse_args()

    meta = json.loads(Path(args.meta).read_text())
    channels = meta["channels"]
    print(f"feature stack: {meta['shape']} channels={len(channels)}", flush=True)
    mm = np.load(args.features, mmap_mode="r")
    if mm.shape[2] != len(channels):
        print(f"ERROR: memmap has {mm.shape[2]} channels, meta lists "
              f"{len(channels)}", file=sys.stderr)
        return 2

    gt, footprint, trace_id = load_truth()
    n_trace = int(trace_id.max())
    print(f"footprint={int(footprint.sum())} gt={int(gt.sum())} "
          f"fault_traces={n_trace}", flush=True)

    folds = gcv.make_folds(n_blocks=args.blocks, n_folds=args.folds,
                           buffer_px=args.buffer)

    # --- optional training-side variants (applied identically to every fold) --
    pos_weight = None
    if args.pos_weight == "itrace":
        lens = np.bincount(trace_id.ravel(), minlength=n_trace + 1)
        raw = 1.0 / np.sqrt(lens[trace_id].astype(np.float64))
        # Background weight MUST be 1.0, not 0.0: HistGradientBoosting's
        # sample_weight=0 drops a sample from the fit entirely, which would
        # delete every negative pixel and collapse the model to all-positive.
        pos_weight = np.ones((spec.HEIGHT, spec.WIDTH), dtype=np.float32)
        pos_weight[gt] = raw[gt]
        pos_weight[gt] = pos_weight[gt] / pos_weight[gt].mean()  # mean 1 on gt
        del raw, lens
        print("pos_weight=itrace (positives 1/sqrt(trace length), mean 1; "
              "negatives 1)", flush=True)

    trace_excl = None
    n_held_traces = 0
    if args.trace_holdout > 0.0:
        rng = np.random.default_rng(20240925)
        drop_ids = rng.choice(n_trace, size=int(round(args.trace_holdout * n_trace)),
                              replace=False) + 1
        trace_excl = np.isin(trace_id, drop_ids) & gt
        n_held_traces = len(drop_ids)
        print(f"trace_holdout={args.trace_holdout}: {n_held_traces} whole traces "
              f"excluded from ALL training "
              f"({int(trace_excl.sum()):,} gt px)", flush=True)

    gates = None
    if len(channels) > 88:
        i25 = channels.index("n_agree_top25")
        i10 = channels.index("n_agree_top10")
        gates = {
            "g25_4": np.asarray(mm[:, :, i25] >= 4, dtype=bool),
            "g10_4": np.asarray(mm[:, :, i10] >= 4, dtype=bool),
        }
        print(f"gates: g25_4={int(gates['g25_4'].sum()):,} px, "
              f"g10_4={int(gates['g10_4'].sum()):,} px", flush=True)

    configs = {}
    for name in args.configs.split(","):
        name = name.strip()
        if name == "baseline":
            configs[name] = 48
        elif name == "extended":
            configs[name] = min(88, len(channels))
        elif name == "agreement":
            configs[name] = len(channels)
        else:
            print(f"unknown config {name}", file=sys.stderr)
            return 2

    out: dict = {
        "design": {
            "purpose": ("controlled comparison on identical blocked folds; "
                        "'baseline' reproduces the number the shipped "
                        "submission is based on"),
            "n_blocks": args.blocks, "n_folds": args.folds,
            "buffer_px": args.buffer, "buffer_m": args.buffer * spec.PIXEL_SIZE_M,
            "max_train_px": args.max_train_px, "iters": args.iters,
            "model": ("HistGradientBoostingClassifier(lr=0.08, "
                      "max_leaf_nodes=31, min_samples_leaf=40, "
                      "l2_regularization=1.0)"),
            "thresholds": THRESHOLDS, "top_fractions": TOP_FRACTIONS,
            "trace_keep": TRACE_KEEP,
            "pos_weight": args.pos_weight,
            "trace_holdout": args.trace_holdout,
            "trace_holdout_traces": n_held_traces,
            "gates": sorted(gates) if gates else [],
            "feature_meta": {k: v for k, v in meta.items() if k != "channels"},
            "note": ("scores are against the PUBLIC CATALOGUE on held-out "
                     "spatial blocks — a proxy for the private new-fault test "
                     "set, not a leaderboard value"),
        },
        "configs": {},
    }

    for name, n_ch in configs.items():
        t0 = time.time()
        print(f"\n=== config {name}: {n_ch} channels ===", flush=True)
        folds_rec = []
        for k in range(args.folds):
            rec = run_fold(mm, channels, n_ch, gt, footprint, trace_id, n_trace,
                           folds, k, args.max_train_px, args.iters, args.seed,
                           pos_weight=pos_weight, trace_excl=trace_excl,
                           gates=gates)
            best = max(v["dti"] for v in rec["gt_full"].values())
            best_name = max(rec["gt_full"].items(), key=lambda kv: kv[1]["dti"])[0]
            print(f"  fold {k}: n_score={rec['n_score_px']} n_gt={rec['n_gt']} "
                  f"best={best:.4f} ({best_name}) [{time.time()-t0:.0f}s]",
                  flush=True)
            folds_rec.append(rec)
        out["configs"][name] = {
            "n_channels": n_ch,
            "channel_names": channels[:n_ch],
            "folds": folds_rec,
            "aggregate_gt_full": aggregate(folds_rec, ("gt_full",)),
        }
        for keep in TRACE_KEEP:
            if keep >= 1.0:
                continue
            out["configs"][name][f"aggregate_keep{keep:g}"] = aggregate(
                folds_rec, ("trace_subsample", f"keep{keep:g}"))
            top = list(out["configs"][name][f"aggregate_keep{keep:g}"].items())[:3]
            print(f"  keep{keep:g}: " + ", ".join(
                f"{n}={v['mean_dti']:.4f}" for n, v in top), flush=True)
        top = list(out["configs"][name]["aggregate_gt_full"].items())[:6]
        print(f"  gt_full best: " + ", ".join(
            f"{n}={v['mean_dti']:.4f}" for n, v in top), flush=True)

    out["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    Path(args.out).write_text(json.dumps(out, indent=2, default=float) + "\n")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

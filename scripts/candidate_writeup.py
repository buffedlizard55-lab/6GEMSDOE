#!/usr/bin/env python3
"""Turn the submitted placement into a defensible, per-candidate geological record.

Phase 2 of the GEMS Prize is judged by geologists reading what we flagged, so
every high-confidence prediction needs more than a pixel count: where it is
(lat/lon), what trend it strikes, how long it is, how confident the model is,
how many independent physical families agree there, and whether the USGS
Quaternary Fault and Fold catalogue already covers it. This script produces
exactly that record, deterministically, from the actual shipped file:

  * reads the final submission GeoTIFF (the exact mask that gets scored),
  * 8-connected components, min size filter (default 8 px = 800 m of line),
  * per component: UTM bbox -> WGS84 ring, PCA azimuth, length, probability
    statistics, per-family median evidence rank (famrank_* channels),
    cross-family agreement (n_agree_top25), and distance to the nearest
    catalogue fault pixel -> NEW / NEAR-CATALOGUE / ON-CATALOGUE,
  * writes data/evidence/candidates.json (machine-readable, sha-pinned to the
    submission file, the probability surface and the feature stack) and
    docs/CANDIDATES.md (the human-readable record with the regional tectonic
    frame, per RESEARCH.md section 6).

    python scripts/candidate_writeup.py \
        --submission downloads/gems6_hgb88-topk03_33cec71ff0.tif \
        --prob data/evidence/prob_hgb88-topk03.f32.npy
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform as crs_transform
from scipy import ndimage

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gems import raster, spec  # noqa: E402

EV = REPO_ROOT / "data" / "evidence"
DOCS = REPO_ROOT  # top-level docs live at the repo root

FAMILIES = ["mag", "grav", "strain", "seis", "cond", "topo"]


def sha256_file(p: Path) -> str:
    return raster.sha256_file(p)


UTM = CRS.from_epsg(spec.EPSG)
WGS84 = CRS.from_epsg(4326)


def to_wgs84(xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """UTM (x=m easting, y=m northing) -> (lon, lat)."""
    return crs_transform(UTM, WGS84, np.asarray(xs, float), np.asarray(ys, float))


def wgs84_ring(minx: float, miny: float, maxx: float, maxy: float) -> list[list[float]]:
    """UTM bbox corners -> WGS84 [lon, lat] ring (4 corners, closed)."""
    lons, lats = to_wgs84([minx, maxx, maxx, minx], [miny, miny, maxy, maxy])
    ring = [[round(lo, 6), round(la, 6)] for lo, la in zip(lons, lats)]
    ring.append(ring[0])
    return ring


def pca_azimuth_deg(rows: np.ndarray, cols: np.ndarray) -> float:
    """Azimuth of the component's major axis, degrees clockwise from north
    (0-180, so N-S and S-N are the same line)."""
    pts = np.stack([rows.astype(np.float64), cols.astype(np.float64)])
    pts -= pts.mean(axis=1, keepdims=True)
    if pts.shape[1] < 2:
        return 0.0
    cov = (pts @ pts.T) / pts.shape[1]
    evals, evecs = np.linalg.eigh(cov)
    v = evecs[:, int(np.argmax(evals))]  # (row, col)
    dr, dc = float(v[0]), float(v[1])
    # geographic: north = -row, east = +col
    az = np.degrees(np.arctan2(dc, -dr)) % 180.0
    return round(float(az), 1)


def component_stats(comp_lab: np.ndarray, label_id: int, prob: np.ndarray,
                    fam: dict[str, np.ndarray], agree25: np.ndarray,
                    dist_cat: np.ndarray) -> dict:
    sel = comp_lab == label_id
    rows, cols = np.nonzero(sel)
    n = int(rows.size)
    # UTM bounds of the component: pixel (r, c) top-left corner is at
    # (ORIGIN_X + c*res, ORIGIN_Y - r*res) on the submission grid.
    res = spec.PIXEL_SIZE_M
    minx = spec.ORIGIN_X + float(cols.min()) * res
    maxx = spec.ORIGIN_X + float(cols.max() + 1) * res
    miny = spec.ORIGIN_Y - float(rows.max() + 1) * res
    maxy = spec.ORIGIN_Y - float(rows.min()) * res
    if prob is None:
        p_mean = p_median = p_p95 = None
    else:
        p = prob[sel]
        p_mean, p_median, p_p95 = (float(p.mean()), float(np.median(p)),
                                   float(np.quantile(p, 0.95)))
    fr = {f: float(np.median(fam[f][sel])) for f in FAMILIES}
    d = float(dist_cat[sel].min())
    if d <= 1.0:
        cls = "on_catalogue"
    elif d <= 3.0:
        cls = "near_catalogue"
    else:
        cls = "new_to_catalogue"
    return {
        "id": int(label_id),
        "class": cls,
        "n_px": n,
        "length_m": n * spec.PIXEL_SIZE_M,
        "utm_bbox": [minx, miny, maxx, maxy],
        "wgs84_ring": wgs84_ring(minx, miny, maxx, maxy),
        "azimuth_deg": pca_azimuth_deg(rows, cols),
        "prob_mean": (None if p_mean is None else round(p_mean, 5)),
        "prob_median": (None if p_median is None else round(p_median, 5)),
        "prob_p95": (None if p_p95 is None else round(p_p95, 5)),
        "famrank_median": {f: (None if fr[f] < 0 else round(fr[f], 4)) for f in FAMILIES},
        "n_agree_top25_median": float(np.median(agree25[sel])),
        "dist_to_catalogue_m": round(d * spec.PIXEL_SIZE_M, 0),
    }


def md_table(rows: list[dict]) -> str:
    head = ("| # | class | length (m) | azim (deg) | median prob | agree4 | "
            "famrank medians (mag/gr/str/seis/cond/topo) | WGS84 bbox centre |")
    sep = "|---|---|---|---|---|---|---|---|"
    out = [head, sep]
    for i, c in enumerate(rows, 1):
        fr = c["famrank_median"]
        frs = "/".join("n/a" if fr[f] is None else f"{fr[f]:.2f}"
                       for f in FAMILIES)
        cx = (c["utm_bbox"][0] + c["utm_bbox"][2]) / 2.0
        cy = (c["utm_bbox"][1] + c["utm_bbox"][3]) / 2.0
        (lon,), (lat,) = to_wgs84([cx], [cy])
        pmed = "n/a" if c["prob_median"] is None else f"{c['prob_median']:.3f}"
        out.append(
            f"| {i} | {c['class']} | {c['length_m']} | {c['azimuth_deg']} "
            f"| {pmed} | {c['n_agree_top25_median']:.1f} "
            f"| {frs} | {lat:.4f}, {lon:.4f} |")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", required=True,
                    help="final submission GeoTIFF (the exact scored mask)")
    ap.add_argument("--prob", default=None,
                    help="probability surface npy saved by build_submission.py "
                         "--save-prob (needed for prob/famrank statistics)")
    ap.add_argument("--features", default=str(EV / "features.f32.npy"))
    ap.add_argument("--features-meta", default=str(EV / "features_meta.json"))
    ap.add_argument("--labels", default=str(REPO_ROOT / "data" / "labels.tif"))
    ap.add_argument("--min-px", type=int, default=8,
                    help="minimum component size in pixels (8 px = 800 m)")
    ap.add_argument("--out-json", default=str(EV / "candidates.json"))
    ap.add_argument("--out-md", default=str(REPO_ROOT / "CANDIDATES.md"))
    args = ap.parse_args()

    t0 = time.time()
    sub = Path(args.submission)
    meta = json.loads(Path(args.features_meta).read_text())
    channels = meta["channels"]

    with rasterio.open(sub) as src:
        assert src.width == spec.WIDTH and src.height == spec.HEIGHT, \
            f"submission grid {src.width}x{src.height} != spec"
        m = src.read(1)
    mask = (m > 0).astype(bool)

    with rasterio.open(args.labels) as src:
        gt = src.read(1) == 1

    prob = None
    prob_sha = None
    if args.prob:
        prob = np.load(args.prob).astype(np.float32)
        prob_sha = sha256_file(Path(args.prob))

    # Per-family evidence ranks come from the feature stack (105-channel layout).
    mm = np.load(args.features, mmap_mode="r")
    fam: dict[str, np.ndarray] = {}
    for f in FAMILIES:
        name = f"famrank_{f}"
        fam[f] = (np.asarray(mm[:, :, channels.index(name)], dtype=np.float32)
                  if name in channels
                  else np.full((spec.HEIGHT, spec.WIDTH), -1.0, np.float32))
    agree25 = (np.asarray(mm[:, :, channels.index("n_agree_top25")], dtype=np.float32)
               if "n_agree_top25" in channels
               else np.zeros((spec.HEIGHT, spec.WIDTH), np.float32))
    del mm

    dist_cat = ndimage.distance_transform_edt(~gt).astype(np.float32)

    comp_lab, n_comp = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    sizes = np.bincount(comp_lab.ravel())
    keep_ids = [int(i) for i in range(1, n_comp + 1) if sizes[i] >= args.min_px]
    print(f"[{time.time()-t0:6.1f}s] mask={int(mask.sum()):,} px, "
          f"components={n_comp}, kept(>={args.min_px}px)={len(keep_ids)}")

    stats = [component_stats(comp_lab, i, prob, fam, agree25, dist_cat)
             for i in keep_ids]
    stats.sort(key=lambda c: (0 if c["class"] == "new_to_catalogue"
                              else 1 if c["class"] == "near_catalogue" else 2,
                              -(c["prob_median"] if c["prob_median"] is not None
                                else 0.0)))
    counts = {c: sum(1 for s in stats if s["class"] == c)
              for c in ("new_to_catalogue", "near_catalogue", "on_catalogue")}

    payload = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "min_px": args.min_px,
        "provenance": {
            "submission_file": sub.name,
            "submission_sha256": sha256_file(sub),
            "prob_surface": (Path(args.prob).name if args.prob else None),
            "prob_surface_sha256": prob_sha,
            "features_sha256": meta.get("features_sha256"),
            "rank_tables_sha256": meta.get("rank_tables_sha256"),
            "labels_sha256": sha256_file(Path(args.labels)),
        },
        "n_components": len(stats),
        "class_counts": counts,
        "total_candidate_line_m": sum(c["length_m"] for c in stats),
        "candidates": stats,
    }
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2) + "\n")

    new = [c for c in stats if c["class"] == "new_to_catalogue"]
    near = [c for c in stats if c["class"] == "near_catalogue"]
    on = [c for c in stats if c["class"] == "on_catalogue"]
    md = []
    md.append("# Candidate fault traces — the Phase-2 record")
    md.append("")
    md.append(f"Generated {payload['generated_utc']} by `scripts/candidate_writeup.py` "
              f"from the **exact shipped submission** "
              f"`{sub.name}` (sha256 `{payload['provenance']['submission_sha256'][:16]}\u2026`), "
              f"{len(stats)} components of \u2265{args.min_px} px "
              f"({payload['total_candidate_line_m'] / 1000:,.0f} km of candidate line). "
              f"Full per-candidate geometry (WGS84 ring, UTM bbox, all statistics) "
              f"is in `data/evidence/candidates.json`.")
    if payload["provenance"]["prob_surface_sha256"] is None:
        md.append("")
        md.append("> **Note:** no probability surface was supplied (`--prob`), so "
                  "probability statistics are `n/a` and the tables are **not** "
                  "ordered by model confidence. Re-run with the `--save-prob` "
                  "output of `build_submission.py` for the final record.")
    md.append("")
    md.append("## How to read this")
    md.append("")
    md.append("- **class** — distance of the nearest model pixel to the nearest USGS "
              "Quaternary Fault and Fold catalogue pixel (the provided labels): "
              "`new_to_catalogue` > 300 m, `near_catalogue` \u2264 300 m, "
              "`on_catalogue` \u2264 100 m. Both scored rounds contain faults "
              "**missing from the catalogue**, so `new_to_catalogue` candidates are "
              "the ones that decide this prize; each must stand on its own evidence.")
    md.append("- **azimuth** — PCA major axis, degrees clockwise from north (0-180; "
              "90 = E-W, 45 = NW-SE, 135 = NE-SW).")
    md.append("- **agree4** — median number of the six independent physical families "
              "(magnetics, gravity, geodetic strain, seismicity, conductivity, "
              "topography) simultaneously in their global top 25% at that trace.")
    md.append("- **famrank medians** — per-family median evidence rank (0 = weakest "
              "pixel in the feature domain, 1 = strongest); `n/a` = family invalid there.")
    md.append("")
    md.append("## Regional tectonic frame")
    md.append("")
    md.append("The study area sits in the eastern Walker Lane / western Great Basin. "
              "The right-lateral, NW-directed Walker Lane shear zone transfers strain "
              "into NW-directed Basin-and-Range extension: range-bounding normal "
              "faults generally strike N-S to NW with strike-slip components, and the "
              "measured regional strain field is extension at ~30 nanostrain/yr with "
              "right-lateral shear on a N35\u00b0W-striking zone (Wesnousky et al. 2005, "
              "Tectonics; Hreinsd\u00f3ttir et al., USGS). Candidate trends at 0-60\u00b0 "
              "(N-S to NW) or 300-340\u00b0 (NW) are therefore consistent with the "
              "regional kinematics; trends outside that family still count but should "
              "be checked against local block rotation before being promoted.")
    md.append("")
    md.append(f"## New to the catalogue — {len(new)} candidates")
    md.append("")
    if new:
        md.append(md_table(new[:200]))
        if len(new) > 200:
            md.append(f"\n({len(new) - 200} more in the JSON, sorted the same way.)")
    else:
        md.append("None: every model component lies within 300 m of the catalogue. "
                  "That itself would be a diagnostic worth reporting (the model is "
                  "memorising the catalogue).")
    md.append("")
    md.append(f"## Near the catalogue (\u2264 300 m) — {len(near)} components")
    md.append("")
    if near:
        md.append("These most often refine, extend or correct catalogue geometries "
                  "(the 300 m scoring kernel treats them as the same fault).")
        md.append("")
        md.append(md_table(near[:100]))
        if len(near) > 100:
            md.append(f"\n({len(near) - 100} more in the JSON.)")
    else:
        md.append("None.")
    md.append("")
    md.append(f"## On the catalogue (\u2264 100 m) — {len(on)} components, "
              f"{sum(c['length_m'] for c in on) / 1000:,.0f} km")
    md.append("")
    md.append("Recovery of already-mapped faults; they anchor the probability "
              "surface but are not new geology. Not listed individually.")
    md.append("")
    md.append("## Caveats")
    md.append("")
    md.append("- A component is a connected blob of high-probability pixels, not a "
              "mapped line: azimuth and length are statistics of that blob, and a "
              "single physical fault can appear as several components (the model "
              "gaps over weak sections). Merging adjacent, co-linear components "
              "before field review is expected.")
    md.append("- `new_to_catalogue` does not mean `real` — it means `not in the "
              "provided labels`. The six-family agreement and the tectonic frame are "
              "the filters that separate candidates from false positives; the "
              "cross-validation evidence for both is in `data/evidence/"
              "experiments_*.json` and RESEARCH.md.")
    md.append("- No 1 m DEM could be pulled from this sandbox (egress blocked), so "
              "scarp-scale confirmation of individual candidates is pending; the "
              "topography family in the agreement count uses the provided 100 m "
              "elevation.")
    md.append("")
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md))
    print(f"[{time.time()-t0:6.1f}s] wrote {out_json} and {out_md}")
    print(f"  new={len(new)} near={len(near)} on_catalogue={len(on)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

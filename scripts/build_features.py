#!/usr/bin/env python3
"""Build the derived-feature stack for the whole official grid — streaming, tile by tile.

    python scripts/build_features.py [--tile-rows 512] [--out data/evidence/features.f32.npy]

Why streaming: the full stack is 12,279,160 px × 48 channels × 4 B ≈ 2.25 GB, and
this host has 3 GB of RAM. An earlier full-grid version of this script thrashed
against the memory limit and took ~3 minutes per channel; processing row tiles with
a halo and writing the interior keeps peak memory near 200 MB and finishes the whole
stack in a few minutes.

The halo guarantees that every filtered value written for a tile interior is
identical to the value a full-grid filter would produce: the halo is wider than the
largest filter support used here (sigma ≤ 8 px, truncate 4 → 32 px).

Nothing produced here is committed: the stack is a derived artifact, rebuilt on demand.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gems import features as F  # noqa: E402
from gems import spec  # noqa: E402
from gems.raster import sha256_file  # noqa: E402

HALO = 40  # px; > 4 * sigma_max (=32) so filtered interiors are exact


class RankTables:
    """Per-band percentile-rank lookups from scripts/build_rank_tables.py.

    rank(band, arr) maps every finite value to its midpoint percentile over
    the valid population of the official footprint. Monotone and per-pixel,
    so it cannot leak across blocked CV folds; the global distribution it
    uses is hash-pinned to the official raster (the JSON stores both sha256s).
    """

    def __init__(self, path: Path):
        payload = json.loads(path.read_text())
        self.nbins = int(payload["nbins"])
        self.features_sha256 = payload["features_sha256"]
        self.tables = payload["bands"]
        self.lut: dict[str, np.ndarray | None] = {}
        for name, t in self.tables.items():
            if t.get("degenerate") or not t.get("cdf") or t["total"] == 0:
                self.lut[name] = None
                continue
            cdf = np.asarray(t["cdf"], dtype=np.float64)
            counts = np.diff(np.concatenate([[0.0], cdf]))
            # bin midpoint: the rank a value in that bin represents
            self.lut[name] = ((cdf - 0.5 * counts) / t["total"]).astype(np.float32)

    def check_sha(self, raster_sha256: str) -> None:
        if self.features_sha256 != raster_sha256:
            raise RuntimeError(
                "rank tables were built from a different feature raster than "
                "the one being processed — re-run scripts/build_rank_tables.py")

    def rank(self, band: str, arr: np.ndarray) -> np.ndarray:
        t = self.tables.get(band)
        lut = self.lut.get(band)
        if t is None or lut is None:
            return np.full(arr.shape, np.nan, dtype=np.float32)
        bad = ~np.isfinite(arr)
        a = np.where(bad, 0.0, arr)
        span = t["vmax"] - t["vmin"]
        binidx = np.clip(
            ((a - t["vmin"]) / span * (self.nbins - 1)).astype(np.int64),
            0, self.nbins - 1)
        r = lut[binidx]
        return np.where(bad, np.nan, r)


def channel_plan() -> list[str]:
    """Baseline 48 channels FIRST, extended channels after.

    The order is load-bearing: `scripts/experiment.py` compares the baseline
    model against the extended model by slicing `channels[:48]` vs the full
    list, so the first 48 names must stay exactly as they were when the 0.1119
    blocked-CV number was produced. Anything new is appended.
    """
    names = [n for n, _ in spec.FEATURE_BANDS]
    baseline = [
        "mag_asa", "mag_tilt", "tmi_hgm_computed", "tmi_asa_computed",
        "rtp_hgm_computed", "mag_anom_hgm_computed",
        "grav_asa", "grav_tilt", "grav_hgm_computed",
        "curv_total", "curv_profile", "curv_plan", "curv_gaussian",
        "slope_computed", "slope_of_slope", "det_elev_hgm_computed",
        "lin_elev_energy_s1", "lin_elev_coherence_s1",
        "lin_elev_cos2theta_s1", "lin_elev_sin2theta_s1",
        "lin_elev_energy_s2", "lin_elev_coherence_s2",
        "lin_tmi_energy_s2", "lin_tmi_coherence_s2",
        "lin_grav_energy_s2", "lin_grav_coherence_s2",
        "x_geod_shearrate__geod_dilaterate",
        "x_cond_surf__depth_to_base_surf",
        "x_ieq_n100a15__deq_n100a15",
    ]
    # ------------------ agreement channels (appended after the 88) ---------
    # Cross-signal agreement across INDEPENDENT source families (task brief:
    # "agreement across independent signals is a stronger candidate than any
    # one layer alone"). Each family's evidence is the max of the percentile
    # ranks of its member bands (global rank tables from
    # scripts/build_rank_tables.py — a monotone per-pixel transform, so no CV
    # leakage). Families, from the official band list:
    #   mag    tmi, rtp, mag_anom, tmi_hg, tmi_vg
    #   grav   iso_grav_anom, iso_grav_anom_hg, iso_grav_anom_vg, iso_grav_anom_slope
    #   strain geod_2ndinv, geod_shearrate, geod_dilaterate
    #   seis   ieq_n100a15, deq_n100a15 (rank inverted: closer = stronger)
    #   cond   cond_surf, depth_to_base_surf
    #   topo   det_elev, det_elev_slope
    # The channels are appended (never inserted), so channels[:48] and
    # channels[:88] remain exactly the baseline/extended stacks of earlier
    # runs — the yardstick is unchanged.
    agreement = [
        "famrank_mag", "famrank_grav", "famrank_strain",
        "famrank_seis", "famrank_cond", "famrank_topo",
        "n_avail_fam", "max_famrank", "mean_famrank", "min_famrank",
        "n_agree_top10", "n_agree_top25", "n_agree_top50",
        "agree_strain_seis", "agree_strain_cond", "agree_seis_cond",
        "agree_strain_seis_cond",
    ]
    extended = []
    # multi-scale horizontal-gradient magnitude (potential-field edge mapping)
    for src in ("tmi", "rtp", "mag_anom", "iso_grav_anom", "det_elev"):
        for sigma in (1.5, 3.0, 6.0):
            extended.append(f"hgm_{src}_s{sigma:g}")
    # vertical gradients smoothed (the provided *_vg bands are single-scale)
    for src in ("tmi", "iso_grav_anom"):
        for sigma in (1.5, 3.0):
            extended.append(f"vg_{src}_s{sigma:g}")
    # analytic-signal amplitude and tilt angle at matched scales
    for src in ("tmi", "iso_grav_anom"):
        for sigma in (1.5, 3.0):
            extended.append(f"asa_{src}_s{sigma:g}")
            extended.append(f"tdr_{src}_s{sigma:g}")
    # multi-scale curvature / break-in-slope on detrended elevation
    for sigma in (1.5, 3.0):
        extended.append(f"curv_total_s{sigma:g}")
        extended.append(f"curv_plan_s{sigma:g}")
        extended.append(f"slope_of_slope_s{sigma:g}")
    # local texture (std over a Gaussian window) — heterogeneity of the field
    for src in ("tmi", "det_elev", "iso_grav_anom"):
        extended.append(f"std_{src}_s3")
    # lineament tensor on the two sources the baseline stack skipped
    extended += ["lin_cond_energy_s2", "lin_cond_coherence_s2",
                 "lin_rtp_energy_s2", "lin_rtp_coherence_s2"]
    return names + baseline + extended + agreement


def derived(bands: dict[str, np.ndarray], ranks: RankTables) -> dict[str, np.ndarray]:
    """All derived channels for one tile (any tile size; NaN-propagating)."""
    out: dict[str, np.ndarray] = {}

    hg = bands["tmi_hg"]; vg = bands["tmi_vg"]
    ghg = bands["iso_grav_anom_hg"]; gvg = bands["iso_grav_anom_vg"]
    out["mag_asa"] = np.sqrt(hg * hg + vg * vg)
    out["mag_tilt"] = F.tilt_angle(vg, np.abs(hg))
    out["grav_asa"] = np.sqrt(ghg * ghg + gvg * gvg)
    out["grav_tilt"] = F.tilt_angle(gvg, np.abs(ghg))

    for src, name in (("tmi", "tmi_hgm_computed"), ("rtp", "rtp_hgm_computed"),
                      ("mag_anom", "mag_anom_hgm_computed"),
                      ("iso_grav_anom", "grav_hgm_computed"),
                      ("det_elev", "det_elev_hgm_computed")):
        gx, gy = F.derivatives(bands[src])
        out[name] = np.sqrt(gx * gx + gy * gy)
        del gx, gy

    gx, gy = F.derivatives(bands["tmi"])
    out["tmi_asa_computed"] = np.sqrt(gx * gx + gy * gy)
    del gx, gy

    curv = F.curvature(bands["det_elev"])
    out["curv_total"] = curv.total
    out["curv_profile"] = curv.profile
    out["curv_plan"] = curv.plan
    out["curv_gaussian"] = curv.gaussian
    out["slope_computed"] = curv.slope
    out["slope_of_slope"] = curv.slope_of_slope
    del curv

    for src_name, arr, factor in (("elev", bands["det_elev"], 1),
                                  ("elev", bands["det_elev"], 2),
                                  ("tmi", bands["tmi"], 2),
                                  ("grav", bands["iso_grav_anom"], 2)):
        ds = F.downsample(arr, factor)
        t = F.structure_tensor(ds, sigma=1.0, integration_sigma=2.0 * factor)
        suffix = f"_s{factor}"
        out[f"lin_{src_name}_energy{suffix}"] = t.energy
        out[f"lin_{src_name}_coherence{suffix}"] = t.coherence
        if factor == 1:
            out[f"lin_{src_name}_cos2theta{suffix}"] = np.cos(2 * t.orientation)
            out[f"lin_{src_name}_sin2theta{suffix}"] = np.sin(2 * t.orientation)
        del t, ds

    out["x_geod_shearrate__geod_dilaterate"] = bands["geod_shearrate"] * bands["geod_dilaterate"]
    out["x_cond_surf__depth_to_base_surf"] = bands["cond_surf"] * bands["depth_to_base_surf"]
    out["x_ieq_n100a15__deq_n100a15"] = bands["ieq_n100a15"] * bands["deq_n100a15"]

    # ===================== extended channels (appended) =====================
    # Multi-scale horizontal-gradient magnitude of the potential fields and of
    # detrended elevation. HGM peaks over the edges of magnetised / dense
    # blocks, which is what a buried fault offsets. Three scales because the
    # depth to the source is unknown: shallow sources give sharp, short-
    # wavelength edges; deep basin-bounding faults give broad ones.
    for src in ("tmi", "rtp", "mag_anom", "iso_grav_anom", "det_elev"):
        for sigma in (1.5, 3.0, 6.0):
            gx, gy = F.derivatives(F.nan_gaussian(bands[src], sigma))
            out[f"hgm_{src}_s{sigma:g}"] = np.sqrt(gx * gx + gy * gy)
            del gx, gy

    # The provided vertical-gradient bands are single-scale and noisy; smoothed
    # copies let the model use them at more than one wavelength, and the
    # analytic-signal amplitude / tilt angle are then recomputed at matched
    # scales (tilt = atan2(VDR, THDR), Miller & Singh 1994 — zero crossings
    # locate the edge and the amplitude is dimensionless).
    for src, vg_band in (("tmi", "tmi_vg"), ("iso_grav_anom", "iso_grav_anom_vg")):
        for sigma in (1.5, 3.0):
            smooth = F.nan_gaussian(bands[src], sigma)
            gx, gy = F.derivatives(smooth)
            hgm = np.sqrt(gx * gx + gy * gy)
            del gx, gy, smooth
            vg = F.nan_gaussian(bands[vg_band], sigma)
            out[f"vg_{src}_s{sigma:g}"] = vg
            out[f"asa_{src}_s{sigma:g}"] = np.sqrt(hgm * hgm + vg * vg)
            out[f"tdr_{src}_s{sigma:g}"] = F.tilt_angle(vg, np.abs(hgm))
            del hgm, vg

    # Scale-explicit curvature and break-in-slope on detrended elevation.
    for sigma in (1.5, 3.0):
        c = F.curvature_at_scale(bands["det_elev"], sigma)
        out[f"curv_total_s{sigma:g}"] = c.total
        out[f"curv_plan_s{sigma:g}"] = c.plan
        out[f"slope_of_slope_s{sigma:g}"] = c.slope_of_slope
        del c

    for src in ("tmi", "det_elev", "iso_grav_anom"):
        out[f"std_{src}_s3"] = F.local_std(bands[src], 3.0)

    for src_name, src in (("cond", bands["cond_surf"]), ("rtp", bands["rtp"])):
        ds = F.downsample(src, 2)
        t = F.structure_tensor(ds, sigma=1.0, integration_sigma=4.0)
        out[f"lin_{src_name}_energy_s2"] = t.energy
        out[f"lin_{src_name}_coherence_s2"] = t.coherence
        del t, ds

    # ===================== agreement channels (appended) =====================
    # Family evidence = max of the (inverted where appropriate) percentile
    # ranks of the family's member bands. NaN where every member is invalid.
    fams: dict[str, tuple[str, ...]] = {
        "mag": ("tmi", "rtp", "mag_anom", "tmi_hg", "tmi_vg"),
        "grav": ("iso_grav_anom", "iso_grav_anom_hg", "iso_grav_anom_vg",
                 "iso_grav_anom_slope"),
        "strain": ("geod_2ndinv", "geod_shearrate", "geod_dilaterate"),
        "seis": ("ieq_n100a15", "deq_n100a15"),
        "cond": ("cond_surf", "depth_to_base_surf"),
        "topo": ("det_elev", "det_elev_slope"),
    }
    famrank: dict[str, np.ndarray] = {}
    shape = bands["tmi"].shape
    for fam, members in fams.items():
        acc = np.full(shape, -1.0, dtype=np.float32)
        for mb in members:
            r = ranks.rank(mb, bands[mb])
            if mb == "deq_n100a15":
                r = np.where(np.isfinite(r), 1.0 - r, r)  # closer = more seismic
            acc = np.fmax(acc, r)  # fmax ignores NaN: -1 stays if all invalid
        famrank[fam] = np.where(acc >= 0.0, acc, np.nan).astype(np.float32)
        out[f"famrank_{fam}"] = famrank[fam]

    n_avail = np.zeros(shape, dtype=np.float32)
    sumv = np.zeros(shape, dtype=np.float32)
    maxv = np.full(shape, -1.0, dtype=np.float32)
    minv = np.full(shape, np.inf, dtype=np.float32)
    for fam in fams:
        f = famrank[fam]
        fin = np.isfinite(f)
        n_avail += fin.astype(np.float32)
        sumv = np.where(fin, sumv + f, sumv)
        maxv = np.fmax(maxv, f)
        minv = np.fmin(minv, f)
    out["n_avail_fam"] = n_avail
    out["max_famrank"] = np.where(maxv >= 0.0, maxv, np.nan).astype(np.float32)
    out["min_famrank"] = np.where(np.isfinite(minv), minv, np.nan).astype(np.float32)
    out["mean_famrank"] = np.where(n_avail > 0, sumv / np.maximum(n_avail, 1.0),
                                   np.nan).astype(np.float32)

    for thr_name, thr in (("top10", 0.90), ("top25", 0.75), ("top50", 0.50)):
        # count of AVAILABLE families whose evidence is in the top thr share;
        # an unavailable family (NaN) is simply not counted
        cnt = np.zeros(shape, dtype=np.float32)
        for fam in fams:
            cnt += (famrank[fam] >= thr).astype(np.float32)
        out[f"n_agree_{thr_name}"] = cnt

    # The brief's named cross-references: strain rate x seismicity,
    # strain rate x conductivity, seismicity x conductivity, and all three.
    # Products of ranks: high only where every factor is elevated.
    pairs = (("strain_seis", ("strain", "seis")),
             ("strain_cond", ("strain", "cond")),
             ("seis_cond", ("seis", "cond")),
             ("strain_seis_cond", ("strain", "seis", "cond")))
    for name, factors in pairs:
        prod = np.ones(shape, dtype=np.float32)
        for fam in factors:
            prod = prod * famrank[fam]  # NaN propagates if any factor missing
        out[f"agree_{name}"] = prod

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=str(REPO_ROOT / "data" / "training_features.tif"))
    ap.add_argument("--out", default=str(REPO_ROOT / "data" / "evidence" / "features.f32.npy"))
    ap.add_argument("--tile-rows", type=int, default=512)
    args = ap.parse_args()

    t0 = time.time()
    channels = channel_plan()
    names = [n for n, _ in spec.FEATURE_BANDS]

    rank_path = REPO_ROOT / "data" / "evidence" / "rank_tables.json"
    if not rank_path.exists():
        print("rank tables missing — run scripts/build_rank_tables.py first "
              "(needed by the agreement channels)", file=sys.stderr)
        return 1
    ranks = RankTables(rank_path)

    mm = np.lib.format.open_memmap(args.out, mode="w+", dtype=np.float32,
                                   shape=(spec.HEIGHT, spec.WIDTH, len(channels)))
    mm[:] = np.nan
    idx = {n: i for i, n in enumerate(channels)}
    invalid = np.zeros((spec.HEIGHT, spec.WIDTH), dtype=bool)

    done_positives = np.zeros(spec.HEIGHT, dtype=bool)
    with rasterio.open(args.features) as src:
        # the rank tables must have been built from THIS raster (sha256 pin)
        ranks.check_sha(sha256_file(args.features))
        for r0 in range(0, spec.HEIGHT, args.tile_rows):
            r1 = min(r0 + args.tile_rows, spec.HEIGHT)
            w0 = max(0, r0 - HALO)
            w1 = min(spec.HEIGHT, r1 + HALO)
            window = rasterio.windows.Window(0, w0, spec.WIDTH, w1 - w0)
            bands: dict[str, np.ndarray] = {}
            bad_any = np.zeros((w1 - w0, spec.WIDTH), dtype=bool)
            for n in names:
                a = src.read(spec.BAND_INDEX[n], window=window).astype(np.float32)
                bad = a < spec.FEATURE_INVALID_BELOW
                bands[n] = np.where(bad, np.nan, a)
                bad_any |= bad
            invalid[w0:w1] |= bad_any

            for n in names:  # passthrough
                mm[w0:w1, :, idx[n]] = bands[n]

            der = derived(bands, ranks)

            lo = r0 - w0
            hi = lo + (r1 - r0)
            for n, arr in der.items():
                a = np.asarray(arr, dtype=np.float32)
                if a.shape != bands["tmi"].shape:
                    # downsampled products: upsample by nearest neighbour to tile size
                    fy = a.shape[0] and bands["tmi"].shape[0] // a.shape[0]
                    fx = a.shape[1] and bands["tmi"].shape[1] // a.shape[1]
                    if fy and fx:
                        a = np.repeat(np.repeat(a, fy, axis=0), fx, axis=1)
                    a = a[: bands["tmi"].shape[0], : bands["tmi"].shape[1]]
                    pad_r = bands["tmi"].shape[0] - a.shape[0]
                    pad_c = bands["tmi"].shape[1] - a.shape[1]
                    if pad_r or pad_c:
                        a = np.pad(a, ((0, pad_r), (0, pad_c)), constant_values=np.nan)
                mm[r0:r1, :, idx[n]] = a[lo:hi, :]
            done_positives[r0:r1] = True
            print(f"[{time.time()-t0:6.1f}s] rows {r0}-{r1} done "
                  f"({cum_pct(r0, r1, spec.HEIGHT):.0f}%)", flush=True)

    mm.flush()
    np.save(REPO_ROOT / "data" / "evidence" / "_invalid_allband.npy", invalid)
    meta = {
        "path": args.out, "shape": list(mm.shape), "channels": channels,
        "invalid_pixels": int(invalid.sum()),
        "valid_all_band_pixels": int((~invalid).sum()),
        "tile_rows": args.tile_rows, "halo": HALO,
        "rank_tables_sha256": sha256_file(rank_path),
        "features_sha256": ranks.features_sha256,
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "build_seconds": round(time.time() - t0, 1),
    }
    (REPO_ROOT / "data" / "evidence" / "features_meta.json").write_text(
        json.dumps(meta, indent=2) + "\n")
    print(json.dumps({k: v for k, v in meta.items() if k != "channels"}, indent=2))
    return 0


def cum_pct(r0: int, r1: int, height: int) -> float:
    return (r1 / height) * 100.0


if __name__ == "__main__":
    raise SystemExit(main())

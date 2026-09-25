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

HALO = 40  # px; > 4 * sigma_max (=32) so filtered interiors are exact


def channel_plan() -> list[str]:
    names = [n for n, _ in spec.FEATURE_BANDS]
    return names + [
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


def derived(bands: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
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

    mm = np.lib.format.open_memmap(args.out, mode="w+", dtype=np.float32,
                                   shape=(spec.HEIGHT, spec.WIDTH, len(channels)))
    mm[:] = np.nan
    idx = {n: i for i, n in enumerate(channels)}
    invalid = np.zeros((spec.HEIGHT, spec.WIDTH), dtype=bool)

    done_positives = np.zeros(spec.HEIGHT, dtype=bool)
    with rasterio.open(args.features) as src:
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

            der = derived(bands)

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

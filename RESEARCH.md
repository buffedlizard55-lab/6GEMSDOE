# Research — the science behind the solution, with every source verified

Every source below was **fetched or resolved on 2026-09-25 (UTC) in this session** —
not copied from memory. For each entry: what it is, the link for manual review, and
what was actually checked. Where a citation in the earlier version of this project
was found to be **wrong, the correction is recorded in §7** rather than silently
fixed. That list is the reason this file exists.

## 1. Official competition sources (re-verified this session)

| Source | What was verified | Link |
|---|---|---|
| Competition home | end date Dec. 3 2026 11:59 UTC; $300k total; $50k initial (top 5 × $10k); $250k final ($100k/$70k/$40k/$25k/$15k); "same submission scored twice"; eligibility; "use of test data" (spatial overlap between training and test faults; provided faults may be used for training); external data encouraged | <https://www.drivendata.org/competitions/306/competition-doe-gems/> |
| Problem description (page 967) | metric formula (TI, triangular kernel k(d)=(1−d/R)₊, R=300 m=3 px, α=0.2 β=0.8, DTI=TP_w/(TP_w+α·FP_w+β·FN_w+ε)); worked example 3.00/(3.00+0.2·1.89+0.8·2.00)=0.60; submission format (EPSG:32611, 100 m, same bounds, single float32 layer, values in [0,1], null/NaN outside bounds); public+private test split with public shown on leaderboard | <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> |
| About page (968) | sponsor (DOE Office of Geothermal + NLR); GeoDAWN = USGS/DOE airborne magnetic + radiometric under EarthMRI, with coordinated 3DEP lidar; Walker Lane + western Great Basin context; the two deep-learning references the organisers cite (Mattéo 2021; Hermant 2025) | <https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/> |
| Data tab | login wall: unauthenticated request redirects to `/accounts/login/` (re-verified this session; no automated download possible without credentials, and none are used) | <https://www.drivendata.org/competitions/306/competition-doe-gems/data/> |
| Official rules PDF | title "GEMS Prize Official Rules, September 2026"; §1.1 (two phases, same submission, up to 10 awards); §1.3 (eligibility in full: U.S. citizen/PR; team captain rule; Federal employees ineligible; under-18; MFTRP; debarred); §2 (GeoDAWN doi:10.5066/P93LGLVQ; 1 m DEM; labels from USGS QFFD + NLR/USGS experts); §3.2 (three submissions per week; generative-AI disclosure; finalist code assets + DrivenData Winning Model Documentation Template; public leaderboard "may not be the same as the final scores on the private leaderboard"); §3.3 (label provenance: INGENIOUS, Ayling et al. 2022 doi:10.15121/1881483); §3.4 ("up to three per week"; "Multiple finalized submissions are not allowed"); §3.5 ("choose only one submission for evaluation across both prize rounds"); §3.6.1/§3.6.2 (public-test score shown; final choice made "without knowledge of your scores on the private test set"); A.2 (ACH + W-9 within 30 days); A.3 (single award to designated primary submitter); A.12 (due diligence; foreign-interference risk review; elimination "not appealable"); A.16 (return of funds for fraudulent or inaccurate information) | <https://www.nlr.gov/docs/fy26osti/96647.pdf> (redirects to docs.nlr.gov) |
| Reference solution | notebook inventories: U-Net (`segmentation_models_pytorch`), ResNet-18 encoder, Tversky **loss** (not the competition metric), Monte-Carlo **random patch splits** (not blocked folds), `X[X < -1e38] = np.nan` sentinel masking — consistent with our byte-level measurements | <https://github.com/drivendataorg/gems-prize-reference-solution> |

## 2. What the science says about detecting faults in these layers

The provided 19 bands (see `DATA.md` for the band table, read from the file's own
TIFF tags) fall into five independent physical families. Faults appear in each
family by a **different mechanism**, which is exactly why cross-family agreement
is a meaningful test (task brief research priority 3):

1. **Magnetics** (`tmi`, `rtp`, `mag_anom`, `tmi_hg`, `tmi_vg`). A fault that
   offsets magnetized layers creates a contrast in magnetization; the anomaly
   peaks and its *edge* (horizontal gradient, analytic signal, tilt) sit over the
   contact. Standard operators, all peer-reviewed and cited by the organisers'
   own research lineage: analytic-signal amplitude (Nabighian 1972; Roest et al.
   1992), tilt angle (Miller & Singh 1994), total horizontal derivative
   (Verduzco et al. 2004), theta map / NTHD (Wijns et al. 2005). Implemented in
   `src/gems/features.py` (single and multi-scale: σ = 1.5/3/6 px).
2. **Gravity** (`iso_grav_anom` + its provided derivatives). Same physics for
   density contrasts; basin-bounding and reverse faults offset basement —
   broad, long-wavelength edges, hence the multi-scale treatment.
3. **Geodetic strain** (`geod_2ndinv`, `geod_shearrate`, `geod_dilaterate`).
   Active faulting loads the elastic crust; contemporary strain-rate tensors
   (GPS/InSAR-derived) peak along the active fault zone. In the Walker Lane the
   measured strain field is extensional N88°E at ~30 nstrain/yr with right-lateral
   shear on a N35°W-striking zone (Hreinsdóttir et al., western Nevada 1993–2000,
   §6 below) — so strain-rate alignment with NW-trending traces is physically
   expected, not a coincidence.
4. **Seismicity** (`ieq_n100a15` density, `deq_n100a15` distance). Earthquakes
   nucleate on faults; quaternary-active fault segments concentrate seismicity.
   The bands are kernel-smoothed (n=100 km, a=15°) per the file's own metadata.
5. **Conductivity** (`cond_surf`, `depth_to_base_surf`) and **topography**
   (`det_elev`, `det_elev_slope`, `depth_to_base_surf` in our family split).
   Hydrothermal systems along faults produce near-surface conductive
   alteration (MT/EM surveys in the region — Dixie Valley, Steamboat — show
   resistivity structures dominated by high-angle features along fault zones);
   fault scarps are breaks in slope that curvature and slope-of-slope isolate
   (Zevenbergen & Thorne 1987; Moore et al. 1991).

The agreement channels in `scripts/build_features.py` (the 17 channels after the
88) encode this: each family's evidence is the max of its members' **global
percentile ranks** (monotone, per-pixel, hence leak-free), and the channels count
how many independent families are simultaneously elevated. A pixel where
magnetics, gravity, strain, seismicity and topography all rank high is a
stronger candidate than the same pixel high in one family only — and a false
positive must be wrong about five independent physical mechanisms at once.

## 3. Deep-learning fault mapping — the prior art the organisers cite

| Reference | Verified as | Link |
|---|---|---|
| Mattéo, L., Manighetti, I., Tarabalka, Y., et al. (2021). *Automatic fault mapping in remote optical images and topographic data with deep learning.* JGR: Solid Earth 126, e2020JB021269. | U-Net ("MRef") for fracture/fault mapping in optical + topographic data; trained on modest data, generalises to unseen image types. Cited by the About page. | <https://doi.org/10.1029/2020JB021269> |
| Hermant, B., Kiersnowski, L., Bellanger, M. (2025). *Using deep learning to map Quaternary faults in Western USA.* 50th Stanford Geothermal Workshop, Feb 10–12 2025 (SGP-TR-229). | CNNs ("siUNET", "FaultSEG") detecting faults on remote-sensing/satellite data, trained on expert-mapped labels in central northern Nevada; goal: complete the USGS Quaternary Faults database — i.e. the same task family as this competition. Cited by the About page. | <https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Hermant.pdf> |

Both are optical/topography-driven. Our data adds the potential-field, strain,
seismicity and conductivity layers those papers do not use — the cross-family
agreement above is our analogue of their multi-sensor fusion.

## 4. Classical operators implemented in `src/gems/features.py`

| Operator | Reference (verified) | Link |
|---|---|---|
| Analytic signal of 2-D magnetic bodies | Nabighian, M. N. (1972). *The analytic signal of two-dimensional magnetic bodies with polygonal cross-section: Its properties and use for automated anomaly interpretation.* Geophysics 37(3), 507–517. | <https://doi.org/10.1190/1.1440276> |
| 3-D analytic signal amplitude (maxima over source edges) | Roest, W. R., Verhoef, J., Pilkington, M. (1992). *Magnetic interpretation using the 3-D analytic signal.* Geophysics 57(1), 116–125. | <https://doi.org/10.1190/1.1443174> |
| Tilt angle T = atan2(VDR, THDR) | Miller, H. G., Singh, V. (1994). *Potential field tilt — a new concept for location of potential field sources.* **Journal of Applied Geophysics 32(2–3), 213–217.** *(earlier version of this project cited it as Geophysics 62(1) with a DOI that actually belongs to an unrelated 1997 paper — corrected, see §7)* | <https://doi.org/10.1016/0926-9851(94)90022-1> |
| Total horizontal derivative for structural mapping | Verduzco, B., Fairhead, J. D., Green, C. M., MacKenzie, C. (2004). *New insights into magnetic derivatives for structural mapping.* The Leading Edge 23(2), 116–119. | <https://doi.org/10.1190/1.1651454> |
| Theta map / normalized total horizontal derivative | Wijns, C., Perez, C., Kowalczyk, P. (2005). *Theta map: edge detection in magnetic data.* Geophysics 70(4), L39–L43. | <https://doi.org/10.1190/1.1988184> |
| Structure tensor / local orientation for lineaments | Bigun, J., Granlund, G. H. (1987). *Optimal orientation detection of linear symmetry.* Proc. First International Conference on Computer Vision, London, June 1987, pp. 433–438. *(the DOI formerly attached here belonged to an unrelated 1987 point-registration paper — corrected, see §7)* | <https://ieeexplore.ieee.org/document/676600> (conference record; cite the proceedings, not the DOI) |
| Coherence-enhancing filtering (structure-tensor integration) | Weickert, J. (1998). *Coherence-based filtering of images and signals.* Image and Vision Computing 16(11), 827–832. | <https://doi.org/10.1016/S0262-8856(98)00111-6> |
| Terrain curvature (profile/plan) from gridded elevation | Zevenbergen, L. W., Thorne, C. R. (1987). *Quantitative analysis of land surface topography.* Earth Surface Processes and Landforms 12(1), 47–56. *(the DOI formerly attached here belonged to an unrelated 1992 geostatistics paper — corrected, see §7)* | <https://doi.org/10.1002/esp.3290120107> |
| Terrain attribute definitions review | Moore, I. D., Grayson, R. B., Ladson, A. R. (1991). *Digital terrain modelling: A review of hydrological, geomorphological, and biological applications.* Hydrological Processes 5(1), 3–30. | <https://doi.org/10.1002/hyp.3360050103> |

## 5. The metric and its training-loss relative

| Reference | Verified as | Link |
|---|---|---|
| Tversky, A. (1977). *Features of similarity.* Psychological Review 84(4), 327–352. | The original Tversky index — the family this competition's metric belongs to. | <https://doi.org/10.1037/0033-295X.84.4.327> |
| Salehi, S. S. M., Erdogmus, D., Gholipour, A. (2017). *Tversky loss function for image segmentation using 3D fully convolutional deep networks.* MLMI Workshop, MICCAI, pp. 379–387, Springer. | The Tversky **loss** used by the reference solution (training objective only — it is *not* the competition's distance-weighted metric; the metric is implemented from the published formula in `src/gems/metric.py` and unit-tested against the page's worked example). | <https://doi.org/10.1007/978-3-319-66183-8_28> |

## 6. Regional tectonics — the frame for the Phase-2 geological narrative

Phase 2 ($250k) is judged by geologists reviewing what we flagged, so every
high-confidence candidate in `docs/CANDIDATES.md` (generated by
`scripts/candidate_writeup.py`) records its trend against this frame:

| Reference | Verified content | Link |
|---|---|---|
| Wesnousky, G. J. et al. (2005). *Active faulting in the Walker Lane.* Tectonics 24(4), doi:10.1029/2004TC001645. | NW-directed strike-slip in the central Walker Lane transfers into NW-directed extension and N-S–trending normal faulting in the Basin and Range; complex, partly detached, rotating blocks; range-bounding normal faults with strike-slip components. | <https://doi.org/10.1029/2004TC001645> |
| Hreinsdóttir, A. et al. *Strain accumulation and rotation in western Nevada, 1993–2000.* (USGS). | Walker Lane belt: extension ~29.6 nstrain/yr on N88°E, clockwise rotation, right-lateral simple shear ~19.5 nstrain/yr across an N35°W-striking zone. | <https://www.usgs.gov/publications/strain-accumulation-and-rotation-western-nevada-1993-2000> |
| Pollitz, F. F., Vergnolle, M. (2006). *Mechanical deformation model of the western United States instantaneous strain-rate field.* Geophysical Journal International 167, doi:10.1111/j.1365-246X.2006.03019.x. | Plate-scale strain-rate model from 746 GPS vectors; the family of the provided `geod_*` bands. | <https://doi.org/10.1111/j.1365-246X.2006.03019.x> |
| USGS Quaternary Fault and Fold Database | live national database of Quaternary faults/folds (the label provenance per rules §2/§3.3), GIS shapefiles downloadable. | <https://earthquake.usgs.gov/hazards/qfaults/> |

## 7. Corrections made this session (hallucination audit)

The literature table in the earlier site carried three citations whose **DOIs or
journal data pointed at different papers**. Each was re-resolved this session:

| Was | Is |
|---|---|
| Miller & Singh 1994, "Geophysics 62(1)", doi:10.1190/1.1444129 | doi:10.1190/1.1444129 is **Duren & Trantham 1997** (Q dispersion). Correct: *Journal of Applied Geophysics* 32(2–3):213–217, <https://doi.org/10.1016/0926-9851(94)90022-1> |
| Zevenbergen & Thorne 1987, "Math. Geol. 19(2)", doi:10.1007/BF00893750 | doi:10.1007/BF00893750 is **Goulard & Voltz 1992** (coregionalization). Correct: *Earth Surf. Process. Landforms* 12(1):47–56, <https://doi.org/10.1002/esp.3290120107> |
| Bigun & Granlund 1987, doi:10.1109/TPAMI.1987.4767965 | doi:10.1109/TPAMI.1987.4767965 is **Arun, Huang & Blostein 1987** (3-D point registration). Correct: ICCV 1987 proceedings paper (no DOI); conference record at <https://ieeexplore.ieee.org/document/676600> |

Also corrected: Verduzco et al. 2004's title ("New insights into magnetic
derivatives for structural mapping" — the earlier line paraphrased it as
"Total horizontal derivative of the tilt angle as an edge detector") and
Roest et al. 1992's title ("Magnetic interpretation using the 3-D analytic
signal").

## 8. External data — free, public, and how each is (or is not) used

| Source | What it gives | Link | Status in this project |
|---|---|---|---|
| GeoDAWN airborne magnetic + radiometric | the 19-band feature backbone | <https://doi.org/10.5066/P93LGLVQ> (ScienceBase: <https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7>) | **Used** — the official `training_features.tif`, sha256-pinned |
| INGENIOUS Great Basin Regional Dataset Compilation | the label provenance | <https://doi.org/10.15121/1881483> (GDR: <https://gdr.openei.org/submissions/1391>) | **Used** — the official `labels.tif` (per rules §3.3) |
| USGS 3DEP 1 m DEM tiles | scarp-scale topography | bucket listing <https://prd-tnm.s3.amazonaws.com/index.html?prefix=StagedProducts/Elevation/1m/Projects/>; newer seamless 1 m collection: <https://doi.org/10.5066/P13LJKFS> | **Not yet used** — the competition ships it as an OCR-derived link list; tiles are terabytes of ~100 MB objects and this sandbox's egress to the bucket is blocked (verified 2026-09-25). Needs an unrestricted host. The seamless collection (doi above) is the cleaner authoritative source to re-derive the tile list from. |
| USGS Quaternary Fault and Fold Database | independent fault catalogue for cross-checking candidates | <https://earthquake.usgs.gov/hazards/qfaults/> | Available; the provided labels already descend from it + INGENIOUS |
| NEIC ComCat earthquake catalog | seismicity (free API, JSON/GeoJSON) | <https://earthquake.usgs.gov/earthquakes/feed/v1.0/>, API <https://earthquake.usgs.gov/fdsnws/event/1/> | Available for independent cross-checks; the provided `ieq/deq` bands already encode smoothed seismicity |
| USGS GPS/InSAR strain-rate products | independent strain context | <https://www.usgs.gov/publications/strain-accumulation-and-rotation-western-nevada-1993-2000> (see §6) | Context for the narrative; the provided `geod_*` bands encode the strain field |
| MT/ZTEM/AFMAG conductivity surveys (Dixie Valley, Steamboat, Gold Springs) | conductivity context for fault-zone alteration | e.g. <https://www.earthdoc.org/content/journals/10.1071/ASEG2012ab318> | Context only; the provided `cond_surf` band is the in-grid signal |

## 9. What the evidence says about design choices (measured, not asserted)

1. **Writing 1.0 beats writing the probability** — algebra (`β·n_gt` does not
   scale with p) plus measurement: 0.1119 → 0.1520–0.1668 on the same folds.
2. **Control the budget, not the threshold** — the score depends on
   predicted-pixel count vs the unknown test-set size; 3% is the minimax-regret
   budget on two independent blockings (tables in `EXECUTIVE_SUMMARY.md`).
3. **4–5 px thinning loses** — measured as the worst non-trivial strategy
   (0.0621) vs 0.1119 for the un-thinned threshold placement; the 300 m kernel
   is a tolerance, not a spacing instruction. The metric-aware step that is kept
   is the *budget* control (top-k with exact budget, and now the
   agreement-gated variant `gated_topk` in `src/gems/placement.py`).
4. **The catalogue is the wrong target** — both rounds score faults missing from
   it. Countermeasures measured in `data/evidence/experiments_*.json`:
   trace-thinned ground truth, whole-trace holdout from training (rediscovery
   diagnostic), PU-style inverse-trace-length re-weighting, and the cross-family
   agreement channels/gate.
5. **Cross-family agreement, measured** (`data/evidence/experiments_agreement.json`,
   identical 4×4 blocked folds, 400k negatives, 300 iterations): the 17 appended
   agreement channels (105-channel model) score 0.1670 vs 0.1698 (88ch) and 0.1706
   vs 0.1750 (88ch) at 3% and 5% budgets on the full catalogue — not a win on the
   shipping axis. On the hard simulation (whole fault traces removed from the
   ground truth) they move the other way: 0.1307 vs 0.1292 at a 2% budget, 0.1159
   vs 0.1184 at 5%. Conclusion: the model's own probability already captures most
   of the cross-family signal on this grid (the HGB sees the raw bands and can form
   the same conjunctions internally); the explicit ranks add robustness against
   trace deletion but not full-catalogue precision. The agreement-gated placement
   (`topk_gate@<frac>` in `src/gems/placement.py`) is decisively worse — 0.112–0.116
   in every configuration — because the gate spends the budget on a stricter set
   that excludes catalogue faults the model already scores well. Both results are
   kept in the record; the shipped 88-channel, ungated file stands.
6. **PU-style re-weighting of the positive class, measured**
   (`data/evidence/experiments_itrace.json`): weighting catalogue fault pixels by
   1/√(trace length) (long, thoroughly mapped traces down-weighted, so the model
   should lean on short, less-mapped ones — closer to the private set) **lowers**
   the score on every axis: 0.1650 (88ch) and 0.1631 (105ch) at a 3% budget vs
   0.1698 / 0.1670 unweighted; keep0.5 and keep0.25 columns fall too. The physics
   explains it: the long, well-mapped traces are not *less like* the private faults,
   they are *cleaner examples* of the same physical mechanisms (the same edge
   signatures in the same five families), and de-emphasising the clearest positives
   degrades the anchor of the probability surface. The correct lever for "the
   private set is unmapped faults" is therefore at the feature/target level
   (semi-supervised positives, whole-system holdout), not at the class-weight level.
   (One implementation trap worth recording: `HistGradientBoostingClassifier` with
   `sample_weight` containing zeros silently drops those samples from the fit — the
   weight surface must be 1.0 on the background, not 0.0. The first run of this
   experiment had that bug; the numbers above are from the corrected weights.)

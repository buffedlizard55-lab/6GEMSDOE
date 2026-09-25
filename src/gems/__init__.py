"""gems — GEMS Prize (DrivenData/DOE) fault-prediction toolkit.

Single-purpose package backing the one canonical competition repo:
  * metric.py     — distance-weighted Tversky index, implemented from the
                    published formula on the competition problem-description page.
  * raster.py     — submission IO + the hard format gate (NaN-inside-footprint).
  * features.py   — derived structural features (edges/curvature/lineaments).
  * placement.py  — metric-aware prediction placement.
  * cv.py         — spatially-blocked, buffered cross-validation.
  * spec.py       — pinned grid/format constants measured from the official files.

Every constant in this package is either (a) quoted from an official source with a
URL, or (b) measured from the official bytes and pinned with a sha256. Nothing is
assumed.
"""

__all__ = ["metric", "raster", "spec", "features", "placement", "cv"]
__version__ = "1.0.0"

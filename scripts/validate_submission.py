#!/usr/bin/env python3
"""HARD GATE: refuse to offer a submission file that the platform would reject.

Run before any file is offered for download or uploaded:

    python scripts/validate_submission.py <file.tif> [--json out.json]

Exit code 0 = pass, 1 = fail. It never "warns and continues" on the gate that
matters. The specific failure the task brief describes,

    "Predicted values must be in range [0, 1]"

is produced by the platform when a NaN sits INSIDE the scored footprint — the
finite values are all in range, but the range check trips on the NaN. The check
`NAN-INSIDE-FOOTPRINT` in src/gems/raster.py is therefore hard-coded as fatal
here, and the footprint it compares against is the official sample submission's
non-NaN mask, verified by sha256 before use.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gems import raster  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="submission GeoTIFF to validate")
    ap.add_argument("--template", default=None,
                    help="official sample submission (default data/sample_submission.tif)")
    ap.add_argument("--json", default=None, help="write the report as JSON here")
    ap.add_argument("--allow-footprint-subset", action="store_true",
                    help="relax only the 'no finite pixel outside the footprint' "
                         "rule (experiments; never for the file we upload)")
    args = ap.parse_args()

    rep = raster.check_submission(
        args.path, template=args.template,
        expect_footprint=not args.allow_footprint_subset)
    print(rep.text())
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rep.as_dict(), indent=2) + "\n")
    if not rep.ok:
        print("\nHARD GATE FAILED — do NOT upload this file.", file=sys.stderr)
        return 1
    print("\nHARD GATE PASSED — this file satisfies the published format rules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

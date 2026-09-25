"""The metric must match the published formula exactly.

Reference: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
section "Scoring example":
    TP_w = 3.00, FP_w = 1.89, FN_w = 2.00
    TI_w(a=0.2, b=0.8) = 3.00 / (3.00 + 0.2*1.89 + 0.8*2.00) = 0.60
"""

import numpy as np
import pytest

from gems import metric


def _grid():
    return np.zeros((9, 9), dtype=np.float32)


def test_official_worked_example_arithmetic():
    tp, fp, fn = 3.00, 1.89, 2.00
    value = tp / (tp + metric.ALPHA * fp + metric.BETA * fn)
    assert value == pytest.approx(0.6026516673, abs=1e-9)
    assert round(value, 2) == 0.60  # exactly what the page prints


def test_kernel_discrete_values_match_the_100m_grid():
    _, _, k = metric.kernel_offsets()
    got = sorted(set(np.round(k, 6)), reverse=True)
    for expected in (1.0, 2 / 3, 0.528595, 1 / 3, 0.254644, 0.057191, 0.0):
        assert any(abs(g - expected) < 1e-6 for g in got), (expected, got)


def test_radius_is_exactly_three_pixels():
    assert metric.RADIUS_PX == 3.0
    assert metric.RADIUS_M == 300.0
    assert metric.PIXEL_SIZE_M == 100.0


def test_perfect_prediction_scores_one():
    g = _grid()
    g[4, 4] = 1
    c = metric.components(g.copy(), g)
    assert c.dti == pytest.approx(1.0)
    assert (c.tp_w, c.fp_w, c.fn_w) == (1.0, 0.0, 0.0)


def test_empty_prediction_scores_zero():
    g = _grid()
    g[4, 4] = 1
    c = metric.components(_grid(), g)
    assert c.dti == 0.0
    assert c.fn_w == pytest.approx(1.0)


def test_hand_computable_one_pixel_offset():
    """One GT pixel, one prediction 1 px right of it (d = 1 px, k = 2/3).

    TP_w = 2/3, FN_w = 1/3, FP_w = p*(1-k) = 1/3
    DTI  = (2/3) / ((2/3) + 0.2*(1/3) + 0.8*(1/3)) = 2/3
    """
    g = _grid()
    g[4, 4] = 1
    p = _grid()
    p[4, 5] = 1
    c = metric.components(p, g)
    assert c.tp_w == pytest.approx(2 / 3)
    assert c.fn_w == pytest.approx(1 / 3)
    assert c.fp_w == pytest.approx(1 / 3)
    assert c.dti == pytest.approx(2 / 3)


def test_two_pixel_offset_uses_diagonal_kernel_value():
    """Distance sqrt(5) px gives k = 1 - sqrt(5)/3 = 0.254644."""
    g = _grid()
    g[4, 4] = 1
    p = _grid()
    p[6, 5] = 1  # dy=2, dx=1 -> sqrt(5)
    c = metric.components(p, g)
    assert c.tp_w == pytest.approx(1 - np.sqrt(5) / 3)
    assert c.fn_w == pytest.approx(np.sqrt(5) / 3)


def test_beyond_radius_contributes_nothing_to_tp():
    g = _grid()
    g[4, 4] = 1
    p = _grid()
    p[4, 8] = 1  # 4 px away > R
    c = metric.components(p, g)
    assert c.tp_w == 0.0
    assert c.fn_w == pytest.approx(1.0)
    assert c.fp_w == pytest.approx(1.0)  # k(d)=0 there, so the full penalty applies


def test_no_ground_truth_is_not_a_nan_score():
    c = metric.components(np.zeros((5, 5)), np.zeros((5, 5)))
    assert c.dti == 0.0 and not np.isnan(c.dti)


def test_empty_prediction_over_empty_gt_is_not_nan():
    c = metric.components(np.zeros((5, 5)), np.zeros((5, 5)))
    assert np.isfinite(c.dti)


def test_probability_weights_are_linear_in_tp():
    g = _grid()
    g[4, 4] = 1
    p = _grid()
    p[4, 4] = 0.5
    c = metric.components(p, g)
    assert c.tp_w == pytest.approx(0.5)
    assert c.fn_w == pytest.approx(0.5)
    assert c.fp_w == pytest.approx(0.0)  # k=1 at d=0 removes the FP penalty


def test_all_ones_matches_brute_force_definition():
    """Brute-force check of the published sums on a small grid."""
    rng = np.random.default_rng(0)
    g = (rng.random((11, 11)) > 0.8)
    p = rng.random((11, 11)).astype(np.float64)
    c = metric.components(p, g)
    R = 3.0
    gs = np.argwhere(g)
    tp = fp = fn = 0.0
    for gy, gx in gs:
        best = 0.0
        for py in range(11):
            for px in range(11):
                d = np.hypot(py - gy, px - gx)
                if d <= R:
                    best = max(best, p[py, px] * max(1 - d / R, 0.0))
        tp += best
        fn += 1 - best
    for py in range(11):
        for px in range(11):
            if p[py, px] <= 0:
                continue
            dmin = min((np.hypot(py - gy, px - gx) for gy, gx in gs), default=np.inf)
            k = max(1 - dmin / R, 0.0) if np.isfinite(dmin) else 0.0
            fp += p[py, px] * (1 - k)
    assert c.tp_w == pytest.approx(tp, rel=1e-9)
    assert c.fn_w == pytest.approx(fn, rel=1e-9)
    assert c.fp_w == pytest.approx(fp, rel=1e-9)


def test_analytic_everywhere_matches_closed_form():
    c = 0.011803
    assert metric.analytic_everywhere_score(c) == pytest.approx(c / (c + 0.2 * (1 - c)))

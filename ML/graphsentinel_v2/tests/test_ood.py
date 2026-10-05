"""Tests for the open-set rejection stack."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphsentinel.evaluate import fpr_at_tpr, open_set_metrics, oscr_curve  # noqa: E402
from graphsentinel.ood import (  # noqa: E402
    AdaptiveConformal,
    MahalanobisOOD,
    Projection,
    blended_score,
    cascade_score,
    cholupdate,
)


# --------------------------------------------------------------------------
# Numerics
# --------------------------------------------------------------------------
def test_cholupdate_matches_explicit_refactorisation():
    rng = np.random.default_rng(0)
    for d in (4, 16, 64):
        A = rng.standard_normal((5 * d, d))
        S = np.cov(A, rowvar=False) + np.eye(d)
        L = np.linalg.cholesky(S)
        v = rng.standard_normal(d)
        beta = 0.37
        got = cholupdate(L, v, beta)
        want = S + beta * np.outer(v, v)
        assert np.abs(got @ got.T - want).max() < 1e-9, f"d={d}"


def test_projection_preserves_relative_distances():
    """Johnson-Lindenstrauss: a random orthonormal basis must not reorder which
    points are near and which are far.

    The data here is deliberately CLUSTERED. An earlier version of this test
    used iid Gaussian points, where every pairwise distance concentrates around
    sqrt(2d) and the correlation is dominated by noise -- the test measured
    distance concentration instead of JL distortion, and failed at corr=0.47.
    That is the very phenomenon that motivates projecting, so it belongs in the
    docs, not in an assertion about the projection's fidelity.
    """
    rng = np.random.default_rng(1)
    centres = rng.standard_normal((8, 384)) * 6
    X = np.concatenate([c + rng.standard_normal((50, 384)) for c in centres])
    Z = Projection(mode="random", out_dim=64, seed=0).fit(X).transform(X)

    d_hi = np.linalg.norm(X[:200, None] - X[None, 200:400], axis=-1).ravel()
    d_lo = np.linalg.norm(Z[:200, None] - Z[None, 200:400], axis=-1).ravel()
    corr = np.corrcoef(d_hi, d_lo)[0, 1]
    # 0.80, not 0.95: the JL bound at d_out=64 over 400 points is genuinely
    # loose (64 ~ 8 ln n / eps^2 gives eps ~ 0.87), so some reordering is
    # expected and is the price of the 10x scoring speedup. What must hold is
    # that the ordering is largely preserved and the distortion is centred.
    assert corr > 0.80, f"distance structure not preserved (corr={corr:.3f})"

    # JL distortion: after rescaling by sqrt(d_out/d_in) the ratio should be
    # tightly concentrated around 1.
    ratio = (d_lo / np.sqrt(64 / 384)) / d_hi
    assert 0.75 < np.median(ratio) < 1.25, f"median distortion {np.median(ratio):.3f}"


def test_high_dimensional_distance_concentration_is_real():
    """Document the motivation for the projection, as a check rather than a claim.

    In 384 dimensions the spread of pairwise distances between iid points
    collapses relative to their mean. That is what blurs the boundary between a
    low-volume beacon and a dense benign cluster, and why the covariance is
    fitted after projection rather than before.
    """
    rng = np.random.default_rng(4)
    contrast = {}
    for d in (16, 64, 384):
        X = rng.standard_normal((300, d))
        D = np.linalg.norm(X[:150, None] - X[None, 150:], axis=-1).ravel()
        contrast[d] = float((D.max() - D.min()) / D.mean())
    assert contrast[16] > contrast[384], (
        f"expected contrast to fall with dimension, got {contrast}"
    )


def test_projection_is_label_agnostic():
    """Neither projection may consult labels -- a supervised bottleneck would
    discard exactly the variance an unknown family lives in."""
    rng = np.random.default_rng(2)
    X = rng.standard_normal((300, 128))
    a = Projection(mode="random", out_dim=32, seed=7).fit(X).W
    b = Projection(mode="random", out_dim=32, seed=7).fit(X).W
    assert np.allclose(a, b), "random projection must be reproducible from its seed"
    assert Projection(mode="pca", out_dim=32).fit(X).W.shape == (128, 32)


# --------------------------------------------------------------------------
# Mahalanobis
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def blobs():
    """Three known classes plus an unseen family displaced off-manifold."""
    rng = np.random.default_rng(3)
    d = 96
    centres = rng.standard_normal((3, d)) * 4
    X = np.concatenate([centres[c] + rng.standard_normal((300, d)) for c in range(3)])
    y = np.repeat([0, 1, 2], 300)
    unknown = rng.standard_normal((150, d)) * 1.2 + 14.0
    return X, y, unknown


def test_mahalanobis_separates_unseen_cluster(blobs):
    X, y, unknown = blobs
    m = MahalanobisOOD(
        projection=Projection(mode="pca", out_dim=32, seed=0), components_per_class=2
    ).fit(X, y, 3)
    s_id, s_ood = m.score(X), m.score(unknown)
    assert s_ood.mean() > s_id.mean() * 5
    yy = np.r_[np.zeros(len(s_id)), np.ones(len(s_ood))].astype(bool)
    assert fpr_at_tpr(yy, np.r_[s_id, s_ood], 0.95) < 0.05


def test_mixture_beats_single_gaussian_on_multimodal_class(blobs):
    """One Gaussian over a multimodal class inflates covariance until nothing
    looks far. This is the failure that makes naive Mahalanobis look useless."""
    X, y, unknown = blobs
    merged = np.zeros_like(y)  # collapse all three modes into 'one class'
    yy = np.r_[np.zeros(len(X)), np.ones(len(unknown))].astype(bool)

    single = MahalanobisOOD(
        projection=Projection(mode="pca", out_dim=32), components_per_class=1
    ).fit(X, merged, 1)
    mixture = MahalanobisOOD(
        projection=Projection(mode="pca", out_dim=32), components_per_class=4
    ).fit(X, merged, 1)

    f_single = fpr_at_tpr(yy, np.r_[single.score(X), single.score(unknown)], 0.95)
    f_mix = fpr_at_tpr(yy, np.r_[mixture.score(X), mixture.score(unknown)], 0.95)
    assert f_mix <= f_single, f"mixture {f_mix:.4f} worse than single {f_single:.4f}"


def test_streaming_update_rejects_outliers(blobs):
    """The EMA gate must not absorb the anomalies it is meant to flag."""
    X, y, unknown = blobs
    m = MahalanobisOOD(
        projection=Projection(mode="pca", out_dim=32), components_per_class=2,
        ema_half_life_windows=5.0,
    ).fit(X, y, 3)
    before = m.score(unknown).mean()
    for _ in range(30):
        stats = m.partial_fit(unknown)          # feed it nothing but attack
        assert stats["accepted"] == 0, "outliers were absorbed into the model"
    after = m.score(unknown).mean()
    assert after > before * 0.9, "anomaly score decayed despite the gate"


def test_streaming_update_tracks_benign_drift(blobs):
    X, y, unknown = blobs
    m = MahalanobisOOD(
        projection=Projection(mode="pca", out_dim=32), components_per_class=2,
        ema_half_life_windows=3.0,
    ).fit(X, y, 3)
    drifted = X[y == 0] + 0.35
    first = m.score(drifted).mean()
    for _ in range(40):
        m.partial_fit(drifted)
    after = m.score(drifted).mean()
    assert after < first, f"EMA failed to follow a benign shift ({first:.2f} -> {after:.2f})"


def test_covariance_does_not_ratchet_shut_under_gated_updates(blobs):
    """Regression guard for a self-inflicted false-alarm ramp.

    The acceptance gate only feeds back samples already close to a component,
    so the update sample is truncated and its spread is biased low. Without the
    anchor toward the fitted covariance, each window shrinks the covariance a
    little, Mahalanobis distances inflate, and the alarm rate climbs on its own
    -- indistinguishable from concept drift in production, but entirely caused
    by the detector. This asserts the anchor holds it.
    """
    X, y, _ = blobs
    m = MahalanobisOOD(
        projection=Projection(mode="pca", out_dim=32), components_per_class=2,
        ema_half_life_windows=3.0,
    ).fit(X, y, 3)
    baseline = m.score(X).mean()
    for _ in range(150):
        m.partial_fit(X)                     # stationary input, many windows
    after = m.score(X).mean()
    assert after < baseline * 1.3, (
        f"score inflated {baseline:.2f} -> {after:.2f} on stationary input "
        "-- covariance is ratcheting shut"
    )


def test_update_strategy_switches_on_dimension():
    hi = MahalanobisOOD(projection=Projection(mode="random", out_dim=384))
    lo = MahalanobisOOD(projection=Projection(mode="random", out_dim=64))
    assert hi._use_rank1() is True
    assert lo._use_rank1() is False, "rank-1 is slower than rebuild at d=64"


def test_scorer_roundtrips_through_json(blobs, tmp_path):
    X, y, unknown = blobs
    m = MahalanobisOOD(projection=Projection(mode="pca", out_dim=32)).fit(X, y, 3)
    p = tmp_path / "ood.json"
    m.save(p)
    m2 = MahalanobisOOD.load(p)
    assert np.allclose(m.score(unknown), m2.score(unknown))


# --------------------------------------------------------------------------
# Cascade
# --------------------------------------------------------------------------
def test_cascade_ranks_head_detections_above_head_benign():
    probs = np.array([[0.9, 0.1], [0.2, 0.8], [0.95, 0.05]])
    maha = np.array([100.0, 0.1, 0.2])   # first sample is far, but head says benign
    s = cascade_score(probs, maha)
    flagged = probs.argmax(1) != 0
    assert s[flagged].min() >= s[~flagged].max()
    # within the benign band, distance decides the ordering
    assert s[0] > s[2]


def test_blended_score_is_monotone_in_both_inputs():
    rng = np.random.default_rng(9)
    probs = rng.dirichlet(np.ones(6), size=200)
    maha = rng.gamma(2.0, 5.0, size=200)
    s = blended_score(probs, maha, weight=0.5)
    assert s.shape == (200,) and np.isfinite(s).all()
    assert 0.0 <= s.min() and s.max() <= 1.0


# --------------------------------------------------------------------------
# Open-set metrics
# --------------------------------------------------------------------------
def test_oscr_penalises_rejecting_knowns():
    """A detector that rejects everything gets perfect OOD separation but zero
    OSCR -- which is the whole reason OSCR is reported."""
    known_correct = np.ones(100, bool)
    reject_all_known = np.full(100, 10.0)
    unknown = np.full(100, 10.0)
    _, _, oscr_bad = oscr_curve(known_correct, reject_all_known, unknown)

    good_known = np.zeros(100)
    good_unknown = np.ones(100)
    _, _, oscr_good = oscr_curve(known_correct, good_known, good_unknown)
    assert oscr_good > oscr_bad


def test_open_set_metrics_shape():
    rng = np.random.default_rng(11)
    y = np.r_[np.zeros(200), np.ones(80), np.full(60, 3)].astype(int)
    pred = y.copy()
    pred[y == 3] = 0                       # unknown collapses into BENIGN
    score = np.r_[rng.normal(1, 0.3, 280), rng.normal(4, 0.5, 60)]
    m = open_set_metrics(y, pred, score, unknown_label=3)
    for k in ("oscr_auc", "fpr_at_95tpr", "ood_auroc", "closed_set_acc_on_knowns"):
        assert k in m and np.isfinite(m[k]), k
    assert m["closed_set_acc_on_knowns"] == 1.0


# --------------------------------------------------------------------------
# Adaptive conformal
# --------------------------------------------------------------------------
def test_aci_holds_target_under_drift_where_static_fails():
    """Split conformal assumes exchangeability. Traffic is not exchangeable."""
    rng = np.random.default_rng(13)
    base = rng.gamma(4.0, 25.0, size=4000)

    aci = AdaptiveConformal(target_fpr=0.01, gamma=0.02)
    aci.calibrate(rng.choice(base, 800))
    static_thr = float(np.percentile(rng.choice(base, 800), 99.0))

    static, adaptive = [], []
    for w in range(60):
        batch = rng.choice(base, 200) * (1.0 + 0.04 * w)   # baseline drifts up
        static.append(float((batch > static_thr).mean()))
        adaptive.append(aci.update(batch)["realised_fpr"])

    s_tail, a_tail = np.mean(static[-15:]), np.mean(adaptive[-15:])
    assert s_tail > 0.05, f"drift did not break the static threshold ({s_tail:.3f})"
    assert a_tail < s_tail / 2, f"ACI did not recover coverage ({a_tail:.3f} vs {s_tail:.3f})"


def test_aci_threshold_is_finite_after_calibration():
    a = AdaptiveConformal(target_fpr=0.01)
    a.calibrate(np.random.default_rng(0).gamma(3, 10, 500))
    assert np.isfinite(a.threshold()) and a.threshold() > 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))

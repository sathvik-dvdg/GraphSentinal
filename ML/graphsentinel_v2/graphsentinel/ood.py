"""
Out-of-distribution rejection for open-set intrusion detection.

STATUS: this machinery is INSTRUMENTATION, not yet an improvement. Read
docs/OPEN_SET.md before relying on the scorer.

Measured over 3 seeds x 2 held-out families, post-hoc Mahalanobis on the JK
embedding LOSES to the closed-set proxy ``1 - P(BENIGN)`` in 5 of 6 paired
runs (mean FPR@95TPR delta +0.11, and lower OSCR in both families). An earlier
single-seed run showed the opposite and was a fluke -- the baseline happened to
land at the bad end of its own range that run. The honest reading is that the
JK embedding does not carry the unseen family in a form an unsupervised
Gaussian distance reads better than the trained head does.

What DOES replicate, 6 runs out of 6, is the diagnosis: the closed-set head
resolves an unknown family into exactly one of two regimes --

  COLLAPSE   Botnet    -> BENIGN    (799/851, 757/805, 608/828)
  SHOEHORN   SSHBrute  -> DoSHulk   (132/132, 130/130, 133/134)

-- and its score is excellent in the second regime and poor in the first, with
no way to tell which you are in without labels. That instability is real and
unresolved; this module is what makes it measurable.

Three components:

  Projection            fixed dimensionality reduction before any covariance
                        is fitted -- 384-d Mahalanobis suffers distance
                        concentration and costs O(d^3) to re-factorise
  MahalanobisOOD        class-conditional Gaussian mixture, Ledoit-Wolf
                        shrinkage, Cholesky-factored, rank-1 EMA updates
  AdaptiveConformal     ACI threshold; split conformal is invalid here because
                        network traffic is not exchangeable

A note on why the projection is NEVER learned from the classification
objective. The encoder is trained with focal loss, so its layers are optimised
to discard variance that does not separate KNOWN classes -- which is exactly
the variance an unknown family lives in. A supervised bottleneck on top would
compound that loss. Both projections offered here are label-agnostic: a random
orthonormal basis (Johnson-Lindenstrauss, unbiased with respect to any
direction) or PCA (unsupervised, but fitted on in-distribution data, so it can
still discard a low-variance OOD direction). Random is the default for that
reason; PCA is available because it is usually stronger when the OOD signal
happens to live in high-variance directions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.linalg import solve_triangular

EPS = 1e-8


# --------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------
@dataclass
class Projection:
    """Fixed linear map applied before any covariance is estimated."""

    mode: str = "random"  # random | pca | none
    out_dim: int = 64
    seed: int = 0
    W: Optional[np.ndarray] = None  # (in_dim, out_dim)
    mean: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray) -> "Projection":
        X = np.asarray(X, dtype=np.float64)
        self.mean = X.mean(0)
        d_in = X.shape[1]

        if self.mode == "none" or self.out_dim >= d_in:
            self.W = np.eye(d_in)
            self.out_dim = d_in
            return self

        if self.mode == "random":
            # Orthonormal columns via QR. JL guarantees pairwise distances are
            # preserved to within (1 +- eps) for out_dim ~ O(log n / eps^2),
            # and crucially the basis is chosen without reference to labels.
            rng = np.random.default_rng(self.seed)
            G = rng.standard_normal((d_in, self.out_dim))
            Q, _ = np.linalg.qr(G)
            self.W = Q[:, : self.out_dim]
        elif self.mode == "pca":
            Xc = X - self.mean
            # economy SVD; no need for the full d_in x d_in covariance
            _, _, Vt = np.linalg.svd(Xc, full_matrices=False)
            self.W = Vt[: self.out_dim].T
        else:
            raise ValueError(f"unknown projection mode: {self.mode}")
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float64)
        return (X - self.mean) @ self.W

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "out_dim": int(self.out_dim),
            "seed": self.seed,
            "W": self.W.tolist(),
            "mean": self.mean.tolist(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Projection":
        p = cls(mode=d["mode"], out_dim=d["out_dim"], seed=d.get("seed", 0))
        p.W = np.array(d["W"], dtype=np.float64)
        p.mean = np.array(d["mean"], dtype=np.float64)
        return p


# --------------------------------------------------------------------------
# Rank-1 Cholesky update
# --------------------------------------------------------------------------
def cholupdate(L: np.ndarray, x: np.ndarray, beta: float = 1.0) -> np.ndarray:
    """Cholesky factor of ``L @ L.T + beta * outer(x, x)``, in O(d^2).

    MEASURED CAVEAT -- read before assuming this is the fast path.

    The asymptotics favour this over re-factorising (O(d^2) vs O(d^3)), but the
    constants decide it at the dimensions we actually run. numpy's cholesky is
    blocked, cache-aware LAPACK; this is an interpreted loop over d iterations.
    Benchmarked at 14 components per update:

        d=384   rebuild 77 ms   rank-1 58 ms    rank-1 wins  1.3x
        d=128   rebuild  4 ms   rank-1 15 ms    rebuild wins 3.6x
        d= 64   rebuild  0.8ms  rank-1  7 ms    rebuild wins 9x
        d= 32   rebuild  0.4ms  rank-1  4 ms    rebuild wins 10x

    So the two mitigations interact: once the embedding is projected to <=64
    dimensions, rank-1 updating is COUNTERPRODUCTIVE and full re-factorisation
    at 0.8 ms/window is already negligible against a 60 s window. This routine
    is kept, correct and tested, for the d>=256 path and for deployments that
    disable the projection. ``MahalanobisOOD`` picks between them by dimension.

    A compiled cholupdate (Cython/numba) would move the crossover down, but not
    below the point where re-factorisation is already free.
    """
    L = np.array(L, dtype=np.float64, copy=True)
    x = np.array(x, dtype=np.float64, copy=True) * np.sqrt(max(beta, 0.0))
    n = L.shape[0]
    for k in range(n):
        Lkk = L[k, k]
        if Lkk <= EPS:
            L[k, k] = Lkk = EPS
        r = float(np.hypot(Lkk, x[k]))
        c = r / Lkk
        s = x[k] / Lkk
        L[k, k] = r
        if k + 1 < n:
            L[k + 1 :, k] = (L[k + 1 :, k] + s * x[k + 1 :]) / c
            x[k + 1 :] = c * x[k + 1 :] - s * L[k + 1 :, k]
    return L


def _ledoit_wolf_cov(X: np.ndarray) -> np.ndarray:
    """Shrunk covariance. Falls back to a ridge if sklearn is unavailable."""
    try:
        from sklearn.covariance import LedoitWolf

        return LedoitWolf(assume_centered=False).fit(X).covariance_
    except Exception:  # pragma: no cover
        S = np.cov(X, rowvar=False)
        mu = np.trace(S) / S.shape[0]
        return 0.9 * S + 0.1 * mu * np.eye(S.shape[0])


# --------------------------------------------------------------------------
# Mahalanobis mixture
# --------------------------------------------------------------------------
@dataclass
class _Component:
    label: int
    mean: np.ndarray
    chol: np.ndarray  # lower-triangular Cholesky of the covariance
    cov0: np.ndarray = None  # covariance at fit time; anchors streaming updates
    weight: float = 1.0
    n_updates: int = 0


class MahalanobisOOD:
    """Class-conditional Gaussian mixture OOD scorer with streaming updates.

    Score is the minimum squared Mahalanobis distance to any component. High =
    far from every known mode = out of distribution.

    Mixture components rather than one Gaussian per class, because BENIGN is
    not a single mode: it is web, DNS, database and backup traffic. Forcing one
    Gaussian over all of it inflates the covariance until nothing is far from
    anything -- the failure mode that makes naive Mahalanobis look useless on
    network data.
    """

    def __init__(
        self,
        projection: Optional[Projection] = None,
        components_per_class: int = 4,
        min_samples: int = 20,
        ema_half_life_windows: float = 200.0,
        update_percentile: float = 95.0,
        anchor: float = 0.02,
        resync_every: int = 500,
        seed: int = 0,
        update_strategy: str = "auto",  # auto | rank1 | rebuild
        rank1_min_dim: int = 256,
    ):
        self.projection = projection or Projection(mode="pca", out_dim=32, seed=seed)
        self.k = components_per_class
        self.min_samples = min_samples
        self.ema_half_life = ema_half_life_windows
        self.update_percentile = update_percentile
        self.anchor = anchor
        self.resync_every = resync_every
        self.seed = seed
        self.update_strategy = update_strategy
        self.rank1_min_dim = rank1_min_dim
        self.components: List[_Component] = []
        self._update_count = 0
        self._accept_threshold: Optional[float] = None

    def _use_rank1(self) -> bool:
        """Rank-1 only pays above ~256 dims. See the note on ``cholupdate``."""
        if self.update_strategy == "rank1":
            return True
        if self.update_strategy == "rebuild":
            return False
        return self.projection.out_dim >= self.rank1_min_dim

    # ------------------------------------------------------------------
    def fit(self, emb: np.ndarray, labels: np.ndarray, n_classes: int) -> "MahalanobisOOD":
        emb = np.asarray(emb, dtype=np.float64)
        labels = np.asarray(labels)
        self.projection.fit(emb)
        Z = self.projection.transform(emb)

        self.components = []
        for c in range(n_classes):
            m = labels == c
            if m.sum() < self.min_samples:
                continue
            Zc = Z[m]
            groups = self._cluster(Zc)
            for gZ in groups:
                if len(gZ) < self.min_samples:
                    continue
                cov = _ledoit_wolf_cov(gZ)
                cov += EPS * np.eye(cov.shape[0])
                try:
                    L = np.linalg.cholesky(cov)
                except np.linalg.LinAlgError:  # pragma: no cover
                    cov += 1e-4 * np.trace(cov) / cov.shape[0] * np.eye(cov.shape[0])
                    L = np.linalg.cholesky(cov)
                self.components.append(
                    _Component(label=c, mean=gZ.mean(0), chol=L, cov0=cov.copy(),
                               weight=len(gZ) / len(Z))
                )

        if not self.components:
            raise RuntimeError("no components fitted -- not enough samples per class")

        # Calibrate the self-update gate on training data, so streaming EMA
        # updates only absorb points that already look in-distribution. Without
        # this, a slow-ramping attacker can walk the Gaussians out to meet
        # their own traffic -- the same poisoning path the feature scaler guards.
        self._accept_threshold = float(
            np.percentile(self.score(emb, already_projected=False), self.update_percentile)
        )
        return self

    def _cluster(self, Z: np.ndarray) -> List[np.ndarray]:
        if len(Z) < self.k * self.min_samples:
            return [Z]
        try:
            from sklearn.cluster import KMeans

            km = KMeans(n_clusters=self.k, n_init=4, random_state=self.seed).fit(Z)
            return [Z[km.labels_ == j] for j in range(self.k)]
        except Exception:  # pragma: no cover
            return [Z]

    # ------------------------------------------------------------------
    def score(self, emb: np.ndarray, already_projected: bool = False) -> np.ndarray:
        """Min squared Mahalanobis distance to any component."""
        Z = np.asarray(emb, dtype=np.float64) if already_projected else self.projection.transform(emb)
        if Z.ndim == 1:
            Z = Z[None, :]
        best = np.full(len(Z), np.inf)
        for comp in self.components:
            D = (Z - comp.mean).T  # (d, n)
            # ||L^-1 (z - mu)||^2 via a triangular solve: O(n d^2), and never
            # forms an explicit inverse.
            sol = solve_triangular(comp.chol, D, lower=True, check_finite=False)
            best = np.minimum(best, np.einsum("ij,ij->j", sol, sol))
        return best

    def score_per_class(self, emb: np.ndarray) -> np.ndarray:
        """(n, n_classes) min distance to each class's components."""
        Z = self.projection.transform(emb)
        labels = sorted({c.label for c in self.components})
        out = np.full((len(Z), max(labels) + 1), np.inf)
        for comp in self.components:
            D = (Z - comp.mean).T
            sol = solve_triangular(comp.chol, D, lower=True, check_finite=False)
            d2 = np.einsum("ij,ij->j", sol, sol)
            out[:, comp.label] = np.minimum(out[:, comp.label], d2)
        return out

    # ------------------------------------------------------------------
    def partial_fit(self, emb: np.ndarray) -> Dict[str, float]:
        """Unsupervised EMA drift tracking. O(d^2) per accepted sample.

        No labels at inference time, so each accepted sample updates its
        nearest component. Samples above the acceptance gate are treated as
        candidate anomalies and are NOT absorbed -- otherwise the detector
        learns the attack it is supposed to be flagging.
        """
        Z = self.projection.transform(emb)
        d2 = self.score(Z, already_projected=True)
        accept = d2 <= (self._accept_threshold or np.inf)
        n_acc = int(accept.sum())
        if n_acc == 0:
            self._update_count += 1
            return {"accepted": 0, "rejected": int(len(Z)), "alpha": 0.0}

        a = 1.0 - 0.5 ** (1.0 / max(self.ema_half_life, 1.0))
        Za = Z[accept]

        # nearest component per accepted sample
        dists = np.stack(
            [
                np.einsum(
                    "ij,ij->j",
                    solve_triangular(c.chol, (Za - c.mean).T, lower=True, check_finite=False),
                    solve_triangular(c.chol, (Za - c.mean).T, lower=True, check_finite=False),
                )
                for c in self.components
            ]
        )
        assign = dists.argmin(0)

        scale = np.sqrt(1.0 - a)
        beta = a / (1.0 - a)
        use_rank1 = self._use_rank1()
        for j, comp in enumerate(self.components):
            sel = Za[assign == j]
            if not len(sel):
                continue
            if use_rank1:
                for z in sel:
                    v = z - comp.mean
                    comp.chol = scale * cholupdate(comp.chol, v, beta)
                    comp.mean = comp.mean + a * v
                # same truncation anchor as the rebuild path
                cov = comp.chol @ comp.chol.T
                cov = (1.0 - self.anchor) * cov + self.anchor * comp.cov0
                comp.chol = np.linalg.cholesky(cov + EPS * np.eye(cov.shape[0]))
            else:
                # Batched rebuild: form the EMA covariance once for the whole
                # accepted batch and re-factorise. At d<=64 this is ~0.06 ms per
                # component -- cheaper than looping rank-1 updates in Python.
                cov = comp.chol @ comp.chol.T
                V_old = sel - comp.mean
                comp.mean = comp.mean + a * V_old.mean(0)
                V_new = sel - comp.mean
                # Cross-moment about old AND new mean (Welford/West form). Using
                # (x - mu_old)^2 alone double-counts the mean shift and inflates
                # the covariance.
                cov = (1.0 - a) * cov + a * (V_old.T @ V_new) / len(V_new)
                # ANCHOR. The acceptance gate feeds back only samples already
                # near the component, so the update sample is truncated and its
                # spread is systematically too small. Left alone, the covariance
                # ratchets downward every window, Mahalanobis distances inflate,
                # and the detector drifts into a rising false-alarm rate -- a
                # slow failure that looks like concept drift but is self-
                # inflicted. Blending a fixed fraction of the ORIGINAL fitted
                # covariance back in each step bounds that ratchet while still
                # tracking a genuine baseline shift.
                cov = (1.0 - self.anchor) * cov + self.anchor * comp.cov0
                d = cov.shape[0]
                try:
                    comp.chol = np.linalg.cholesky(cov + EPS * np.eye(d))
                except np.linalg.LinAlgError:  # pragma: no cover
                    mu = np.trace(cov) / d
                    comp.chol = np.linalg.cholesky(
                        0.9 * cov + 0.1 * mu * np.eye(d) + EPS * np.eye(d)
                    )
            comp.n_updates += len(sel)

        self._update_count += 1
        if self.resync_every and self._update_count % self.resync_every == 0:
            self._resync()
        return {"accepted": n_acc, "rejected": int(len(Z) - n_acc), "alpha": float(a)}

    def _resync(self) -> None:
        """Periodic re-shrinkage: repeated rank-1 updates drift toward
        ill-conditioning, so pull each factor back toward its isotropic target."""
        for comp in self.components:
            cov = comp.chol @ comp.chol.T
            mu = np.trace(cov) / cov.shape[0]
            cov = 0.95 * cov + 0.05 * mu * np.eye(cov.shape[0])
            try:
                comp.chol = np.linalg.cholesky(cov + EPS * np.eye(cov.shape[0]))
            except np.linalg.LinAlgError:  # pragma: no cover
                comp.chol = np.linalg.cholesky(mu * np.eye(cov.shape[0]))

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": 1,
            "projection": self.projection.to_dict(),
            "components_per_class": self.k,
            "ema_half_life_windows": self.ema_half_life,
            "update_percentile": self.update_percentile,
            "anchor": self.anchor,
            "accept_threshold": self._accept_threshold,
            "components": [
                {
                    "label": c.label,
                    "mean": c.mean.tolist(),
                    "chol": c.chol.tolist(),
                    "cov0": c.cov0.tolist() if c.cov0 is not None else None,
                    "weight": c.weight,
                }
                for c in self.components
            ],
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict()), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: dict) -> "MahalanobisOOD":
        m = cls(
            projection=Projection.from_dict(d["projection"]),
            components_per_class=d.get("components_per_class", 4),
            ema_half_life_windows=d.get("ema_half_life_windows", 200.0),
            update_percentile=d.get("update_percentile", 95.0),
            anchor=d.get("anchor", 0.02),
        )
        m._accept_threshold = d.get("accept_threshold")
        m.components = [
            _Component(
                label=c["label"],
                mean=np.array(c["mean"]),
                chol=np.array(c["chol"]),
                cov0=np.array(c["cov0"]) if c.get("cov0") is not None else None,
                weight=c.get("weight", 1.0),
            )
            for c in d["components"]
        ]
        return m

    @classmethod
    def load(cls, path: str | Path) -> "MahalanobisOOD":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# --------------------------------------------------------------------------
# Cascade scoring
# --------------------------------------------------------------------------
def _rank(x: np.ndarray) -> np.ndarray:
    r = np.empty(len(x), dtype=np.float64)
    r[np.argsort(x)] = np.arange(len(x))
    return r / max(len(x) - 1, 1)


def cascade_score(
    head_probs: np.ndarray,
    maha_score: np.ndarray,
    benign_index: int = 0,
) -> np.ndarray:
    """Two-stage OOD score. Head first, structural distance as second opinion.

    Motivated by the two failure regimes measured on held-out families:

      SHOEHORN   the unseen family is absorbed by a known ATTACK class
                 (SSH brute force -> DoS Hulk, 137/138 nodes). The closed-set
                 head is then RIGHT about "not benign" and scores a perfect
                 AUROC. Mahalanobis is slightly worse here.
      COLLAPSE   the unseen family is absorbed by BENIGN
                 (Botnet -> BENIGN, 792/806 nodes). The head is confidently
                 wrong; its score degrades to FPR@95TPR = 0.74. Mahalanobis
                 recovers most of it.

    Neither score dominates, and you cannot tell which regime you are in
    without labels. The cascade sidesteps the choice: anything the head already
    calls an attack ranks above everything it calls benign, and *within* the
    benign band -- the collapse regime, and the only place the head has failed
    -- ordering comes from structural distance instead.

    MEASURED RESULT, 3 seeds x 2 families, mean FPR@95TPR (lower better):

        family      closed-set   blended   cascade   mahalanobis
        Botnet         0.533      0.484     0.700       0.717
        SSHBrute       0.000      0.000     0.000       0.042

    The cascade does NOT beat the baseline. Paired across all six runs it is
    +0.084 worse on average (1 win, 2 losses, 3 ties). Only ``blended`` is
    marginally ahead (-0.025), which is well inside the seed-to-seed spread.

    A single-seed run previously suggested the cascade won decisively. It did
    not replicate. Both combiners are retained because they bound the downside
    of the closed-set score, and because the evaluation harness needs something
    to compare against -- not because either is currently recommended.
    """
    head_probs = np.asarray(head_probs, dtype=np.float64)
    maha_score = np.asarray(maha_score, dtype=np.float64)
    pred = head_probs.argmax(axis=1)
    threat = 1.0 - head_probs[:, benign_index]
    return np.where(
        pred != benign_index,
        0.5 + 0.5 * _rank(threat),
        0.5 * _rank(maha_score),
    )


def blended_score(
    head_probs: np.ndarray, maha_score: np.ndarray, weight: float = 0.5,
    benign_index: int = 0,
) -> np.ndarray:
    """Softer alternative: keep softmax ordering, let distance re-rank the
    benign band. Better OSCR and better FPR@80TPR than the cascade, worse
    FPR@95TPR. Use when the operating point is known and moderate."""
    head_probs = np.asarray(head_probs, dtype=np.float64)
    pred = head_probs.argmax(axis=1)
    rp = _rank(1.0 - head_probs[:, benign_index])
    rm = _rank(np.asarray(maha_score, dtype=np.float64))
    return np.where(pred != benign_index, rp, (1 - weight) * rp + weight * rm)


# --------------------------------------------------------------------------
# Adaptive Conformal Inference
# --------------------------------------------------------------------------
@dataclass
class AdaptiveConformal:
    """Online threshold with a long-run false-alarm guarantee under drift.

    Split conformal assumes exchangeability. Window graphs are not
    exchangeable -- they carry diurnal baseline shifts, burst dynamics and
    heavy temporal autocorrelation -- so a threshold frozen from a calibration
    fold silently loses coverage as the day progresses. ACI (Gibbs & Candes,
    2021) instead adjusts the working miscoverage level after every window:

        alpha_{t+1} = alpha_t + gamma * (target - err_t)

    err_t is 1 when the window's realised alarm rate exceeded the target. The
    guarantee is asymptotic on the realised rate, and it holds regardless of
    how the distribution moves.

    ONE HONEST CAVEAT. ACI needs feedback -- it must observe err_t. An IDS has
    no ground-truth labels at inference time, so this cannot be driven from
    detection correctness. What it CAN be driven from is the alarm rate on a
    designated benign reference population (a known-clean subnet, an
    allowlisted host set, or the analyst-dispositioned backlog on a delay).
    That controls the false-alarm side, which is the side that has an operating
    budget. It does not, and cannot, control the miss rate without labels.
    """

    target_fpr: float = 0.01
    gamma: float = 0.01
    alpha: float = 0.01
    quantile_window: int = 500
    alpha_min: float = 1e-4
    alpha_max: float = 0.5

    _scores: List[float] = field(default_factory=list)
    _history: List[dict] = field(default_factory=list)

    def calibrate(self, reference_scores: Sequence[float]) -> float:
        """Seed the score buffer from a benign calibration fold."""
        self._scores = list(map(float, reference_scores))[-self.quantile_window * 4 :]
        self.alpha = self.target_fpr
        return self.threshold()

    def threshold(self) -> float:
        if not self._scores:
            return float("inf")
        q = 100.0 * (1.0 - min(max(self.alpha, self.alpha_min), self.alpha_max))
        return float(np.percentile(self._scores[-self.quantile_window * 4 :], q))

    def update(self, reference_scores: Sequence[float]) -> dict:
        """One ACI step from this window's benign-reference scores."""
        thr = self.threshold()
        ref = np.asarray(reference_scores, dtype=np.float64)
        realised = float((ref > thr).mean()) if len(ref) else 0.0
        err = 1.0 if realised > self.target_fpr else 0.0

        self.alpha = float(
            np.clip(self.alpha + self.gamma * (self.target_fpr - err), self.alpha_min, self.alpha_max)
        )
        if len(ref):
            self._scores.extend(ref.tolist())
            self._scores = self._scores[-self.quantile_window * 4 :]

        rec = {
            "threshold": thr,
            "realised_fpr": realised,
            "alpha": self.alpha,
            "n_reference": int(len(ref)),
        }
        self._history.append(rec)
        return rec

    def to_dict(self) -> dict:
        return {
            "target_fpr": self.target_fpr,
            "gamma": self.gamma,
            "alpha": self.alpha,
            "quantile_window": self.quantile_window,
            "scores": self._scores[-self.quantile_window * 4 :],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AdaptiveConformal":
        a = cls(
            target_fpr=d.get("target_fpr", 0.01),
            gamma=d.get("gamma", 0.01),
            alpha=d.get("alpha", 0.01),
            quantile_window=d.get("quantile_window", 500),
        )
        a._scores = list(d.get("scores", []))
        return a

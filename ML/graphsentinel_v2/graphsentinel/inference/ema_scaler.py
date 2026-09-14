"""
Adaptive feature scaling for a non-stationary signal.

Replaces the pickled ``StandardScaler`` fitted once on an offline snapshot.
Network traffic is not stationary: mean flow rate at 03:00 is nothing like
14:00, a new service deployment shifts byte volumes permanently, and a
legitimate traffic spike looks -- to a frozen scaler -- exactly like an attack.
That is a false-positive generator, and it gets worse every week the model
stays deployed.

Here the statistics track the signal:

    mu_t     = (1 - a) mu_{t-1}     + a x_t
    var_t    = (1 - a) var_{t-1}    + a (x_t - mu_{t-1})(x_t - mu_t)

with ``a`` derived from a half-life in wall-clock seconds, so the adaptation
rate is a stated operational policy ("forget the last hour over an hour")
rather than an opaque constant.

Two safeguards matter, because an adaptive scaler can be attacked:

  * WARM START. Statistics are seeded from the training distribution and the
    first ``warmup_updates`` batches blend toward the live signal, so the model
    is never scaled by a half-empty estimate at startup.

  * BOUNDED DRIFT. Live statistics are clamped to a band around the reference.
    Without this, an attacker who ramps traffic slowly enough can walk the
    normal band out to meet their attack -- boiling-frog poisoning. The clamp
    means adaptation can absorb a shifted baseline but cannot be led anywhere.
    Breaching the band raises a drift alarm instead of silently following.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np


@dataclass
class DriftReport:
    drifted: bool
    max_z: float
    feature_index: int
    feature_name: str
    detail: str


@dataclass
class EMAScaler:
    """Streaming standardiser with drift detection and poisoning bounds."""

    n_features: int
    feature_names: List[str] = field(default_factory=list)
    half_life_seconds: float = 900.0
    warmup_updates: int = 50
    max_drift_sigma: float = 3.0  # how far live mu may wander from reference
    eps: float = 1e-6

    # state
    mean: np.ndarray = field(default=None, repr=False)
    var: np.ndarray = field(default=None, repr=False)
    ref_mean: np.ndarray = field(default=None, repr=False)
    ref_std: np.ndarray = field(default=None, repr=False)
    n_updates: int = 0
    last_t: Optional[float] = None

    def __post_init__(self):
        if self.mean is None:
            self.mean = np.zeros(self.n_features, dtype=np.float64)
        if self.var is None:
            self.var = np.ones(self.n_features, dtype=np.float64)
        if self.ref_mean is None:
            self.ref_mean = self.mean.copy()
        if self.ref_std is None:
            self.ref_std = np.sqrt(self.var).copy()
        if not self.feature_names:
            self.feature_names = [f"f{i}" for i in range(self.n_features)]

    # ------------------------------------------------------------------
    @classmethod
    def from_training(
        cls, x: np.ndarray, feature_names: List[str], **kwargs
    ) -> "EMAScaler":
        """Seed reference statistics from the training feature matrix."""
        mean = np.asarray(x, dtype=np.float64).mean(axis=0)
        var = np.asarray(x, dtype=np.float64).var(axis=0)
        s = cls(n_features=x.shape[1], feature_names=list(feature_names), **kwargs)
        s.mean, s.var = mean.copy(), np.maximum(var, s.eps)
        s.ref_mean, s.ref_std = mean.copy(), np.sqrt(np.maximum(var, s.eps))
        return s

    def _alpha(self, dt: float) -> float:
        if self.half_life_seconds <= 0:
            return 1.0
        return 1.0 - math.pow(0.5, max(dt, 0.0) / self.half_life_seconds)

    # ------------------------------------------------------------------
    def partial_fit(self, x: np.ndarray, t: Optional[float] = None) -> DriftReport:
        """Fold a batch of live feature rows into the running statistics."""
        x = np.asarray(x, dtype=np.float64)
        if x.ndim == 1:
            x = x[None, :]
        if x.shape[1] != self.n_features:
            raise ValueError(f"expected {self.n_features} features, got {x.shape[1]}")

        batch_mean = np.nanmean(x, axis=0)
        batch_var = np.nanvar(x, axis=0)

        dt = self.half_life_seconds if t is None or self.last_t is None else (t - self.last_t)
        a = self._alpha(dt)
        # During warmup, blend more slowly toward live stats so a quiet first
        # minute cannot define "normal" for the whole deployment.
        if self.n_updates < self.warmup_updates:
            a *= (self.n_updates + 1) / self.warmup_updates

        prev_mean = self.mean.copy()
        self.mean = (1 - a) * self.mean + a * batch_mean
        self.var = (1 - a) * self.var + a * (
            batch_var + (batch_mean - prev_mean) * (batch_mean - self.mean)
        )
        self.var = np.maximum(self.var, self.eps)
        self.n_updates += 1
        self.last_t = t if t is not None else self.last_t

        return self._clamp_and_report()

    def _clamp_and_report(self) -> DriftReport:
        z = np.abs(self.mean - self.ref_mean) / np.maximum(self.ref_std, self.eps)
        idx = int(np.argmax(z))
        max_z = float(z[idx])
        drifted = max_z > self.max_drift_sigma
        if drifted:
            lo = self.ref_mean - self.max_drift_sigma * self.ref_std
            hi = self.ref_mean + self.max_drift_sigma * self.ref_std
            self.mean = np.clip(self.mean, lo, hi)
        return DriftReport(
            drifted=drifted,
            max_z=max_z,
            feature_index=idx,
            feature_name=self.feature_names[idx],
            detail=(
                f"'{self.feature_names[idx]}' mean is {max_z:.2f} sigma from the "
                f"training reference; clamped at {self.max_drift_sigma} sigma. "
                "Investigate: new service, traffic-shape change, or slow poisoning."
            )
            if drifted
            else "within reference band",
        )

    # ------------------------------------------------------------------
    def transform(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        out = (x - self.mean) / np.sqrt(self.var + self.eps)
        return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    def fit_transform(self, x: np.ndarray, t: Optional[float] = None) -> np.ndarray:
        self.partial_fit(x, t)
        return self.transform(x)

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": 1,
            "n_features": self.n_features,
            "feature_names": self.feature_names,
            "half_life_seconds": self.half_life_seconds,
            "warmup_updates": self.warmup_updates,
            "max_drift_sigma": self.max_drift_sigma,
            "mean": self.mean.tolist(),
            "var": self.var.tolist(),
            "ref_mean": self.ref_mean.tolist(),
            "ref_std": self.ref_std.tolist(),
            "n_updates": self.n_updates,
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: dict) -> "EMAScaler":
        s = cls(
            n_features=d["n_features"],
            feature_names=d.get("feature_names", []),
            half_life_seconds=d.get("half_life_seconds", 900.0),
            warmup_updates=d.get("warmup_updates", 50),
            max_drift_sigma=d.get("max_drift_sigma", 3.0),
        )
        s.mean = np.array(d["mean"], dtype=np.float64)
        s.var = np.array(d["var"], dtype=np.float64)
        s.ref_mean = np.array(d["ref_mean"], dtype=np.float64)
        s.ref_std = np.array(d["ref_std"], dtype=np.float64)
        s.n_updates = int(d.get("n_updates", 0))
        return s

    @classmethod
    def load(cls, path: str | Path) -> "EMAScaler":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

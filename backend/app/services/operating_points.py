# [WSL2]
"""Operating points — the thresholds that turn model scores into decisions.

WHY THESE ARE NOT CONSTANTS IN THIS FILE

A binary gate and an alert rule are claims about measured precision and recall,
so they are read from the artefact that measured them, `ML/threshold_study.json`,
and each loaded value records the key it came from. Nothing here restates a
number.

WHAT IS READ, AND WHAT IS NOT

Exactly three top-level scalars: `binary_gate`, `alert_min_flows`,
`alert_window_seconds`. The file's `flow_level` block and its
`per_class_min_conf` fits are NOT read -- the SDN confidence floors in
mitigation_policy.py are unaffected by this module.

THE LOADED VALUES ARE PROVISIONAL

A file that loads as `verified` is not a validated operating point
(INTEGRATION.md §4):

  * `binary_gate` 0.5 is one of six fixed values the study script appended to
    its quantile search grid; `idxmax` can return an appended value as the
    "fitted" answer, and breaks ties by taking the lowest threshold. Whether 0.5
    is a real optimum is being re-checked.
  * the model's inference is not reproducible run to run, and that variation is
    unmeasured. The committed notebook's saved output and threshold_study.json
    already disagree by a few edges.

The v2 path implements no alerting, so nothing acts on these values today. They
must not be wired to anything that alerts until both points are resolved.

`InferenceEngine`'s default `threat_threshold=0.75` is a PACKAGE DEFAULT, not a
fitted value, and is not adopted here. The engine applies no threshold to
`WindowResult.flows`; the gate is applied in the backend, where its provenance
is recorded.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Field names expected in ML/threshold_study.json. Named here so that when the
# file arrives, a missing key fails loudly instead of silently falling back.
_KEY_BINARY_GATE = "binary_gate"
_KEY_ALERT_MIN_FLOWS = "alert_min_flows"
_KEY_ALERT_WINDOW_SECONDS = "alert_window_seconds"


class OperatingPointError(RuntimeError):
    """Raised when threshold_study.json exists but cannot be trusted."""


@dataclass(frozen=True)
class OperatingPoints:
    """Fitted decision thresholds, or an explicit record that there are none."""

    #: P(attack) = 1 - P(BENIGN) above which a flow counts as an attack flow.
    binary_gate: float | None = None
    #: How many gated flows must appear in one window before an alert is raised.
    alert_min_flows: int | None = None
    #: The window the alert rule is counted over, in seconds.
    alert_window_seconds: int | None = None
    #: Provenance, for /health and INTEGRATION.md.
    # ASCII only: this string reaches logs and API responses, and a console on a
    # cp1252 default codec mangles anything outside it.
    source: str = "TODO: unverified - ML/threshold_study.json not present"
    #: Per-field citation: field name -> the key it was read from.
    citations: dict[str, str] | None = None

    @property
    def verified(self) -> bool:
        """True only when every decision threshold came from a real file.

        The backend must not raise an alert while this is False: an alert is a
        claim about precision, and there is no measured precision behind an
        invented threshold.
        """
        return (
            self.binary_gate is not None
            and self.alert_min_flows is not None
            and self.alert_window_seconds is not None
        )

    def describe(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "binary_gate": self.binary_gate,
            "alert_min_flows": self.alert_min_flows,
            "alert_window_seconds": self.alert_window_seconds,
            "source": self.source,
            "citations": self.citations or {},
        }


def load_operating_points(model_dir: str | Path) -> OperatingPoints:
    """Read `threshold_study.json` if present; otherwise return the unverified set.

    A missing file is NOT an error — it is the current, known state, and the
    backend degrades to "score but do not alert". A file that is present but
    malformed IS an error, because a half-read threshold is worse than none.
    """
    path = Path(model_dir) / "threshold_study.json"
    if not path.is_file():
        return OperatingPoints()  # every field None; verified is False

    try:
        study = json.loads(path.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OperatingPointError(f"{path} is present but unreadable: {exc}") from exc

    if not isinstance(study, dict):
        raise OperatingPointError(f"{path} is not a JSON object.")

    missing = [k for k in (_KEY_BINARY_GATE, _KEY_ALERT_MIN_FLOWS, _KEY_ALERT_WINDOW_SECONDS)
               if k not in study]
    if missing:
        raise OperatingPointError(
            f"{path} is missing required key(s) {missing}. Expected "
            f"{_KEY_BINARY_GATE!r}, {_KEY_ALERT_MIN_FLOWS!r} and "
            f"{_KEY_ALERT_WINDOW_SECONDS!r}. Refusing to half-read a threshold."
        )

    gate = float(study[_KEY_BINARY_GATE])
    min_flows = int(study[_KEY_ALERT_MIN_FLOWS])
    window = int(study[_KEY_ALERT_WINDOW_SECONDS])

    if not 0.0 < gate < 1.0:
        raise OperatingPointError(f"{path}: {_KEY_BINARY_GATE}={gate} is not a probability.")
    if min_flows < 1:
        raise OperatingPointError(f"{path}: {_KEY_ALERT_MIN_FLOWS}={min_flows} must be >= 1.")
    if window < 1:
        raise OperatingPointError(f"{path}: {_KEY_ALERT_WINDOW_SECONDS}={window} must be >= 1.")

    return OperatingPoints(
        binary_gate=gate,
        alert_min_flows=min_flows,
        alert_window_seconds=window,
        source=str(path),
        citations={
            "binary_gate": f"{path.name}:{_KEY_BINARY_GATE}",
            "alert_min_flows": f"{path.name}:{_KEY_ALERT_MIN_FLOWS}",
            "alert_window_seconds": f"{path.name}:{_KEY_ALERT_WINDOW_SECONDS}",
        },
    )

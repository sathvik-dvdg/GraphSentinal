# [WSL2]
"""Operating points — the thresholds that turn model scores into decisions.

WHY THESE ARE NOT CONSTANTS IN THIS FILE

A binary gate and an alert rule are claims about measured precision and recall.
`ML/threshold_study.json` is the file that holds the fitted values, and it does
not currently exist in this repo. Until it does, every operating point here is
`TODO: unverified` and the backend REFUSES TO ALERT rather than invent one.

Three numbers have been discussed for this integration and none of them is
usable as a fitted value today:

  0.500   the binary attack gate, said to be fitted on validation at
          precision 0.9910 / recall 0.9989. NOT traceable to any file in this
          repo. (Corroboration, not verification: that precision/recall pair
          implies F1 0.9949343, against model_card.json's VALIDATION
          `edge_binary_f1` of 0.9950064 — a 7.2e-05 gap consistent with 4-dp
          rounding. That makes the PAIR plausible; it says nothing about the
          threshold being 0.500.)

  >= 5    flows over the gate in a 60 s window, said to give test precision
          1.000 across 486 attack-free windows. NOT traceable to any file.

  0.75    `InferenceEngine`'s default `threat_threshold`. This is a PACKAGE
          DEFAULT, not a fitted value. It is not adopted here, silently or
          otherwise. The engine is deliberately driven with no threshold at all
          (it applies none to `WindowResult.flows`), so the gate lives here.

When `threshold_study.json` lands, `load_operating_points()` reads it and the
comment on each field records the exact key it came from.
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

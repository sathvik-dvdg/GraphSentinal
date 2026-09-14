# [WSL2]
"""GraphSentinel v2 runtime state: contract, policy, operating points.

This is the object `main.py` builds at startup and everything else reads. It
exists so there is exactly ONE place that decides whether the v2 path is safe to
run, rather than each handler re-deciding.

STARTUP CONTRACT

When `gs2_enabled` is on and `gs2_require_contract` is on (both default for any
real deployment), a missing `model_card.json`, a `contract_version` other than
the one this code was written against, or a mitigation policy that disagrees
with the card's class list, all REFUSE THE BOOT. None of these degrade to a
warning: every one of them means the backend would be attaching wrong labels to
real traffic, and an operator has no way to notice that from the output.

CLAIMS THIS BACKEND MUST NOT MAKE — anywhere, in code, comments, logs or API
responses:

  * zero-day or novel-attack detection. The split protocol is `episode`; train
    and test can share an attack burst. `ML/MANIFEST.json` says so in as many
    words: "these are NOT novel-attack numbers".
  * real-time performance. Nothing here has been measured against a latency
    budget, and the monitor polls on a 5 s timer.
  * production readiness.
  * host/node-level attack attribution. The node head's test binary F1 is
    0.1407, PR-AUC below base rate for three of four attack classes. The node
    head is never read; `WindowResult.detections` is deliberately discarded.
  * Botnet detection. Test F1 0.0000, PR-AUC 0.0024, all 266 test edges
    predicted BENIGN, unstable across identical reruns. A Botnet label that
    reaches the API is documented as unreliable and never enforced on.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.models.schemas import NON_MODEL_ATTACK_LABELS
from app.services.mitigation_policy import MitigationPolicy, PolicyError, build_policy
from app.services.model_contract import ContractError, ModelContract, load_contract
from app.services.operating_points import OperatingPointError, OperatingPoints, load_operating_points

_log = logging.getLogger("graphsentinel.inference_v2")

#: Attack classes whose labels must be reported as unreliable wherever surfaced.
#: Derived from measured numbers in ML/test_report.json, not from taste.
UNRELIABLE_CLASSES: dict[str, str] = {
    "Botnet": (
        "UNRELIABLE: test F1 0.0000, PR-AUC 0.0024, all 266 test edges predicted "
        "BENIGN, unstable across identical reruns. Do not act on this label."
    ),
}


@dataclass(frozen=True)
class InferenceV2State:
    """Validated v2 runtime state. Built once at startup."""

    enabled: bool
    contract: ModelContract | None = None
    policy: MitigationPolicy | None = None
    operating_points: OperatingPoints | None = None
    disabled_reason: str | None = None

    @property
    def ready(self) -> bool:
        """True when the contract and policy loaded. Says nothing about whether
        the inference SERVICE is reachable — that is the client's business."""
        return self.enabled and self.contract is not None and self.policy is not None

    @property
    def can_alert(self) -> bool:
        """True only when a fitted operating point exists to gate on.

        Without `ML/threshold_study.json` there is no measured precision behind
        any threshold, so the backend scores flows and reports them but raises
        no alerts and creates no incidents on the v2 path.
        """
        return self.ready and bool(self.operating_points and self.operating_points.verified)

    def class_note(self, class_name: str) -> str | None:
        """Reliability caveat for a class label, or None if it has none."""
        return UNRELIABLE_CLASSES.get(class_name)

    def validate_label(self, label: str) -> str:
        """Validate an attack label AT THE SEAM that produces it.

        `NodeData.attack_type` and `LinkData.attack_type` were widened from a
        closed Literal to `Optional[str]` so a new taxonomy does not 500 the
        graph endpoint on response validation. That moved the check here, where
        an out-of-contract label fails at its ORIGIN and names what produced it,
        instead of surfacing as a serialisation error three layers away.

        Accepts any class the loaded card declares, plus the non-model labels
        (manual operator actions, the v1 heuristic fallback).
        """
        if label in NON_MODEL_ATTACK_LABELS:
            return label
        if self.contract is not None and label in self.contract.classes:
            return label
        declared = list(self.contract.classes) if self.contract else []
        raise ValueError(
            f"attack label {label!r} is neither a class declared by the model "
            f"card ({declared}) nor a non-model label "
            f"({sorted(NON_MODEL_ATTACK_LABELS)}). Refusing to emit it."
        )

    def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "reason": self.disabled_reason}
        contract = self.contract
        return {
            "enabled": True,
            "ready": self.ready,
            "disabled_reason": self.disabled_reason,
            "contract": None if contract is None else {
                "version": contract.contract_version,
                "classes": list(contract.classes),
                "node_features": contract.node_feature_count,
                "edge_features": contract.edge_feature_count,
                "card_sha256": contract.card_sha256,
                # model_card.json's metrics are VALIDATION on cards that predate
                # the `metrics_split` key. Headline numbers come from
                # ML/test_report.json. Recorded so nobody quotes the wrong split.
                "metrics_split": contract.metrics_split or "validation (unlabelled card)",
            },
            "policy": None if self.policy is None else {
                "enforceable": [c for c in self.policy.table if self.policy.is_enforceable(c)],
                "alert_only": list(self.policy.alert_only_classes),
            },
            "operating_points": (
                self.operating_points.describe() if self.operating_points else None
            ),
            "can_alert": self.can_alert,
            "unreliable_classes": dict(UNRELIABLE_CLASSES),
        }


def verify_service_contract(state: InferenceV2State, served: dict[str, Any]) -> None:
    """Refuse to run if the inference service serves a different contract.

    The backend validates `model_card.json` on its own disk; the service labels
    flows with ITS copy. If the two disagree on version or class order, the
    backend would map class names and caveats onto labels produced under a
    different list. Raises ContractError on mismatch.
    """
    if state.contract is None:
        return
    served_version = served.get("contract_version")
    served_classes = (served.get("outputs") or {}).get("classes")
    if served_version != state.contract.contract_version or list(served_classes or []) != list(state.contract.classes):
        raise ContractError(
            "The inference service is serving a different model contract than the "
            "backend validated.\n"
            f"  backend : version={state.contract.contract_version!r} classes={list(state.contract.classes)}\n"
            f"  service : version={served_version!r} classes={served_classes}\n"
            "Both must read the same model_card.json."
        )


def build_state() -> InferenceV2State:
    """Load and validate everything the v2 path needs. Raises to refuse the boot.

    Raises ContractError / PolicyError / OperatingPointError when
    `gs2_require_contract` is set. With it unset, the failure is logged loudly
    and the v2 path is left disabled — it never runs half-configured.
    """
    if not settings.gs2_enabled:
        return InferenceV2State(enabled=False, disabled_reason="gs2_enabled is false")

    model_dir = settings.resolved_gs2_model_dir
    try:
        contract = load_contract(model_dir)
        policy = build_policy(contract)
        points = load_operating_points(model_dir)
    except (ContractError, PolicyError, OperatingPointError) as exc:
        if settings.gs2_require_contract:
            # Refuse the boot. Mislabelling traffic silently is the worse outcome.
            raise
        _log.error("v2 inference DISABLED — contract/policy failed to load: %s", exc)
        return InferenceV2State(enabled=False, disabled_reason=str(exc))

    unknown = [c for c in UNRELIABLE_CLASSES if c not in contract.classes]
    if unknown:
        # Not fatal: a caveat for a class that no longer exists is stale
        # documentation, not a mislabelling risk. But say so.
        _log.warning(
            "UNRELIABLE_CLASSES names %s, which the contract does not declare. "
            "Stale caveat — review it.", unknown,
        )

    _log.info(
        "v2 contract %s loaded from %s (sha256 %s); classes=%s",
        contract.contract_version, contract.card_path, contract.card_sha256[:16],
        list(contract.classes),
    )
    for class_name, note in UNRELIABLE_CLASSES.items():
        if class_name in contract.classes:
            _log.warning("class %s: %s", class_name, note)
    if not points.verified:
        _log.warning(
            "No fitted operating points (%s). The v2 path will SCORE flows but "
            "raise NO alerts and create NO incidents: an alert is a claim about "
            "precision, and there is no measured precision behind an unfitted "
            "threshold. InferenceEngine's default threat_threshold=0.75 is a "
            "package default and is deliberately NOT adopted here.",
            points.source,
        )

    return InferenceV2State(
        enabled=True, contract=contract, policy=policy, operating_points=points,
    )

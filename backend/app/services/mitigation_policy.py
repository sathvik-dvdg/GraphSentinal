# [WSL2]
"""Mitigation policy, keyed off the model card's class list.

WHY THIS IS NOT THE PACKAGE'S `MITIGATION_POLICY`

`graphsentinel.inference.sdn.MITIGATION_POLICY` is a module-level dict keyed on
the OLD six-class taxonomy (`DDoS`, `PortScan`, `Botnet`, `SSHBrute`,
`DoSHulk`). The live model uses the five-class `flood4` taxonomy
(`BENIGN`, `Volumetric_Flood`, `PortScan`, `BruteForce`, `Botnet`). Measured
against the live contract:

    idx class              has policy?                   action
      1  Volumetric_Flood  NO  -- can NEVER fire a rule  -
      2  PortScan          YES                           drop
      3  BruteForce        NO  -- can NEVER fire a rule  -
      4  Botnet            YES                           drop_and_quarantine
    DEAD keys (no such class): ['DDoS', 'SSHBrute', 'DoSHulk']

`SDNTranslator.translate()` does `MITIGATION_POLICY.get(cls)` and `continue`s on
None — silently, with no log line. So the two highest-volume attack classes
could never produce a rule, while the ONLY two that could were the model's best
class (PortScan, test F1 0.980) and its worst (Botnet, test F1 0.0000).

This module rebuilds the table from `model_card.json` instead, so it cannot
drift from the taxonomy again:

  * every non-BENIGN class in the card MUST have an entry, or startup fails;
  * every entry MUST name a class in the card, or startup fails;
  * "we know about this class and deliberately do not enforce on it" is an
    explicit `alert_only` entry, never an absent key — a deliberate decision and
    a forgotten one must not look identical.

The result is passed to `SDNTranslator`; the module global is never mutated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.model_contract import BENIGN_CLASS, ModelContract

# Actions the SDN translator understands. `alert_only` is ours: it means the
# class is recognised, scored and reported, but never turned into a rule.
ACTION_ALERT_ONLY = "alert_only"

# ---------------------------------------------------------------------------
# Per-class mitigation, keyed by the CARD's class names.
#
# Every entry is a deliberate decision recorded against a measured number from
# ML/test_report.json (the TEST split — model_card.json's identically-named
# metrics are VALIDATION and read ~0.05 macro F1 higher).
#
#   Volumetric_Flood  test F1 0.9910, precision 0.9998, recall 0.9823
#   PortScan          test F1 0.9800, precision 0.9609, recall 1.0000
#   BruteForce        test F1 0.5508, precision 1.0000, recall 0.3801
#   Botnet            test F1 0.0000, precision 0.0,    recall 0.0
#
# `min_conf` values below are INHERITED from the training package's own table
# for the classes that had one, and are NOT fitted operating points. They are
# not the subject of ML/threshold_study.json and must not be presented as
# tuned. See the operating-point handling in inference_client.py, which is a
# separate concern and is currently unverified.
# ---------------------------------------------------------------------------
_POLICY_BY_CLASS: dict[str, dict[str, Any]] = {
    "Volumetric_Flood": dict(
        action="meter", idle=60, hard=600, priority=40_000, min_conf=0.90,
        meter_kbps=1_000,
        rationale="Rate-limit rather than drop: the victim still has to serve "
                  "everyone else. Inherited from the old DDoS/DoSHulk entries, "
                  "which flood4 merges into this one class.",
    ),
    "PortScan": dict(
        action="drop", idle=30, hard=300, priority=45_000, min_conf=0.85,
        rationale="Short TTL — scans are cheap to re-run from a new source. "
                  "This is the model's strongest class (test F1 0.9800).",
    ),
    "BruteForce": dict(
        action="drop_port", idle=120, hard=1800, priority=48_000, min_conf=0.85,
        rationale="Drop only the targeted service port so the host stays "
                  "reachable otherwise. Test recall is 0.3801 — this class "
                  "MISSES about two thirds of real brute force; absence of a "
                  "rule is not evidence of absence of an attack.",
    ),
    # DELIBERATE NON-ENFORCEMENT. Botnet is trained but not learned: test F1
    # 0.0000, PR-AUC 0.0024, and all 266 Botnet edges in the test split were
    # predicted BENIGN. The number is also unstable across identical reruns.
    # It must never carry an enforcement action. Recorded as an explicit entry
    # rather than an omission so nobody "fixes" a missing key by adding one.
    "Botnet": dict(
        action=ACTION_ALERT_ONLY, idle=0, hard=0, priority=0, min_conf=1.01,
        rationale="NOT ENFORCEABLE. Test F1 0.0000, PR-AUC 0.0024, all 266 test "
                  "edges predicted BENIGN, unstable across identical reruns. Any "
                  "Botnet label returned by the API is unreliable and must be "
                  "documented as such. min_conf > 1.0 makes it unreachable even "
                  "if the action were changed by accident.",
    ),
}


class PolicyError(RuntimeError):
    """Raised when the policy table and the model contract disagree. Fatal."""


@dataclass(frozen=True)
class MitigationPolicy:
    """Validated, card-derived policy. `table` is what SDNTranslator consumes."""

    table: dict[str, dict[str, Any]] = field(default_factory=dict)

    def for_class(self, class_name: str) -> dict[str, Any] | None:
        return self.table.get(class_name)

    def is_enforceable(self, class_name: str) -> bool:
        entry = self.table.get(class_name)
        return bool(entry) and entry.get("action") != ACTION_ALERT_ONLY

    @property
    def alert_only_classes(self) -> tuple[str, ...]:
        return tuple(
            name for name, e in self.table.items() if e.get("action") == ACTION_ALERT_ONLY
        )


def build_policy(contract: ModelContract) -> MitigationPolicy:
    """Build the policy for exactly the classes the card declares.

    Raises PolicyError if a card class has no entry, or an entry names a class
    the card does not declare. Both are startup failures: the first means a real
    attack class would silently never produce a rule, the second means the table
    is keyed on a taxonomy that is no longer live.
    """
    card_classes = set(contract.classes)

    missing = [c for c in contract.attack_classes if c not in _POLICY_BY_CLASS]
    if missing:
        raise PolicyError(
            f"No mitigation policy entry for class(es) {missing} declared by "
            f"{contract.card_path}.\n"
            "A class with no entry is silently dropped by SDNTranslator and can "
            "never produce a rule. If non-enforcement is intended, add an explicit "
            f"{ACTION_ALERT_ONLY!r} entry — do not leave the key absent."
        )

    stale = [c for c in _POLICY_BY_CLASS if c not in card_classes]
    if stale:
        raise PolicyError(
            f"Mitigation policy has entries for {stale}, which are not classes in "
            f"{contract.card_path} (declared: {list(contract.classes)}).\n"
            "These are dead keys from a previous taxonomy and would never match."
        )

    if BENIGN_CLASS in _POLICY_BY_CLASS:
        raise PolicyError(
            f"{BENIGN_CLASS!r} must not have a mitigation entry — benign traffic "
            "is never enforced against."
        )

    # Ordered by the card so iteration order is the contract's, not a dict literal's.
    table = {c: dict(_POLICY_BY_CLASS[c]) for c in contract.attack_classes}
    return MitigationPolicy(table=table)

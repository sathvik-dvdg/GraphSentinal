# [WSL2]
"""Mitigation policy, keyed off the model card's class list.

THIS IS THE ONLY MITIGATION POLICY.

It is sent, in wire form (`MitigationPolicy.wire()`), with every request to the
inference service, whose translator has no policy of its own and makes no rule
without one. The service echoes the policy's digest; rules are accepted only
when the echo matches (`analysis_pipeline_v2`). Rules stay dry-run.

WHY THE PACKAGE'S TABLE WAS DELETED (2026-10-04)

`graphsentinel.inference.sdn.MITIGATION_POLICY` was a module-level dict keyed on
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

The result is validated, reported at /health, and sent to the translator with
every request. The module global is never mutated.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from app.services.model_contract import BENIGN_CLASS, ModelContract

# Actions the SDN translator understands. `alert_only` is ours: it means the
# class is recognised, scored and reported, but never turned into a rule.
ACTION_ALERT_ONLY = "alert_only"

# ---------------------------------------------------------------------------
# Per-class mitigation, keyed by the CARD's class names.
#
# Every entry is a deliberate decision recorded against measured numbers from
# ML/test_report.json (TEST split; model retrained 2026-10-03 under the fixed
# timestamp parse; model_card.json's identically-named metrics are VALIDATION).
#
#   Volumetric_Flood  test F1 0.9617, precision 0.9263, recall 1.0000
#   PortScan          test F1 0.2598  } the model does not separate these two:
#   BruteForce        test F1 0.0000  } 17,909 of 23,812 PortScan edges are
#                                       predicted BruteForce, 904 of 918
#                                       BruteForce edges PortScan
#   Botnet            no test edges; 0 of 168 correct on the Phase 2b sample
#
# What these floors let through is measured in MODEL_BEHAVIOUR.md section 6
# (test split) and section 1 (live, on the sample). In short: most correct
# Volumetric_Flood predictions clear their floor, almost no wrong-class or
# benign prediction clears any, and no PortScan edge mislabelled BruteForce
# reaches 0.85. The class head is unreliable and these floors absorb almost all
# of it: do not lower them.
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
    # DELIBERATE NON-ENFORCEMENT since 2026-10-05; it was `drop`. No CORRECT
    # PortScan prediction reaches its floor in either population the model has
    # been scored on, the test split or the live sample (MODEL_BEHAVIOUR.md
    # sections 6 and 1.3). The only PortScan predictions that do reach it are
    # wrong ones: on the test split, true BruteForce edges labelled PortScan.
    # So `drop` could only ever have fired on the wrong class, and this removes
    # that; on the live sample it changes the withholding reason and nothing
    # else. The floor is unchanged.
    #
    # This suppresses LESS than the decision it implements. Suppressing BOTH
    # PortScan and BruteForce was approved when the evidence was "no correct
    # rule from either". That was narrowed, on later evidence, to PortScan
    # only. BruteForce stays enforceable because the live rule check then
    # admitted BruteForce rules on genuinely BruteForce flows
    # (ML/live_rule_check.json), and because its zero test F1 is measured on the
    # one class whose test windows hold no benign traffic, which section 5.1's
    # pre-registered measurement says is not the representative condition:
    # live traffic is mixed.
    "PortScan": dict(
        action=ACTION_ALERT_ONLY, idle=30, hard=300, priority=45_000, min_conf=0.85,
        rationale="NOT ENFORCEABLE. No correct PortScan prediction reaches this "
                  "floor on the test split or on the live sample, and the model "
                  "does not separate PortScan from BruteForce. Recognised, "
                  "scored and reported; never turned into a rule.",
    ),
    "BruteForce": dict(
        action="drop_port", idle=120, hard=1800, priority=48_000, min_conf=0.85,
        rationale="Drop only the targeted service port so the host stays "
                  "reachable otherwise. Test F1 0.0000: the model labels real "
                  "brute force as PortScan; absence of a rule is not evidence "
                  "of absence of an attack.",
    ),
    # DELIBERATE NON-ENFORCEMENT. Botnet is trained but not learned: the
    # retrained model's test split holds no Botnet edges, and on the Phase 2b
    # sample 0 of 168 are correct; the epoch-31 model predicted all 266 of its
    # test Botnet edges BENIGN, unstably across identical reruns.
    # It must never carry an enforcement action. Recorded as an explicit entry
    # rather than an omission so nobody "fixes" a missing key by adding one.
    "Botnet": dict(
        action=ACTION_ALERT_ONLY, idle=0, hard=0, priority=0, min_conf=1.01,
        rationale="NOT ENFORCEABLE. 0 of 168 Botnet edges correct on the "
                  "Phase 2b sample (no Botnet edges in the test split). Any "
                  "Botnet label returned by the API is unreliable and must be "
                  "documented as such. min_conf > 1.0 makes it unreachable even "
                  "if the action were changed by accident.",
    ),
}


class PolicyError(RuntimeError):
    """Raised when the policy table and the model contract disagree. Fatal."""


@dataclass(frozen=True)
class MitigationPolicy:
    """Validated, card-derived policy. `wire()` is what the translator receives."""

    table: dict[str, dict[str, Any]] = field(default_factory=dict)

    #: The keys the translator reads. `rationale` is documentation and stays here.
    WIRE_KEYS = ("action", "idle", "hard", "priority", "min_conf", "meter_kbps")

    def wire(self) -> dict[str, dict[str, Any]]:
        """The policy as sent to the inference service: no rationale, and
        `meter_kbps` only where the entry has one."""
        return {c: {k: e[k] for k in self.WIRE_KEYS if k in e} for c, e in self.table.items()}

    def wire_sha256(self) -> str:
        """Same canonical digest as graphsentinel.inference.sdn.policy_sha256."""
        blob = json.dumps(self.wire(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

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
            "A class with no entry can never produce a rule; the translator "
            "withholds it as 'no_policy'. If non-enforcement is intended, add an explicit "
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

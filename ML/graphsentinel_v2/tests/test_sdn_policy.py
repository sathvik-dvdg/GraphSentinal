"""The rule path takes its policy from the caller, and only from the caller.

The inference service used to carry its own mitigation table keyed on the
retired six-class taxonomy, under which Botnet was ``drop_and_quarantine`` at
0.80 while the backend's validated policy, which says Botnet is never enforced,
reached nothing. These tests fail if that table comes back, if a floor other
than the policy's admits a rule, or if a rule can leave the translator in
dry-run.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphsentinel.config import CLASS_NAMES, Config  # noqa: E402
from graphsentinel.inference import sdn  # noqa: E402
from graphsentinel.inference.sdn import (  # noqa: E402
    PolicyRejected, SDNTranslator, policy_sha256, validate_policy,
)

#: The backend's policy for the five-class taxonomy, in wire form (no rationale).
#: Values as in backend/app/services/mitigation_policy.py.
POLICY = {
    "Volumetric_Flood": dict(action="meter", idle=60, hard=600, priority=40_000,
                             min_conf=0.90, meter_kbps=1_000),
    "PortScan": dict(action="alert_only", idle=30, hard=300, priority=45_000, min_conf=0.85),
    "BruteForce": dict(action="drop_port", idle=120, hard=1800, priority=48_000, min_conf=0.85),
    "Botnet": dict(action="alert_only", idle=0, hard=0, priority=0, min_conf=1.01),
}


@pytest.fixture(autouse=True)
def flood4():
    """The live five-class taxonomy, restored afterwards: CLASS_NAMES is a
    module-level list that Config mutates in place."""
    saved = list(CLASS_NAMES)
    cfg = Config()
    cfg.data.taxonomy = "flood4"
    cfg.sync_taxonomy()
    assert list(CLASS_NAMES) == ["BENIGN", "Volumetric_Flood", "PortScan", "BruteForce", "Botnet"]
    yield
    CLASS_NAMES[:] = saved


def _one_edge(cls: str, p: float, node_threat: float = 0.9):
    """One flow 10.0.0.1 -> 10.0.0.2 predicted `cls` with probability `p`."""
    k = list(CLASS_NAMES).index(cls)
    ep = torch.full((1, len(CLASS_NAMES)), (1.0 - p) / (len(CLASS_NAMES) - 1))
    ep[0, k] = p
    npb = torch.zeros(2, len(CLASS_NAMES))
    npb[:, 0] = 1.0 - node_threat
    npb[:, k] = node_threat
    return dict(edge_probs=ep, node_probs=npb, edge_index=torch.tensor([[0], [1]]),
                node_ips=["10.0.0.1", "10.0.0.2"], dst_ports=[22], src_ports=[40000],
                protocols=[6], real_edge_mask=np.ones(1, bool))


def test_the_stale_six_class_table_is_gone():
    assert not hasattr(sdn, "MITIGATION_POLICY")


def test_a_rule_carries_the_policy_floor_not_another():
    rules = SDNTranslator(policy=POLICY).translate(**_one_edge("BruteForce", 0.95))
    assert len(rules) == 1 and rules[0].policy_floor == 0.85 and rules[0].action == "drop_port"
    # the same flow under a stricter policy is withheld: the floor is the caller's
    stricter = {**POLICY, "BruteForce": {**POLICY["BruteForce"], "min_conf": 0.97}}
    t = SDNTranslator(policy=stricter)
    assert t.translate(**_one_edge("BruteForce", 0.95)) == []
    assert t.withheld[0]["reason"] == "below_floor" and t.withheld[0]["policy_floor"] == 0.97


@pytest.mark.parametrize("p", [0.5, 0.86, 0.999])
def test_portscan_is_alert_only_and_admits_nothing_above_its_floor_either(p):
    """PortScan was `drop` until 2026-10-05. Its floor is unchanged; it is the
    action that makes it unenforceable, so a confident prediction is withheld as
    suppressed, not as below the floor."""
    t = SDNTranslator(policy=POLICY)
    assert POLICY["PortScan"]["min_conf"] == 0.85
    assert t.translate(**_one_edge("PortScan", p)) == []
    assert t.withheld[0]["reason"] == "class_suppressed"


def test_below_the_floor_no_rule_and_exactly_one_withholding():
    t = SDNTranslator(policy=POLICY)
    assert t.translate(**_one_edge("BruteForce", 0.62)) == []
    assert len(t.withheld) == 1
    w = t.withheld[0]
    assert (w["reason"], w["attack_class"], w["policy_floor"]) == ("below_floor", "BruteForce", 0.85)
    assert t.withheld_summary() == {"BruteForce": {"below_floor": 1}}


def test_no_policy_means_no_rules():
    t = SDNTranslator()
    assert t.translate(**_one_edge("PortScan", 0.99)) == []
    assert t.withheld[0]["reason"] == "no_policy" and t.policy_sha256 is None


@pytest.mark.parametrize("p", [0.5, 0.9, 0.999, 1.0])
def test_botnet_admits_nothing_at_any_confidence(p):
    t = SDNTranslator(policy=POLICY)
    assert t.translate(**_one_edge("Botnet", p, node_threat=1.0)) == []
    assert t.withheld[0]["reason"] == "class_suppressed"
    # and were its action ever changed by accident, 1.01 is still unreachable
    t = SDNTranslator(policy={**POLICY, "Botnet": {**POLICY["Botnet"], "action": "drop"}})
    assert t.translate(**_one_edge("Botnet", p, node_threat=1.0)) == []
    assert t.withheld[0]["reason"] == "below_floor"


def test_dry_run_writes_nothing_at_the_boundary():
    t = SDNTranslator(policy=POLICY)
    rules = t.translate(**_one_edge("BruteForce", 0.95))
    assert rules and t.dry_run is True
    written = []
    report = t.install(rules, writer=written.append)
    assert written == [] and report == {"dry_run": True, "installed": 0, "would_install": 1}
    t.dry_run = False                      # even then, installation is refused
    with pytest.raises(RuntimeError, match="not enabled"):
        t.install(rules, writer=written.append)
    assert written == []


def test_only_the_live_taxonomy_is_known_to_the_rule_path():
    for retired in ("DDoS", "SSHBrute", "DoSHulk"):
        with pytest.raises(PolicyRejected, match="not attack classes of the live taxonomy"):
            validate_policy({**POLICY, retired: dict(action="drop", idle=1, hard=1,
                                                     priority=1, min_conf=0.5)})
    with pytest.raises(PolicyRejected):
        validate_policy({"BENIGN": dict(action="drop", idle=1, hard=1, priority=1, min_conf=0.5)})
    with pytest.raises(PolicyRejected, match="lacks"):
        validate_policy({"PortScan": dict(action="drop")})


def test_policy_digest_is_the_one_the_backend_computes():
    """backend/tests/test_v2_rule_wiring.py pins the same literal: the backend
    accepts rules only when the service echoes this digest."""
    assert policy_sha256(POLICY) == EXPECTED_POLICY_SHA256


def test_engine_echoes_the_policy_it_was_given():
    from graphsentinel.inference.engine import InferenceEngine
    from graphsentinel.models.net import build_model

    cfg = Config()
    cfg.data.taxonomy = "flood4"
    cfg.sync_taxonomy()
    eng = InferenceEngine(build_model(cfg), cfg)
    rng = np.random.default_rng(0)
    recs = [{"Source IP": f"10.0.0.{1 + i % 6}", "Destination IP": f"10.0.1.{1 + (i * 3) % 4}",
             "Source Port": int(rng.integers(1024, 65535)),
             "Destination Port": int(rng.integers(1, 1024)), "Protocol": 6,
             "t": 1_500_000_000 + i, "Flow Duration": 1000.0, "Total Fwd Packets": 3,
             "Total Backward Packets": 0, "Total Length of Fwd Packets": 300.0,
             "Total Length of Bwd Packets": 0.0} for i in range(40)]
    eng.ingest(recs, policy=POLICY)
    res = eng.flush(policy=POLICY)
    assert res.policy_sha256 == policy_sha256(POLICY) and res.dry_run is True
    assert res.to_dict()["policy_sha256"] == policy_sha256(POLICY)
    eng.ingest(recs[:5])
    res = eng.flush()                       # no policy: no rules, digest None
    assert res.policy_sha256 is None and res.rules == []


#: Pinned literal, also in backend/tests/test_v2_rule_wiring.py.
EXPECTED_POLICY_SHA256 = "e99290226e2d4ad9b8293ffae19bbf53c2bfc673dde11aae4abd9bcff1c8f717"

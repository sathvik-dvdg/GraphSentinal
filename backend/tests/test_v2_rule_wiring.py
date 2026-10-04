# [WSL2]
"""The validated mitigation policy is the only source of v2 rules.

The backend sends `MitigationPolicy.wire()` with every batch; the service's
translator has no table of its own and echoes the digest of the policy it
applied. These tests fail if the backend stops sending its policy, accepts
rules made under any other policy, drops the withholding log, or lets a v2 rule
anywhere near the enforcement agent.

DATA: the policy is built from the real ML/model_card.json. The service is
faked at the client boundary; its payloads have the shape
graphsentinel.inference.engine.WindowResult.to_dict() produces.
"""
from __future__ import annotations

import logging

import pytest

from app.config import settings
from app.services import analysis_pipeline_v2 as pipeline
from app.services.enforcement_agent import EnforcementAgent
from app.services.inference_client import WindowOutcome
from app.services.inference_v2 import InferenceV2State
from app.services.mitigation_policy import build_policy
from app.services.model_contract import load_contract
from app.services.self_healing import SelfHealingEngine

#: Pinned in ML/graphsentinel_v2/tests/test_sdn_policy.py too: the package's
#: policy_sha256 over the same wire policy.
EXPECTED_POLICY_SHA256 = "d030e547ae90aafe6611b87adc6733d288a1669c7945102e61f8222c5c26a0b2"


@pytest.fixture(scope="module")
def state():
    contract = load_contract(settings.resolved_gs2_model_dir)
    return InferenceV2State(enabled=True, contract=contract, policy=build_policy(contract))


def _rule(cls="Volumetric_Flood", floor=0.90, action="meter"):
    return {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "protocol": 6, "dst_port": 80,
            "src_port": 40000, "attack_class": cls, "confidence": 0.94,
            "node_confidence": 0.9, "action": action, "priority": 40000,
            "idle_timeout": 60, "hard_timeout": 600, "policy_floor": floor}


class FakeClient:
    """Records what the backend sent; returns one closed window."""

    def __init__(self, window: dict):
        self.window = window
        self.sent_policy = "never called"
        self.contract_verified = True
        self.unscored_rate = 0.0

    def submit(self, flows, observed_at=None, policy=None):
        self.sent_policy = policy
        return [WindowOutcome.from_payload(self.window)]


def _window(policy_sha256, rules=(), withheld=None, dry_run=True):
    return {"window_start": 0.0, "window_end": 60.0, "n_flows": 3, "n_hosts": 2,
            "unscored": False, "flows": [], "rules": list(rules),
            "withheld_summary": withheld or {}, "withheld": [],
            "policy_sha256": policy_sha256, "dry_run": dry_run}


@pytest.fixture()
def no_enforcement(monkeypatch):
    """Any path from a v2 rule to the switch fails the test."""
    def refuse(*_a, **_k):
        raise AssertionError("a v2 rule reached the enforcement path")
    monkeypatch.setattr(EnforcementAgent, "block_ip", refuse)
    monkeypatch.setattr(SelfHealingEngine, "block_ip", refuse)


def _score(monkeypatch, state, window):
    fake = FakeClient(window)
    monkeypatch.setattr(pipeline.InferenceClient, "get_instance", classmethod(lambda cls: fake))
    return fake, pipeline.score_flows([object()], state)


def test_wire_policy_is_the_backend_policy_and_its_digest_is_pinned(state):
    wire = state.policy.wire()
    assert set(wire) == set(state.contract.attack_classes)
    assert all("rationale" not in e for e in wire.values())
    assert wire["Botnet"]["action"] == "alert_only" and wire["Botnet"]["min_conf"] == 1.01
    assert state.policy.wire_sha256() == EXPECTED_POLICY_SHA256


def test_the_backend_sends_its_policy_and_accepts_rules_made_under_it(
        monkeypatch, state, no_enforcement):
    fake, out = _score(monkeypatch, state, _window(EXPECTED_POLICY_SHA256, rules=[_rule()]))
    assert fake.sent_policy == state.policy.wire()
    w = out["windows"][0]
    assert w["rules_admitted"] == 1 and w["rules_discarded_reason"] is None
    assert w["rules"][0]["policy_floor"] == 0.90 and w["rules"][0]["dry_run"] is True
    assert w["dry_run"] is True


def test_rules_made_under_another_policy_are_discarded(monkeypatch, state, caplog, no_enforcement):
    stale = _window("f" * 64, rules=[_rule("Botnet", 0.80, "drop_and_quarantine")])
    with caplog.at_level(logging.ERROR, logger="graphsentinel.pipeline_v2"):
        _, out = _score(monkeypatch, state, stale)
    w = out["windows"][0]
    assert w["rules"] == [] and w["rules_admitted"] == 0
    assert "discarded" in w["rules_discarded_reason"]
    assert any("discarded" in r.message for r in caplog.records)
    # an older service that sends no digest at all is treated the same way
    _, out = _score(monkeypatch, state, _window(None, rules=[_rule()]))
    assert out["windows"][0]["rules"] == []


def test_a_withheld_flow_is_logged_once_with_its_reason(monkeypatch, state, caplog, no_enforcement):
    win = _window(EXPECTED_POLICY_SHA256, withheld={"BruteForce": {"below_floor": 1}})
    with caplog.at_level(logging.INFO, logger="graphsentinel.pipeline_v2"):
        _, out = _score(monkeypatch, state, win)
    lines = [r.message for r in caplog.records if "withheld" in r.message]
    assert lines == ["v2 window [0,60]: withheld 1 BruteForce flow(s): below_floor"]
    assert out["windows"][0]["rules_withheld"] == {"BruteForce": {"below_floor": 1}}
    assert out["windows"][0]["rules_admitted"] == 0


def test_a_service_claiming_live_mode_is_refused(monkeypatch, state, no_enforcement):
    _, out = _score(monkeypatch, state, _window(EXPECTED_POLICY_SHA256, rules=[_rule()],
                                                dry_run=False))
    assert out["windows"][0]["rules"] == []
    assert "dry_run=False" in out["windows"][0]["rules_discarded_reason"]

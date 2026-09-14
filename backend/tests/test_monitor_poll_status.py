# [WSL2]
"""Poll status: a failed OVS poll must be distinguishable from a quiet network.

Before this change `parse_ovs_flows` swallowed every failure and returned
normally, so the monitor recorded `last_error = None` and an hour-long daemon
outage looked exactly like an hour of quiet traffic.

DATA. The `failed` path is exercised against a real closed local port: a real
connection failure, no mocked socket. The substituted content is the real
`demo_flows()` generator, whose use is the policy under test.

BLOCKED, deliberately not written: tests for `ok` and `ok_empty`. Both need real
`ovs-ofctl dump-flows` output, which arrives as ML/testdata/ovs_dump_flows.txt.
They must not be written against hand-made dump lines -- hand-made fixtures are
what made the `duration=` default hard to reason about (INTEGRATION.md §8).
"""
from __future__ import annotations

import socket

import pytest

from app.config import settings
from app.mininet_monitor.flow_parser import POLL_FAILED, poll_ovs_flows
from app.mininet_monitor.monitor import V2_REFUSED_NON_OVS, MininetMonitor


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def daemon_down(monkeypatch):
    """Point the parser at a local port nothing listens on."""
    monkeypatch.setattr(settings, "daemon_host", "127.0.0.1")
    monkeypatch.setattr(settings, "daemon_port", _unused_port())


def test_unreachable_daemon_is_reported_as_failed_not_empty(daemon_down):
    result = poll_ovs_flows("s1")

    assert result.status == POLL_FAILED
    assert result.flows == []
    assert result.error, "a failed poll must carry the reason"
    assert result.lines_in_dump is None, "no dump was received"
    assert result.demo_substituted is False, "the parser must never invent traffic"


def test_failed_poll_is_visible_in_monitor_health_with_demo_off(daemon_down, monkeypatch):
    monkeypatch.setattr(settings, "demo_fallback_flows", False)
    m = MininetMonitor(sio=None)

    first = m._poll()
    second = m._poll()

    assert first.flows == [] and second.flows == []
    health = m.health()
    assert health["last_poll_status"] == POLL_FAILED
    assert health["last_error"], "an outage must not read as last_error = None"
    assert health["consecutive_failures"] == 2
    assert health["last_successful_poll_at"] is None
    assert health["poll_counts"][POLL_FAILED] == 2
    assert health["last_demo_substituted"] is False


def test_failed_poll_substitutes_demo_only_with_flag_on_and_keeps_the_error(daemon_down, monkeypatch):
    monkeypatch.setattr(settings, "demo_fallback_flows", True)
    m = MininetMonitor(sio=None)

    result = m._poll()

    assert result.status == POLL_FAILED
    assert result.demo_substituted is True
    assert result.flows and all(f["data_source"] == "demo" for f in result.flows)
    health = m.health()
    assert health["last_demo_substituted"] is True
    assert health["last_error"], "serving demo traffic must not hide the real failure"
    assert health["consecutive_failures"] == 1


def test_substituted_flows_are_refused_by_the_v2_gate(daemon_down, monkeypatch):
    """The two fixes compose: a failed poll with demo on yields demo flows, and
    the v2 gate refuses them. Uses the real contract from ML/."""
    from app.services.inference_v2 import InferenceV2State
    from app.services.mitigation_policy import build_policy
    from app.services.model_contract import load_contract
    from app.services.operating_points import load_operating_points

    monkeypatch.setattr(settings, "demo_fallback_flows", True)
    model_dir = settings.resolved_gs2_model_dir
    contract = load_contract(model_dir)
    state = InferenceV2State(enabled=True, contract=contract, policy=build_policy(contract),
                             operating_points=load_operating_points(model_dir))
    m = MininetMonitor(sio=None, gs2_state=state)

    m._score_v2(m._poll().flows, observed_at=0.0)

    assert m.health()["v2_provenance"]["last_poll_state"] == V2_REFUSED_NON_OVS

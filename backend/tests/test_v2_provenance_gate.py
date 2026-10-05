# [WSL2]
"""The v2 provenance gate in MininetMonitor._score_v2.

`parse_ovs_flows` can return randomised flows from `demo_flows()` in place of a
real poll, and `map_flow` does not carry `data_source` into the service request,
so the gate at the monitor is the only thing that keeps randomised input out of
the v2 path. These tests pin that down.

DATA. No hand-made traffic:
  * the randomised input is the real `demo_flows()` generator -- the thing the
    gate exists to refuse, not a stand-in for it;
  * the one accepted OVS flow is a line captured verbatim from this project's
    own Mininet topology, copied from test_error_md_regressions.py:471-478
    ("Captured verbatim 2026-08-22 -- not synthesized").

HOW "NOT SUBMITTED" IS OBSERVED. The inference client points at a local port
nothing listens on. A submission that should not have happened is therefore
VISIBLE -- the client records a connection error -- instead of silently
succeeding against a service.
"""
from __future__ import annotations

import logging
import socket

import pytest

from app.config import settings
from app.mininet_monitor.flow_parser import _parse_output, demo_flows
from app.mininet_monitor.monitor import (
    V2_DISABLED,
    V2_NOTHING_TO_SCORE,
    V2_REFUSED_NON_OVS,
    V2_SUBMITTED,
    MininetMonitor,
)
from app.services.inference_client import InferenceClient
from app.services.inference_v2 import InferenceV2State
from app.services.mitigation_policy import build_policy
from app.services.model_contract import load_contract
from app.services.operating_points import load_operating_points

# Real ICMP echo request from `ovs-ofctl dump-flows` on this project's topology,
# copied verbatim from test_error_md_regressions.py:472-478.
_REAL_ICMP_LINE = (
    'cookie=0x0, duration=17.401s, table=0, n_packets=0, n_bytes=0, '
    'idle_timeout=60, priority=1,icmp,in_port="s1-eth1",'
    'vlan_tci=0x0000/0x1fff,dl_src=00:00:00:00:00:01,'
    'dl_dst=00:00:00:00:00:02,nw_src=10.0.0.1,nw_dst=10.0.0.2,nw_tos=0,'
    'icmp_type=8,icmp_code=0 actions=output:"s1-eth2"'
)


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _real_ovs_flows() -> list[dict]:
    flows = _parse_output(_REAL_ICMP_LINE)
    assert len(flows) == 1 and flows[0]["data_source"] == "ovs"
    return flows


@pytest.fixture(scope="module")
def v2_state() -> InferenceV2State:
    """The real contract, policy and operating points from ML/."""
    model_dir = settings.resolved_gs2_model_dir
    contract = load_contract(model_dir)
    return InferenceV2State(
        enabled=True,
        contract=contract,
        policy=build_policy(contract),
        operating_points=load_operating_points(model_dir),
    )


@pytest.fixture
def dead_client():
    InferenceClient.reset_instance()
    client = InferenceClient(base_url=f"http://127.0.0.1:{_unused_port()}", timeout=1.0)
    InferenceClient._instance = client
    yield client
    InferenceClient.reset_instance()


@pytest.fixture
def monitor(v2_state):
    return MininetMonitor(sio=None, gs2_state=v2_state)


def _untouched(client: InferenceClient) -> bool:
    """True when the client never tried to reach the service at all."""
    return (
        client.last_error is None
        and client.last_success_at is None
        and not client.contract_verified
        and client._counters["flows_sent"] == 0
    )


def test_demo_batch_produces_no_v2_submission_and_is_counted(monitor, dead_client):
    flows = demo_flows()
    monitor._score_v2(flows, observed_at=0.0)

    assert _untouched(dead_client), "a demo-tagged batch reached the inference client"
    prov = monitor.health()["v2_provenance"]
    assert prov["last_poll_state"] == V2_REFUSED_NON_OVS
    assert prov["batches_refused_non_ovs"] == 1
    assert prov["flows_refused_non_ovs"] == len(flows)
    assert prov["last_refused_sources"] == {"demo": len(flows)}
    assert prov["last_refused_at"] is not None


def test_untagged_flow_is_refused_fail_closed(monitor, dead_client):
    flows = _real_ovs_flows()
    del flows[0]["data_source"]  # a source that forgot to tag its flows
    monitor._score_v2(flows, observed_at=0.0)

    assert _untouched(dead_client)
    prov = monitor.health()["v2_provenance"]
    assert prov["last_poll_state"] == V2_REFUSED_NON_OVS
    # FlowRecord's own default for a missing tag -- which is not "ovs".
    assert prov["last_refused_sources"] == {"manual": 1}


def test_mixed_batch_is_refused_whole(monitor, dead_client):
    ovs, demo = _real_ovs_flows(), demo_flows()
    monitor._score_v2(ovs + demo, observed_at=0.0)

    assert _untouched(dead_client), "part of a mixed batch was salvaged and sent"
    prov = monitor.health()["v2_provenance"]
    assert prov["flows_refused_non_ovs"] == len(ovs) + len(demo)
    assert prov["last_refused_sources"] == {"ovs": len(ovs), "demo": len(demo)}


def test_ovs_batch_passes_the_gate(monitor, dead_client):
    """The control that CAN fail: a gate refusing everything would pass the
    three tests above. A real OVS flow must get through -- here to a service
    that is not running, so passing the gate shows up as a connection error."""
    monitor._score_v2(_real_ovs_flows(), observed_at=0.0)

    assert monitor.health()["v2_provenance"]["last_poll_state"] == V2_SUBMITTED
    assert monitor.health()["v2_provenance"]["batches_refused_non_ovs"] == 0
    assert dead_client.last_error is not None, "OVS input never reached the client"
    assert monitor.last_v2_error is not None


def test_empty_poll_is_nothing_to_score_not_a_refusal(monitor, dead_client):
    monitor._score_v2([], observed_at=0.0)

    prov = monitor.health()["v2_provenance"]
    assert prov["last_poll_state"] == V2_NOTHING_TO_SCORE
    assert prov["batches_refused_non_ovs"] == 0
    assert _untouched(dead_client)


def test_disabled_v2_reports_disabled_not_refused(dead_client):
    m = MininetMonitor(sio=None, gs2_state=None)
    m._score_v2(demo_flows(), observed_at=0.0)

    prov = m.health()["v2_provenance"]
    assert prov["last_poll_state"] == V2_DISABLED
    assert prov["batches_refused_non_ovs"] == 0
    assert _untouched(dead_client)


def test_refusal_warns_at_onset_then_once_a_minute_and_logs_recovery(monitor, dead_client, caplog):
    clock = {"t": 1000.0}
    monitor._clock = lambda: clock["t"]
    caplog.set_level(logging.INFO, logger="graphsentinel.monitor")

    def warnings():
        return [r for r in caplog.records
                if r.name == "graphsentinel.monitor" and r.levelno == logging.WARNING]

    monitor._score_v2(demo_flows(), observed_at=0.0)          # onset
    assert len(warnings()) == 1
    assert "REFUSING" in warnings()[0].getMessage()

    clock["t"] += 10
    monitor._score_v2(demo_flows(), observed_at=0.0)          # 10 s later: quiet
    assert len(warnings()) == 1

    clock["t"] += 55
    monitor._score_v2(demo_flows(), observed_at=0.0)          # 65 s in: reminder
    assert len(warnings()) == 2
    assert "still refusing" in warnings()[1].getMessage()

    clock["t"] += 15
    monitor._score_v2(_real_ovs_flows(), observed_at=0.0)      # recovery, 80 s in
    recovery = [r for r in caplog.records
                if r.name == "graphsentinel.monitor" and r.levelno == logging.INFO
                and "stopped refusing" in r.getMessage()]
    assert len(recovery) == 1
    assert "80s" in recovery[0].getMessage()
    assert V2_SUBMITTED in recovery[0].getMessage()
    assert monitor.health()["v2_provenance"]["batches_refused_non_ovs"] == 3

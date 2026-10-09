"""The live loop must be able to show itself from the log.

Found on the first live run (2026-10-05): the backend's v2 lines were INFO with
no handler, so nothing printed; the gate logged refusals and not admissions; and
the committed dump-flows text was a second reading of the table, not what the
daemon returned.
"""
import importlib.util
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.logging_setup import configure_graphsentinel_logging
from app.mininet_monitor import monitor as mon

REPO = Path(__file__).resolve().parents[2]


def test_graphsentinel_loggers_print_info_without_a_log_config(capsys):
    logger = logging.getLogger("graphsentinel")
    saved = (list(logger.handlers), logger.level, logger.propagate)
    logger.handlers, logger.level = [], logging.NOTSET
    try:
        configure_graphsentinel_logging()
        logging.getLogger("graphsentinel.pipeline_v2").info("v2 window [0,60]: 1 rule(s) admitted")
        assert "1 rule(s) admitted" in capsys.readouterr().out
        configure_graphsentinel_logging()          # idempotent: still one handler
        assert len(logger.handlers) == 1
    finally:
        logger.handlers, logger.level, logger.propagate = saved


def test_an_existing_handler_is_left_alone():
    logger = logging.getLogger("graphsentinel")
    saved = (list(logger.handlers), logger.level, logger.propagate)
    mine = logging.NullHandler()
    logger.handlers = [mine]
    try:
        configure_graphsentinel_logging()
        assert logger.handlers == [mine]
    finally:
        logger.handlers, logger.level, logger.propagate = saved


@pytest.fixture()
def monitor(monkeypatch):
    m = mon.MininetMonitor(sio=MagicMock(), gs2_state=MagicMock(ready=True))
    now = {"t": 1000.0}
    m._clock = lambda: now["t"]
    m._now = now
    import app.services.analysis_pipeline_v2 as pipeline
    monkeypatch.setattr(pipeline, "score_flows", lambda flows, state, observed_at=None: {"available": True, "closed_windows": 0})
    return m


OVS = [{"src_ip": "10.0.0.2", "dst_ip": "10.0.0.3", "data_source": "ovs"}] * 3


def test_the_gate_says_when_it_admits_then_once_a_minute(monitor, caplog):
    caplog.set_level(logging.INFO, logger="graphsentinel.monitor")
    lines = lambda: [r.getMessage() for r in caplog.records if "provenance gate" in r.getMessage()]

    monitor._score_v2(OVS, 1.0)
    assert len(lines()) == 1 and "ADMITTING" in lines()[0] and "3 flows" in lines()[0]
    for _ in range(5):                       # five more polls inside the minute: silent
        monitor._now["t"] += 5
        monitor._score_v2(OVS, 1.0)
    assert len(lines()) == 1
    monitor._now["t"] += 60
    monitor._score_v2(OVS, 1.0)
    assert len(lines()) == 2 and "still admitting -- 6 poll(s), 18 flow(s)" in lines()[1]
    assert monitor.health()["v2_provenance"]["batches_admitted"] == 7
    assert monitor.health()["v2_provenance"]["flows_admitted"] == 21


def test_admission_is_logged_again_after_a_refusal(monitor, caplog):
    caplog.set_level(logging.INFO, logger="graphsentinel.monitor")
    monitor._score_v2(OVS, 1.0)
    monitor._score_v2([{"src_ip": "10.0.0.2", "dst_ip": "10.0.0.3", "data_source": "demo"}], 1.0)
    monitor._score_v2(OVS, 1.0)
    admitting = [r for r in caplog.records if "ADMITTING" in r.getMessage()]
    assert len(admitting) == 2
    assert monitor.health()["v2_provenance"]["batches_admitted"] == 2


def test_the_daemon_records_exactly_what_it_returned(tmp_path, monkeypatch):
    monkeypatch.setenv("DAEMON_TOKEN", "t")
    monkeypatch.setenv("DAEMON_DUMP_LOG", str(tmp_path / "dumps.txt"))
    spec = importlib.util.spec_from_file_location("enforcement_daemon", REPO / "backend" / "scripts" / "enforcement_daemon.py")
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    text = "NXST_FLOW reply (xid=0x4):\n cookie=0x0, n_packets=5, nw_src=10.0.0.7,nw_dst=10.0.0.3 actions=output:3\n"
    monkeypatch.setattr(daemon.subprocess, "run", lambda *a, **k: MagicMock(stdout=text))
    answer = daemon.handle_request({"token": "t", "action": "dump_flows", "switch": "s1"})
    recorded = (tmp_path / "dumps.txt").read_text(encoding="utf-8")
    assert answer["output"] == text
    assert recorded.endswith(text) and recorded.startswith("=== ") and "dump_flows s1" in recorded.splitlines()[0]

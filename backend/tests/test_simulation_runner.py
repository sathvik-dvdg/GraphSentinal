"""The Simulate button runs the real demo scripts (services/simulation_runner).

No Mininet here: the child process is replaced by a fake that prints what a
script prints, and the incident lookup by a function. What is tested is the
runner's own behaviour: which command it builds, preflight, one run at a time,
the negative control, stop, and the API around it.
"""
import io
import threading
import time

import pytest

from app.config import settings
from app.services import simulation_runner as sim

HEALTHY = {"status": "running", "last_poll_status": "ok", "last_flow_count": 14, "last_error": None}


class FakeProc:
    def __init__(self, argv, lines=(b"flood: done\n",), code=0, block: threading.Event | None = None):
        self.argv = argv
        self._code = code
        self._block = block
        self.terminated = False
        data = b"".join(lines)
        self.stdout = io.BytesIO(data) if block is None else _BlockingStream(data, block)

    def poll(self):
        return None if (self._block is not None and not self._block.is_set()) else self._code

    def wait(self):
        if self._block is not None:
            self._block.wait(5)
        return -15 if self.terminated else self._code

    def terminate(self):
        self.terminated = True
        if self._block is not None:
            self._block.set()

    def kill(self):
        self.terminate()


class _BlockingStream(io.BytesIO):
    def __init__(self, data, block):
        super().__init__(data)
        self._block = block
        self._done = False

    def readline(self, *a):
        line = super().readline(*a)
        if line:
            return line
        self._block.wait(5)
        return b""


def _runner(procs, incident=None):
    def popen(argv, **kw):
        p = procs.pop(0)(argv) if procs and callable(procs[0]) else FakeProc(argv)
        started.append(p)
        return p

    started: list = []
    r = sim.SimulationRunner(popen=popen, incident_lookup=lambda ip, since: incident(ip) if incident else None,
                             sleep=lambda s: time.sleep(0.01))
    r.started = started
    return r


def _wait_done(runner, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        run = runner.current()
        if run is not None and not run.active:
            return run
        time.sleep(0.02)
    raise AssertionError("run did not finish")


@pytest.fixture(autouse=True)
def _short_wait(monkeypatch):
    monkeypatch.setattr(settings, "simulation_score_wait_seconds", 0.2)
    monkeypatch.setattr(settings, "enforcement_mode", "simulated")


def test_flood_runs_the_real_script_and_records_the_incident():
    found = {"id": 7, "attack_type": "DDoS", "threat_score": 0.86, "is_blocked": True, "enforcement_status": "simulated"}
    r = _runner([], incident=lambda ip: found if ip == "10.0.0.2" else None)
    r.start("flood", False, "admin", HEALTHY)
    run = _wait_done(r)
    argv = r.started[0].argv
    assert argv[-1].endswith("mininet/demo/attacks/flood.py") or argv[-1].endswith("flood.py")
    assert "--mode" not in argv
    assert run.status == "finished"
    assert run.results[0]["incident"] == found
    lines = [e["line"] for e in run.log]
    assert "flood: done" in lines
    assert any("incident #7" in line for line in lines)


def test_negative_control_adds_only_the_known_flag_and_expects_nothing():
    r = _runner([])
    r.start("flood", True, "admin", HEALTHY)
    run = _wait_done(r)
    assert r.started[0].argv[-2:] == ["--mode", "icmp"]
    assert run.status == "finished"
    assert run.results[0]["incident"] is None
    assert run.results[0]["expected_label"] is None
    assert any("as expected" in e["line"] for e in run.log)

    r2 = _runner([])
    r2.start("portscan", True, "admin", HEALTHY)
    _wait_done(r2)
    assert r2.started[0].argv[-1] == "--closed"


def test_sequence_runs_the_three_scripts_in_order():
    r = _runner([])
    r.start("sequence", False, "admin", HEALTHY)
    run = _wait_done(r)
    scripts = [p.argv[-1].replace("\\", "/").rsplit("/", 1)[-1] for p in r.started]
    assert scripts == ["flood.py", "portscan.py", "bruteforce.py"]
    assert [x["attack"] for x in run.results] == ["flood", "portscan", "bruteforce"]


def test_a_failing_script_fails_the_run_and_stops_the_sequence():
    r = _runner([lambda argv: FakeProc(argv, lines=(b"flood: h2 not found\n",), code=1)])
    r.start("sequence", False, "admin", HEALTHY)
    run = _wait_done(r)
    assert run.status == "failed"
    assert len(r.started) == 1
    assert "exited with code 1" in run.error


def test_preflight_refuses_when_the_switch_is_not_being_read():
    r = _runner([])
    with pytest.raises(sim.SimulationRefused) as exc:
        r.start("flood", False, "admin", {"status": "running", "last_poll_status": "failed", "last_error": "daemon down"})
    assert exc.value.code == "preflight_failed"
    assert r.started == []
    with pytest.raises(sim.SimulationRefused):
        r.start("flood", False, "admin", None)


def test_preflight_refuses_real_enforcement(monkeypatch):
    monkeypatch.setattr(settings, "enforcement_mode", "ovs")
    with pytest.raises(sim.SimulationRefused) as exc:
        _runner([]).start("flood", False, "admin", HEALTHY)
    assert "ENFORCEMENT_MODE=simulated" in exc.value.message


def test_one_run_at_a_time_and_stop_ends_it():
    gate = threading.Event()
    r = _runner([lambda argv: FakeProc(argv, lines=(b"sending\n",), block=gate)])
    r.start("flood", False, "admin", HEALTHY)
    with pytest.raises(sim.SimulationRefused) as exc:
        r.start("portscan", False, "admin", HEALTHY)
    assert exc.value.code == "busy"
    r.stop()
    run = _wait_done(r)
    assert run.status == "stopped"
    assert r.started[0].terminated


def test_control_is_refused_for_the_sequence():
    with pytest.raises(sim.SimulationRefused) as exc:
        _runner([]).start("sequence", True, "admin", HEALTHY)
    assert exc.value.code == "invalid"


def test_api_lists_attacks_and_refuses_without_a_readable_switch(client, admin_headers, monkeypatch):
    monkeypatch.setattr(sim.SimulationRunner, "_instance", _runner([]))
    res = client.get("/api/v1/simulations", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert [a["key"] for a in body["attacks"]] == ["flood", "portscan", "bruteforce", "sequence"]
    assert {c["key"] for c in body["preflight"]["checks"]} >= {"switch_poll", "enforcement", "scripts"}

    # The test app has no Mininet, so its switch poll cannot succeed.
    res = client.post("/api/v1/simulations", json={"attack": "flood"}, headers=admin_headers)
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "preflight_failed"

    res = client.post("/api/v1/simulations", json={"attack": "rm -rf /"}, headers=admin_headers)
    assert res.status_code == 422


def test_api_starting_a_run_needs_admin(client, operator_headers):
    res = client.post("/api/v1/simulations", json={"attack": "flood"}, headers=operator_headers)
    assert res.status_code == 403


def test_find_incident_reads_only_switch_traffic_since_the_attack():
    from datetime import datetime, timedelta, timezone

    from app.database import SessionLocal
    from app.models.incident import Incident

    since = datetime.now(timezone.utc) - timedelta(seconds=1)
    db = SessionLocal()
    try:
        db.add(Incident(source_ip="10.0.0.9", attack_type="DDoS", threat_score=0.9, severity=3,
                        data_source="simulation"))
        db.commit()
        assert sim.find_incident("10.0.0.9", since) is None
        db.add(Incident(source_ip="10.0.0.9", attack_type="DDoS", threat_score=0.9, severity=3,
                        is_blocked=True, data_source="ovs", enforcement_status="simulated"))
        db.commit()
        found = sim.find_incident("10.0.0.9", since)
        assert found and found["attack_type"] == "DDoS" and found["is_blocked"] is True
        assert sim.find_incident("10.0.0.9", datetime.now(timezone.utc) + timedelta(minutes=1)) is None
    finally:
        db.close()

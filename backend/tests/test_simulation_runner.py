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


def _runner(procs, incident=None, score=None, blocked=()):
    def popen(argv, **kw):
        p = procs.pop(0)(argv) if procs and callable(procs[0]) else FakeProc(argv)
        started.append(p)
        return p

    started: list = []
    r = sim.SimulationRunner(popen=popen, incident_lookup=lambda ip, since: incident(ip) if incident else None,
                             sleep=lambda s: time.sleep(0.01),
                             score_lookup=score or (lambda ip: None),
                             blocked_lookup=lambda ips: {ip for ip in ips if ip in blocked})
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


def test_preflight_explains_a_missing_switch():
    health = {"status": "running", "last_poll_status": "failed", "last_flow_count": 2,
              "last_error": "RuntimeError: Command failed: ovs-ofctl: s1 is not a bridge or a socket"}
    poll = next(c for c in sim.preflight(health) if c["key"] == "switch_poll")
    assert poll["ok"] is False
    assert "topology is not running" in poll["detail"]
    assert "-WithMininet" in poll["detail"]


def test_a_source_that_is_already_blocked_is_refused_before_any_traffic():
    """ThreatAnalyzer skips a blocked source, so a second flood from h2 would score
    high and record nothing -- which the console used to report as "v1 did not
    score it". Refused up front, naming the host and the fix."""
    r = _runner([], blocked={"10.0.0.2"})
    with pytest.raises(sim.SimulationRefused) as exc:
        r.start("flood", False, "admin", HEALTHY)
    assert exc.value.code == "source_blocked"
    assert "10.0.0.2" in exc.value.message and "Unblock" in exc.value.message
    assert r.started == []
    with pytest.raises(sim.SimulationRefused):          # one held host holds the sequence
        r.start("sequence", False, "admin", HEALTHY)
    r.start("portscan", False, "admin", HEALTHY)         # another host is fine
    _wait_done(r)


def test_a_control_is_not_held_up_by_a_blocked_source():
    r = _runner([], blocked={"10.0.0.2"})
    r.start("flood", True, "admin", HEALTHY)
    assert _wait_done(r).status == "finished"


def test_no_incident_reports_the_latest_score_and_whether_it_is_still_rising(monkeypatch):
    monkeypatch.setattr(settings, "simulation_score_wait_seconds", 0.3)
    scores = iter([0.30, 0.45, 0.62, 0.70] + [0.70] * 100)
    r = _runner([], score=lambda ip: next(scores))
    r.start("flood", False, "admin", HEALTHY)
    run = _wait_done(r)
    lines = [e["line"] for e in run.log]
    assert any(line.startswith("v1 score for 10.0.0.2: 0.30") for line in lines)
    assert run.results[0]["score"] is not None
    assert any("Latest v1 score" in line and "threshold" in line for line in lines)
    assert not any("did not score it over" in line for line in lines)


def test_no_incident_and_no_score_says_the_switch_did_not_show_the_traffic():
    r = _runner([], score=lambda ip: None)
    r.start("flood", False, "admin", HEALTHY)
    run = _wait_done(r)
    assert any("never appeared in a scored batch" in e["line"] for e in run.log)


def test_an_attack_waits_longer_than_a_control(monkeypatch):
    monkeypatch.setattr(settings, "simulation_score_wait_seconds", 45.0)
    assert sim.wait_seconds(False) == 45.0
    assert sim.wait_seconds(True) == 20.0


def test_api_reports_why_an_attack_is_blocked(client, admin_headers):
    body = client.get("/api/v1/simulations", headers=admin_headers).json()
    assert set(body["blockers"]) == {"flood", "portscan", "bruteforce", "sequence"}

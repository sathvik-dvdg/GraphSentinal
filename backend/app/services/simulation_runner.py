"""Run the real demo attacks (mininet/demo/attacks) from the dashboard.

The Simulate button used to post synthetic flows to /analyze. This replaces it:
a run starts one of the three scripts in mininet/demo/attacks as a child
process, exactly as `run_demo.py` does by hand, and the result is whatever the
switch, the monitor and v1 make of the traffic. Nothing here builds a flow.

    flood       h2 10.0.0.2 -> h1:80     2000 HTTP requests   (--mode icmp: ping flood)
    portscan    h3 10.0.0.3 -> h1:20-30  11 TCP connects      (--closed: ports left shut)
    bruteforce  h4 10.0.0.4 -> h1:22     300 TCP connections  (--closed: port left shut)
    sequence    the three above, in that order, as run_demo.py runs them

Where the processes go: the scripts themselves send their commands into WSL as
root when the backend runs on Windows (attacks/_hosts.py). On Linux/WSL they
need root; a backend that is not root runs them through `sudo -n`, so a missing
sudoers rule fails at once with sudo's own message rather than hanging on a
password prompt.

Only these three scripts and their two flags can be started: the request picks
from the table below and nothing it sends reaches the command line.
"""
from __future__ import annotations

import itertools
import logging
import os
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.config import settings

logger = logging.getLogger(__name__)

# backend/app/services/ -> repository root
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCRIPTS_DIR = _REPO_ROOT / "mininet" / "demo" / "attacks"

# Polls that count as "the backend can see the switch" (run_demo.py preflight).
_POLL_OK = ("ok", "ok_empty")
_LOG_LINES = 400
_SCRIPT_TIMEOUT_S = 300.0


@dataclass(frozen=True)
class Attack:
    key: str
    name: str
    script: str
    source_host: str
    source_ip: str
    target: str
    sends: str
    expected_label: str
    control_args: tuple[str, ...]
    control_note: str


ATTACKS: dict[str, Attack] = {
    "flood": Attack(
        "flood", "HTTP flood", "flood.py", "h2", "10.0.0.2", "h1:80",
        "2000 HTTP requests, a new connection each", "DDoS",
        ("--mode", "icmp"), "a ping flood instead: v1 does not score ICMP, expect no incident",
    ),
    "portscan": Attack(
        "portscan", "Port scan", "portscan.py", "h3", "10.0.0.3", "h1:20-30",
        "a TCP connect to each of 11 ports", "PortScan",
        ("--closed",), "the ports are left closed: expect no incident",
    ),
    "bruteforce": Attack(
        "bruteforce", "SSH brute-force shape", "bruteforce.py", "h4", "10.0.0.4", "h1:22",
        "300 short TCP connections", "SSHBrute",
        ("--closed",), "port 22 is left closed: expect no incident",
    ),
}
SEQUENCE: tuple[str, ...] = ("flood", "portscan", "bruteforce")
RUNNABLE = (*ATTACKS.keys(), "sequence")


class SimulationRefused(Exception):
    """A run was not started. `code` is busy | preflight_failed | invalid."""

    def __init__(self, code: str, message: str, checks: list[dict] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.checks = checks or []


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def scripts_dir() -> Path:
    configured = settings.simulation_scripts_dir
    return Path(configured) if configured else DEFAULT_SCRIPTS_DIR


def catalog() -> list[dict]:
    rows = [
        {
            "key": a.key, "name": a.name, "script": a.script,
            "source_host": a.source_host, "source_ip": a.source_ip, "target": a.target,
            "sends": a.sends, "expected_label": a.expected_label,
            "control_flag": " ".join(a.control_args), "control_note": a.control_note,
        }
        for a in ATTACKS.values()
    ]
    rows.append({
        "key": "sequence", "name": "Full sequence", "script": "flood.py, portscan.py, bruteforce.py",
        "source_host": "h2, h3, h4", "source_ip": "10.0.0.2-4", "target": "h1",
        "sends": "the three attacks in order, waiting for the score after each",
        "expected_label": "DDoS, PortScan, SSHBrute", "control_flag": "", "control_note": "",
    })
    return rows


def preflight(monitor_health: dict | None) -> list[dict]:
    """The checks run_demo.py makes, from the backend's own state. An attack the
    backend cannot see demonstrates nothing, so every one must pass."""
    health = monitor_health or {"status": "disabled"}
    monitor_on = health.get("status") != "disabled"
    poll = health.get("last_poll_status")
    poll_detail = f"{poll} ({health.get('last_flow_count')} flows)" if poll else "no poll yet"
    if health.get("last_error"):
        poll_detail += f": {health['last_error']}"
    folder = scripts_dir()
    missing = [a.script for a in ATTACKS.values() if not (folder / a.script).is_file()]
    return [
        {
            "key": "monitor", "label": "Switch monitor running", "ok": monitor_on,
            "detail": "on" if monitor_on else "off: start the backend with the monitor enabled",
        },
        {
            "key": "switch_poll", "label": "Last switch poll (through the enforcement daemon)",
            "ok": monitor_on and poll in _POLL_OK,
            "detail": poll_detail if monitor_on else "monitor off",
        },
        {
            "key": "enforcement", "label": "Enforcement mode is simulated",
            "ok": settings.enforcement_mode == "simulated",
            "detail": settings.enforcement_mode if settings.enforcement_mode == "simulated"
            else f"{settings.enforcement_mode}: a run would install real drop rules. Set ENFORCEMENT_MODE=simulated",
        },
        {
            "key": "scripts", "label": "Attack scripts present", "ok": not missing,
            "detail": str(folder) if not missing else f"missing in {folder}: {', '.join(missing)}",
        },
    ]


def _command_prefix() -> list[str]:
    if sys.platform == "win32":
        return []           # the scripts send their own commands into WSL as root
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        return ["sudo", "-n"]
    return []


@dataclass
class Run:
    id: int
    attack: str
    control: bool
    started_by: str
    started_at: datetime = field(default_factory=_utc_now)
    status: str = "running"          # running | finished | failed | stopped
    phase: str = "preflight"         # preflight | traffic | scoring | done
    current: str | None = None       # the attack being run now
    finished_at: datetime | None = None
    error: str | None = None
    results: list[dict] = field(default_factory=list)
    log: deque = field(default_factory=lambda: deque(maxlen=_LOG_LINES))
    phase_started_at: datetime = field(default_factory=_utc_now)

    @property
    def active(self) -> bool:
        return self.status == "running"

    def snapshot(self, log_tail: int | None = None) -> dict[str, Any]:
        lines = list(self.log)
        if log_tail is not None:
            lines = lines[-log_tail:]
        return {
            "id": self.id,
            "attack": self.attack,
            "control": self.control,
            "started_by": self.started_by,
            "status": self.status,
            "active": self.active,
            "phase": self.phase,
            "phase_started_at": self.phase_started_at.isoformat(),
            "current": self.current,
            "steps": list(SEQUENCE) if self.attack == "sequence" else [self.attack],
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
            "results": list(self.results),
            "score_wait_seconds": settings.simulation_score_wait_seconds,
            "log": lines,
        }


def find_incident(source_ip: str, since: datetime) -> dict | None:
    """The first incident recorded for this source from switch traffic since
    `since`, or None. Read from the database the monitor writes to."""
    from app.database import SessionLocal
    from app.models.incident import Incident

    db = SessionLocal()
    try:
        row = (
            db.query(Incident)
            .filter(Incident.source_ip == source_ip, Incident.created_at >= since, Incident.data_source == "ovs")
            .order_by(Incident.id.asc())
            .first()
        )
        if row is None:
            return None
        return {
            "id": row.id, "attack_type": row.attack_type, "threat_score": row.threat_score,
            "is_blocked": bool(row.is_blocked), "enforcement_status": row.enforcement_status,
        }
    finally:
        db.close()


class SimulationRunner:
    """At most one run at a time, process-wide."""

    _instance: "SimulationRunner | None" = None

    def __init__(self, popen: Callable[..., subprocess.Popen] = subprocess.Popen,
                 incident_lookup: Callable[[str, datetime], dict | None] = find_incident,
                 sleep: Callable[[float], None] = time.sleep):
        self._popen = popen
        self._incident_lookup = incident_lookup
        self._sleep = sleep
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._current: Run | None = None
        self._process: subprocess.Popen | None = None
        self._stop = threading.Event()
        self._listeners: list[Callable[[dict], None]] = []

    @classmethod
    def get_instance(cls) -> "SimulationRunner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── observers ────────────────────────────────────────────────────────────
    def add_listener(self, fn: Callable[[dict], None]) -> None:
        self._listeners.append(fn)

    def _notify(self, run: Run) -> None:
        snap = run.snapshot(log_tail=60)
        for fn in list(self._listeners):
            try:
                fn(snap)
            except Exception:  # noqa: BLE001 -- a listener must never stop a run
                logger.exception("simulation listener failed")

    # ── state ────────────────────────────────────────────────────────────────
    def current(self) -> Run | None:
        return self._current

    def _log(self, run: Run, line: str, kind: str = "out") -> None:
        run.log.append({"t": _utc_now().isoformat(), "kind": kind, "line": line.rstrip()})
        self._notify(run)

    def _phase(self, run: Run, phase: str, current: str | None = None) -> None:
        run.phase = phase
        run.current = current
        run.phase_started_at = _utc_now()
        self._notify(run)

    # ── control ──────────────────────────────────────────────────────────────
    def start(self, attack: str, control: bool, started_by: str, monitor_health: dict | None) -> Run:
        if attack not in RUNNABLE:
            raise SimulationRefused("invalid", f"unknown attack {attack!r}")
        if control and attack == "sequence":
            raise SimulationRefused("invalid", "the negative control is for a single attack, not the sequence")
        with self._lock:
            if self._current is not None and self._current.active:
                raise SimulationRefused("busy", f"run {self._current.id} ({self._current.attack}) is still running")
            checks = preflight(monitor_health)
            failed = [c for c in checks if not c["ok"]]
            if failed:
                raise SimulationRefused(
                    "preflight_failed",
                    "; ".join(f"{c['label']}: {c['detail']}" for c in failed),
                    checks,
                )
            run = Run(id=next(self._ids), attack=attack, control=control, started_by=started_by)
            self._current = run
            self._stop.clear()
        for c in checks:
            self._log(run, f"preflight: {c['label']}: {c['detail']}", "info")
        threading.Thread(target=self._execute, args=(run,), name=f"simulation-{run.id}", daemon=True).start()
        return run

    def stop(self) -> Run | None:
        run = self._current
        if run is None or not run.active:
            return run
        self._stop.set()
        proc = self._process
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        return run

    # ── the run itself (worker thread) ───────────────────────────────────────
    def _execute(self, run: Run) -> None:
        keys = list(SEQUENCE) if run.attack == "sequence" else [run.attack]
        try:
            for key in keys:
                if self._stop.is_set():
                    break
                ok = self._run_one(run, ATTACKS[key])
                if not ok:
                    break
            if self._stop.is_set():
                run.status = "stopped"
                self._log(run, "stopped by an admin. Listeners opened on h1 close by themselves within 60 s.", "error")
            elif run.status == "running":
                run.status = "finished"
        except Exception as exc:  # noqa: BLE001
            logger.exception("simulation run %s crashed", run.id)
            run.status, run.error = "failed", str(exc)
            self._log(run, f"runner error: {exc}", "error")
        finally:
            self._process = None
            run.finished_at = _utc_now()
            self._phase(run, "done", None)

    def _run_one(self, run: Run, attack: Attack) -> bool:
        args = list(attack.control_args) if run.control else []
        argv = [*_command_prefix(), settings.simulation_python or sys.executable, "-u",
                str(scripts_dir() / attack.script), *args]
        result = {
            "attack": attack.key, "source_ip": attack.source_ip, "control": run.control,
            "expected_label": None if run.control else attack.expected_label,
            "exit_code": None, "incident": None,
        }
        run.results.append(result)
        self._phase(run, "traffic", attack.key)
        self._log(run, "$ " + " ".join([*(["sudo", "-n"] if argv[0] == "sudo" else []),
                                         "python3", f"mininet/demo/attacks/{attack.script}", *args]), "cmd")
        sent_at = _utc_now()
        code = self._spawn(run, argv)
        result["exit_code"] = code
        if self._stop.is_set():
            return False
        if code != 0:
            run.status = "failed"
            run.error = f"{attack.script} exited with code {code}"
            self._log(run, run.error, "error")
            return False

        # v1's score for a source rises over the first polls after an attack.
        # Watch for the incident, and stop waiting as soon as it is recorded.
        wait = float(settings.simulation_score_wait_seconds)
        self._phase(run, "scoring", attack.key)
        self._log(run, f"waiting up to {wait:.0f} s for the monitor to poll s1 and v1 to score {attack.source_ip}", "info")
        deadline = time.monotonic() + wait
        while not self._stop.is_set():
            incident = self._incident_lookup(attack.source_ip, sent_at)
            if incident is not None:
                result["incident"] = incident
                self._log(run, f"incident #{incident['id']}: {attack.source_ip} scored "
                               f"{incident['threat_score']:.2f}, label {incident['attack_type']} (heuristic), "
                               f"enforcement {incident['enforcement_status']}", "result")
                return True
            if time.monotonic() >= deadline:
                break
            self._sleep(2.0)
        if self._stop.is_set():
            return False
        if run.control:
            self._log(run, f"no incident for {attack.source_ip}: as expected for this control.", "result")
        else:
            self._log(run, f"no incident for {attack.source_ip} after {wait:.0f} s. v1 did not score it over "
                           f"the threshold ({settings.threat_threshold}).", "result")
        return True

    def _spawn(self, run: Run, argv: list[str]) -> int:
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        try:
            proc = self._popen(
                argv, cwd=str(_REPO_ROOT), env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
        except OSError as exc:
            self._log(run, f"could not start {argv[0]}: {exc}", "error")
            return 127
        self._process = proc
        timer = threading.Timer(_SCRIPT_TIMEOUT_S, lambda: proc.poll() is None and proc.kill())
        timer.daemon = True
        timer.start()
        try:
            for raw in iter(proc.stdout.readline, b""):
                # wsl.exe can answer in UTF-16: strip the NULs rather than guess
                line = raw.decode("utf-8", "replace").replace("\x00", "").rstrip()
                if line:
                    self._log(run, line)
            return proc.wait()
        finally:
            timer.cancel()
            if proc.stdout:
                proc.stdout.close()

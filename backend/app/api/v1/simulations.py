"""The Simulate button: start, follow and stop a run of the real demo attacks.

    GET  /api/v1/simulations          catalog, preflight and the current run
    POST /api/v1/simulations          {"attack": "flood", "control": false}  (admin)
    POST /api/v1/simulations/stop     (admin)

Progress is pushed as the socket event `simulation_update` and can be read back
with GET. What a run does: services/simulation_runner.py.
"""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_request_id, require_admin_privilege, require_session_or_api_key
from app.database import get_db
from app.services import simulation_runner as sim
from app.services.audit_service import log_audit_event

router = APIRouter()


class SimulationStartRequest(BaseModel):
    attack: Literal["flood", "portscan", "bruteforce", "sequence"]
    # Run the attack's negative control (flood --mode icmp, the others --closed).
    control: bool = False


def _monitor_health(request: Request) -> dict | None:
    monitor = getattr(request.app.state, "monitor", None)
    return monitor.health() if monitor is not None else None


def attach_socket(sio, loop: asyncio.AbstractEventLoop) -> None:
    """Push every change of a run to the dashboards, from the runner's thread."""

    def emit(snapshot: dict) -> None:
        if loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(sio.emit("simulation_update", snapshot), loop)

    sim.SimulationRunner.get_instance().add_listener(emit)


@router.get("/simulations")
async def get_simulations(request: Request, _: dict = Depends(require_session_or_api_key)):
    checks = sim.preflight(_monitor_health(request))
    run = sim.SimulationRunner.get_instance().current()
    return {
        "attacks": sim.catalog(),
        "preflight": {"ok": all(c["ok"] for c in checks), "checks": checks},
        # Per attack, why a real (non-control) run could not record its incident.
        "blockers": {a: sim.blockers(a, False) for a in sim.RUNNABLE},
        "current": run.snapshot() if run else None,
    }


@router.post("/simulations", status_code=202)
async def start_simulation(
    body: SimulationStartRequest,
    request: Request,
    identity: dict = Depends(require_admin_privilege),
    db: Session = Depends(get_db),
):
    who = identity.get("identity", "admin")
    try:
        run = sim.SimulationRunner.get_instance().start(
            body.attack, body.control, who, _monitor_health(request),
        )
    except sim.SimulationRefused as exc:
        status = 422 if exc.code == "invalid" else 409
        log_audit_event(
            db=db, actor_identity=who, actor_role=identity.get("role", "admin"),
            action="simulation_start", target_resource=body.attack,
            details={"control": body.control, "refused": exc.code, "reason": exc.message},
            status="failure", request_id=get_current_request_id(request),
        )
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message, "checks": exc.checks})
    log_audit_event(
        db=db, actor_identity=who, actor_role=identity.get("role", "admin"),
        action="simulation_start", target_resource=body.attack,
        details={"run_id": run.id, "control": body.control},
        status="success", request_id=get_current_request_id(request),
    )
    return run.snapshot()


@router.post("/simulations/stop")
async def stop_simulation(
    request: Request,
    identity: dict = Depends(require_admin_privilege),
    db: Session = Depends(get_db),
):
    run = sim.SimulationRunner.get_instance().stop()
    if run is None:
        raise HTTPException(status_code=404, detail="No simulation has run since the backend started")
    log_audit_event(
        db=db, actor_identity=identity.get("identity", "admin"), actor_role=identity.get("role", "admin"),
        action="simulation_stop", target_resource=run.attack, details={"run_id": run.id},
        status="success", request_id=get_current_request_id(request),
    )
    return run.snapshot()

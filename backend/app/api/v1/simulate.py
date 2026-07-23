# [WSL2]
"""POST /api/v1/simulate — inject attack from Settings.jsx."""
import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.deps import require_admin_key
from app.services.analysis_pipeline import analyze_flows
from app.websocket.events import emit_analysis_events


router = APIRouter()


class SimulateRequest(BaseModel):
    attack_type: Literal["DDoS", "SSHBrute", "PortScan", "Botnet"] = "DDoS"
    target_ip: str = Field(default="10.0.0.2", pattern=r"^10\.0\.0\.\d{1,3}$")


# Synthetic flow templates per attack type
_ATTACK_TEMPLATES: dict[str, list[dict]] = {
    "DDoS": [
        {"src_ip": "{ip}", "dst_ip": "10.0.0.1", "src_port": 54321, "dst_port": 80, "protocol": "TCP", "packet_count": 15000, "byte_count": 5120000, "duration_sec": 3.5, "tcp_flags": 2},
        {"src_ip": "{ip}", "dst_ip": "10.0.0.1", "src_port": 54322, "dst_port": 443, "protocol": "TCP", "packet_count": 12000, "byte_count": 4096000, "duration_sec": 3.0, "tcp_flags": 2},
    ],
    "SSHBrute": [
        {"src_ip": "{ip}", "dst_ip": "10.0.0.1", "src_port": 49001, "dst_port": 22, "protocol": "TCP", "packet_count": 500, "byte_count": 30000, "duration_sec": 10.0, "tcp_flags": 2},
        {"src_ip": "{ip}", "dst_ip": "10.0.0.1", "src_port": 49002, "dst_port": 22, "protocol": "TCP", "packet_count": 480, "byte_count": 28000, "duration_sec": 10.0, "tcp_flags": 2},
    ],
    "PortScan": [
        {"src_ip": "{ip}", "dst_ip": "10.0.0.1", "src_port": 60001, "dst_port": port, "protocol": "TCP", "packet_count": 3, "byte_count": 180, "duration_sec": 0.5, "tcp_flags": 2}
        for port in [21, 22, 23, 25, 80, 443, 3306, 5432, 8080]
    ],
    "Botnet": [
        {"src_ip": "{ip}", "dst_ip": "10.0.0.3", "src_port": 51000, "dst_port": 6667, "protocol": "TCP", "packet_count": 200, "byte_count": 48000, "duration_sec": 2.0, "tcp_flags": 0},
        {"src_ip": "{ip}", "dst_ip": "10.0.0.3", "src_port": 51001, "dst_port": 8080, "protocol": "TCP", "packet_count": 180, "byte_count": 42000, "duration_sec": 2.0, "tcp_flags": 0},
    ],
}


@router.post("/simulate")
async def simulate_attack(
    request: SimulateRequest,
    _: None = Depends(require_admin_key),
):
    template = _ATTACK_TEMPLATES.get(request.attack_type)
    if not template:
        raise HTTPException(status_code=422, detail=f"Unknown attack type: {request.attack_type}")

    flows = [
        {k: (v.replace("{ip}", request.target_ip) if isinstance(v, str) else v) for k, v in flow.items()}
        for flow in template
    ]

    try:
        result = await asyncio.to_thread(analyze_flows, flows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        from app.main import sio
        await emit_analysis_events(sio, result)
    except Exception:
        pass

    return {
        "status": "injected",
        "attack_type": request.attack_type,
        "target_ip": request.target_ip,
        "flows_generated": len(flows),
        "result": result,
    }

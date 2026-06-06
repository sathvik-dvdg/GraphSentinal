# [WSL2]
from __future__ import annotations


async def emit_analysis_events(sio, result: dict) -> None:
    await sio.emit("graph_update", result["graph_snapshot"])
    for alert in result.get("alerts", []):
        await sio.emit("alert", alert)
    for event in result.get("healing_events", []):
        await sio.emit("healing_triggered", event)


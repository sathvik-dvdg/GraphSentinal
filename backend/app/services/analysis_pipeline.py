# [WSL2]
from __future__ import annotations

from typing import Any

from app.config import settings
from app.models.schemas import FlowRecord
from app.services.graph_state import graph_state
from app.services.inference_service import InferenceService
from app.services.threat_analyzer import ThreatAnalyzer


def analyze_flows(flows: list[Any], cap: int | None = None) -> dict[str, Any]:
    """`cap` replaces MAX_ANALYZE_FLOWS for callers that are not the HTTP API.
    The API keeps the small cap (it bounds what a client can make the server
    compute); the switch monitor passes MONITOR_MAX_FLOWS, because a flood of
    2000 connections leaves 4000 entries in the switch's table for up to a minute,
    and refusing the whole poll blinded detection and froze the dashboard."""
    limit = settings.max_analyze_flows if cap is None else cap
    if len(flows) > limit:
        raise ValueError(f"Too many flows; max is {limit}")

    flow_records = [flow if isinstance(flow, FlowRecord) else FlowRecord(**dict(flow)) for flow in flows]
    inference = InferenceService.get_instance()
    prediction = inference.predict(flow_records)
    analyzer = ThreatAnalyzer()
    alerts, healing_events = analyzer.evaluate(prediction, flow_records)
    graph = graph_state.update(flow_records, prediction)
    return {
        "predictions": prediction["ip_scores"],
        "flow_scores": prediction["flow_scores"],
        "incidents_created": [alert["id"] for alert in alerts],
        "healing_triggered": [event["ip"] for event in healing_events],
        "graph_snapshot": graph,
        "alerts": alerts,
        "healing_events": healing_events,
        "skipped": analyzer.skipped,
        "ml_mode": prediction.get("mode"),
        "degraded_reason": prediction.get("degraded_reason"),
    }


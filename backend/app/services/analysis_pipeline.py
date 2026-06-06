# [WSL2]
from __future__ import annotations

from typing import Any

from app.config import settings
from app.models.schemas import FlowRecord
from app.services.graph_state import graph_state
from app.services.inference_service import InferenceService
from app.services.threat_analyzer import ThreatAnalyzer


def analyze_flows(flows: list[Any]) -> dict[str, Any]:
    if len(flows) > settings.max_analyze_flows:
        raise ValueError(f"Too many flows; max is {settings.max_analyze_flows}")

    flow_records = [flow if isinstance(flow, FlowRecord) else FlowRecord(**dict(flow)) for flow in flows]
    inference = InferenceService.get_instance()
    prediction = inference.predict(flow_records)
    alerts, healing_events = ThreatAnalyzer().evaluate(prediction, flow_records)
    graph = graph_state.update(flow_records, prediction)
    return {
        "predictions": prediction["ip_scores"],
        "flow_scores": prediction["flow_scores"],
        "incidents_created": [alert["id"] for alert in alerts],
        "healing_triggered": [event["ip"] for event in healing_events],
        "graph_snapshot": graph,
        "alerts": alerts,
        "healing_events": healing_events,
        "ml_mode": prediction.get("mode"),
        "degraded_reason": prediction.get("degraded_reason"),
    }


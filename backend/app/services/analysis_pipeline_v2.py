# [WSL2]
"""The v2 (flow/edge-level) scoring path.

Runs ALONGSIDE `analysis_pipeline.analyze_flows()`, not instead of it. The v1
path keeps its own behaviour, including its heuristic fallback; nothing here
inherits that fallback.

WHAT THIS PATH DOES AND DOES NOT DO

  does      score real flows from the live ingestion path at FLOW (edge) level,
            report per-flow verdicts, and track how often a window could not be
            scored at all.

  does NOT  create incidents, raise alerts, block IPs, or write to the chain.
            Alerting is not implemented on this path (`V2_ALERTING_IMPLEMENTED`
            in inference_v2.py). `ML/threshold_study.json` now exists and loads,
            but loading it changes only what is reported: its `binary_gate` is
            provisional -- 0.5 sits on one of the fixed values the study script
            appended to its search grid, and run-to-run variation of the model
            is unmeasured (INTEGRATION.md §4). It must not be wired to anything
            that alerts until both are resolved. `flows_over_gate` below is
            reported for inspection only.

  does NOT  read the node head. `WindowResult.detections` is node-level
            (test binary F1 0.1407, PR-AUC below base rate for three of four
            attack classes) and is discarded unread. Host-level attribution is
            not a claim this backend makes.

  does NOT  install SDN rules. `SDNTranslator` stays dry_run=True.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.services.inference_client import InferenceClient, InferenceUnavailable, WindowOutcome
from app.services.inference_v2 import ALERTING_DISABLED_REASON, InferenceV2State, verify_service_contract
from app.services.model_contract import ContractError

_log = logging.getLogger("graphsentinel.pipeline_v2")


def _verdict_payload(verdict, state: InferenceV2State) -> dict[str, Any]:
    """One flow verdict as the API reports it, with reliability caveats attached."""
    # Validate at the seam: an out-of-contract label fails here, where we can say
    # what produced it, rather than as a pydantic response error three layers on.
    label = state.validate_label(verdict.attack_class)
    payload: dict[str, Any] = {
        "src_ip": verdict.src_ip,
        "dst_ip": verdict.dst_ip,
        "src_port": verdict.src_port,
        "dst_port": verdict.dst_port,
        "protocol": verdict.protocol,
        "attack_class": label,
        "confidence": round(verdict.confidence, 6),
        "threat_score": round(verdict.threat_score, 6),
        "class_probs": {k: round(v, 6) for k, v in verdict.class_probs.items()},
    }
    note = state.class_note(label)
    if note:
        # A Botnet label must never reach an operator without this attached.
        payload["reliability"] = note
    return payload


def _window_payload(outcome: WindowOutcome, state: InferenceV2State) -> dict[str, Any]:
    gate = state.operating_points.binary_gate if state.operating_points else None
    flows = [_verdict_payload(v, state) for v in outcome.flows]

    over_gate: int | None = None
    if gate is not None:
        over_gate = sum(1 for f in flows if f["threat_score"] >= gate)

    return {
        "window_start": outcome.window_start,
        "window_end": outcome.window_end,
        "n_flows": outcome.n_flows,
        "n_hosts": outcome.n_hosts,
        # An unscored window is NOT a clean window. The builder refuses to make a
        # graph below its minimum flow count, so nothing in it was examined.
        "unscored": outcome.unscored,
        "unscored_reason": (
            "window held fewer flows than the graph builder's minimum; no graph "
            "was built and nothing was scored. This is not a clean window."
        ) if outcome.unscored else None,
        "flows": flows,
        "flows_over_gate": over_gate,
        "latency_ms": round(outcome.latency_ms, 3),
    }


def score_flows(
    flows: list[Any],
    state: InferenceV2State,
    observed_at: float | None = None,
) -> dict[str, Any]:
    """Submit real flows to the inference service and report what came back.

    Never raises on an unreachable service: returns `available: False` with the
    reason. The caller must treat that as "no scores", never as "no threats".
    """
    if not state.ready:
        return {
            "available": False,
            "reason": state.disabled_reason or "v2 inference not configured",
            "windows": [],
        }

    client = InferenceClient.get_instance()
    t0 = time.perf_counter()
    try:
        if not client.contract_verified:
            # The service labels flows with ITS card. Until that card is proven
            # identical to the one validated here, its labels are not scored.
            verify_service_contract(state, client.fetch_contract())
            client.contract_verified = True
        outcomes = client.submit(flows, observed_at=observed_at)
    except ContractError as exc:
        _log.error("v2 service contract mismatch — NOT scoring: %s", exc)
        return {
            "available": False,
            "reason": str(exc),
            "windows": [],
            "note": "Scores were NOT produced. This is not evidence of clean traffic.",
        }
    except InferenceUnavailable as exc:
        # No fallback, deliberately. A hand-tuned formula emitting numbers that
        # look like model output, into the same incidents table, that then block
        # IPs, is worse than an outage.
        _log.error("v2 inference unavailable — NOT scoring this batch: %s", exc)
        return {
            "available": False,
            "reason": str(exc),
            "windows": [],
            "note": "Scores were NOT produced. This is not evidence of clean traffic.",
        }

    windows = [_window_payload(o, state) for o in outcomes]
    return {
        "available": True,
        "windows": windows,
        "closed_windows": len(windows),
        "flows_submitted": len(flows),
        "unscored_rate": client.unscored_rate,
        # Alerting is not implemented on this path. Stated in the response so a
        # consumer cannot mistake "no alerts" for "nothing found".
        "alerting_enabled": state.alerting_enabled,
        "alerting_disabled_reason": None if state.alerting_enabled else ALERTING_DISABLED_REASON,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 3),
    }

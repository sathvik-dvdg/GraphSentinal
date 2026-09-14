"""
HTTP inference microservice -- the real decoupling boundary.

The backend POSTs flow records and receives detections plus OpenFlow rules. It
never imports a model class, never learns a feature count, and does not care
whether the model behind this endpoint is a 3-layer SAGE, a GATv2 with memory,
or something not written yet.

    GET  /health           liveness + memory occupancy + drift state
    GET  /contract         the model card (feature names, classes, version)
    POST /flows            ingest flow records; returns any closed windows
    POST /flush            force-close the current window
    GET  /stats            throughput counters

Run:
    uvicorn graphsentinel.inference.service:app --host 0.0.0.0 --port 8080
with ``GRAPHSENTINEL_MODEL_DIR`` pointing at an export directory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field

    _HAS_FASTAPI = True
except ImportError:  # pragma: no cover
    _HAS_FASTAPI = False
    FastAPI = object  # type: ignore
    BaseModel = object  # type: ignore

from ..config import Config
from .engine import InferenceEngine

MODEL_DIR = os.environ.get("GRAPHSENTINEL_MODEL_DIR", "models/")
_engine: Optional[InferenceEngine] = None


def get_engine() -> InferenceEngine:
    global _engine
    if _engine is None:
        _engine = InferenceEngine.from_artifacts(MODEL_DIR)
    return _engine


if _HAS_FASTAPI:

    class FlowRecord(BaseModel):
        """One CICFlowMeter-style flow. Extra keys are accepted and ignored."""

        source_ip: str = Field(alias="Source IP")
        destination_ip: str = Field(alias="Destination IP")
        source_port: int = Field(0, alias="Source Port")
        destination_port: int = Field(0, alias="Destination Port")
        protocol: int = Field(6, alias="Protocol")
        timestamp: float = Field(alias="t")

        model_config = {"populate_by_name": True, "extra": "allow"}

    class FlowBatch(BaseModel):
        flows: List[Dict[str, Any]]

    app = FastAPI(
        title="GraphSentinel Inference",
        version="2.0.0",
        description="Graph-based IDS inference. Contract lives at /contract.",
    )

    @app.get("/health")
    def health():
        try:
            eng = get_engine()
        except Exception as exc:
            raise HTTPException(503, f"model not loaded: {exc}")
        mem = eng.model.memory.occupancy() if eng.model.memory is not None else {}
        return {
            "status": "ok",
            "model_dir": MODEL_DIR,
            "memory": mem,
            "stats": eng.stats,
            "buffered_flows": len(eng._buffer),
        }

    @app.get("/contract")
    def contract():
        path = Path(MODEL_DIR) / "model_card.json"
        if not path.exists():
            raise HTTPException(404, "model_card.json not found")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.post("/flows")
    def ingest(batch: FlowBatch):
        eng = get_engine()
        results = eng.ingest(batch.flows)
        return {"closed_windows": len(results), "results": [r.to_dict() for r in results]}

    @app.post("/flush")
    def flush():
        res = get_engine().flush()
        return {"result": res.to_dict() if res else None}

    @app.get("/stats")
    def stats():
        return get_engine().stats

else:  # pragma: no cover

    app = None

    def _missing(*_a, **_k):
        raise RuntimeError(
            "fastapi and pydantic are required for the inference service:\n"
            "    pip install fastapi uvicorn pydantic"
        )

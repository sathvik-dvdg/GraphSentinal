# [WSL2]
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.graph_builder import build_pyg_graph


def _import_torch():
    try:
        import torch
    except Exception as exc:
        raise RuntimeError("PyTorch is unavailable or misconfigured") from exc
    return torch


class InferenceService:
    _instance: "InferenceService | None" = None

    @classmethod
    def get_instance(cls) -> "InferenceService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.torch = None
        self.degraded_reason = ""
        try:
            self.torch = _import_torch()
            self.torch.set_num_threads(min(4, os.cpu_count() or 1))
        except RuntimeError as exc:
            self.torch = None
            self.degraded_reason = str(exc)

        self.model = None
        self.mode = "degraded"
        self.weights_path: str | None = None
        self._load_model()

    def _load_model_class(self):
        source = Path(settings.model_source_path)
        candidates = [source]
        if not source.is_absolute():
            backend_dir = Path(__file__).resolve().parent.parent.parent
            candidates.append((backend_dir / source).resolve())

        for candidate in candidates:
            if (candidate / "model.py").exists():
                sys.path.insert(0, str(candidate))
                module = importlib.import_module("model")
                return module.GraphSAGEClassifier

        from app.services.graphsage_model import GraphSAGEClassifier

        return GraphSAGEClassifier

    def _existing_weights_path(self) -> Path | None:
        for candidate in settings.resolved_weights_candidates:
            if candidate.exists():
                return candidate
        return None

    def _load_model(self) -> None:
        if self.torch is None:
            self._degrade_or_raise("PyTorch unavailable; model disabled")
            return

        weights_path = self._existing_weights_path()
        if weights_path is None:
            self._degrade_or_raise("GraphSAGE weights file not found")
            return

        try:
            model_cls = self._load_model_class()
            self.model = model_cls(
                in_channels=settings.node_feature_count,
                hidden_channels=256,
                out_channels=2,
                num_layers=3,
            )
            state_dict = self.torch.load(weights_path, map_location="cpu")
            self.model.load_state_dict(state_dict)
            self.model.eval()
            self.mode = "model"
            self.degraded_reason = ""
            self.weights_path = str(weights_path)
        except Exception as exc:
            self._degrade_or_raise(f"GraphSAGE model unavailable: {exc}")

    def _degrade_or_raise(self, reason: str) -> None:
        if settings.require_ml_model and not settings.demo_allow_mock_ml:
            raise RuntimeError(reason)
        self.model = None
        self.mode = "degraded"
        self.degraded_reason = reason

    def health(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "weights_path": self.weights_path,
            "degraded_reason": self.degraded_reason or None,
        }

    def predict(self, flows: list[Any]) -> dict[str, Any]:
        if self.model is None or self.torch is None:
            return self._heuristic_predict(flows)

        graph = build_pyg_graph(flows)
        if graph.x.shape[0] == 0:
            return {"flow_scores": [], "ip_scores": {}, "source_scores": {}}

        try:
            with self.torch.no_grad():
                if hasattr(self.model, "predict_proba"):
                    probs = self.model.predict_proba(graph.x, graph.edge_index)
                else:
                    logits = self.model(graph.x, graph.edge_index)
                    probs = self.torch.softmax(logits, dim=1)[:, 1]
            # Clamp NaN/Inf scores to prevent propagation through threat analysis
            scores = [
                round(max(0.0, min(float(v), 1.0)), 4) if not (v != v) else 0.0  # NaN != NaN
                for v in probs.tolist()
            ]
        except Exception as exc:
            self.mode = "degraded"
            self.degraded_reason = f"Inference failed; using heuristic fallback: {exc}"
            return self._heuristic_predict(flows)

        flow_scores = [
            {
                "flow_index": index,
                "src_ip": graph.flow_sources[index],
                "dst_ip": graph.flow_destinations[index],
                "score": score,
            }
            for index, score in enumerate(scores)
        ]
        source_scores = self._aggregate_source_scores(flow_scores)
        ip_scores = self._aggregate_ip_scores(flow_scores)
        return {
            "flow_scores": flow_scores,
            "ip_scores": ip_scores,
            "source_scores": source_scores,
            "mode": self.mode,
            "degraded_reason": self.degraded_reason or None,
        }

    def _heuristic_predict(self, flows: list[Any]) -> dict[str, Any]:
        flow_records = [
            flow.model_dump() if hasattr(flow, "model_dump") else flow.dict() if hasattr(flow, "dict") else dict(flow)
            for flow in flows
        ]
        flow_scores = [
            {
                "flow_index": index,
                "src_ip": str(flow.get("src_ip")),
                "dst_ip": str(flow.get("dst_ip")),
                "score": self._heuristic_score(flow),
            }
            for index, flow in enumerate(flow_records)
        ]
        return {
            "flow_scores": flow_scores,
            "ip_scores": self._aggregate_ip_scores(flow_scores),
            "source_scores": self._aggregate_source_scores(flow_scores),
            "mode": self.mode,
            "degraded_reason": self.degraded_reason or None,
        }

    def _heuristic_score(self, flow: dict[str, Any]) -> float:
        packets = float(flow.get("packet_count") or 0)
        bytes_count = float(flow.get("byte_count") or 0)
        duration = max(float(flow.get("duration_sec") or 1.0), 0.001)
        dst_port = int(flow.get("dst_port") or 0)
        tcp_flags = int(flow.get("tcp_flags") or 0)
        bytes_per_s = bytes_count / duration

        score = 0.04
        score += min(packets / 15000.0, 0.42)
        score += min(bytes_per_s / 8_000_000.0, 0.28)
        if dst_port in {22, 23, 80, 443, 8080}:
            score += 0.08
        if tcp_flags & 2:
            score += 0.08
        if packets > 5000 and duration < 5:
            score += 0.14
        return round(min(score, 0.98), 4)

    @staticmethod
    def _aggregate_source_scores(flow_scores: list[dict[str, Any]]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for flow in flow_scores:
            src = flow["src_ip"]
            scores[src] = max(scores.get(src, 0.0), float(flow["score"]))
        return scores

    @staticmethod
    def _aggregate_ip_scores(flow_scores: list[dict[str, Any]]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for flow in flow_scores:
            src = flow["src_ip"]
            dst = flow["dst_ip"]
            score = float(flow["score"])
            scores[src] = max(scores.get(src, 0.0), score)
            scores[dst] = max(scores.get(dst, 0.0), round(score * 0.25, 4))
        return scores


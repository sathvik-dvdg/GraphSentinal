"""
Streaming inference engine.

The thing the backend talks to. It takes raw flow records -- from a live
capture, a CICFlowMeter socket, a Kafka topic, or a replayed CSV -- and returns
scored hosts, scored flows, and installable SDN rules.

Nothing here is coupled to a feature count or a class name. The engine loads a
model card (JSON) alongside the weights and derives its contract from that, so
a v3 model with different features drops in without a backend change.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import torch

from ..config import CLASS_NAMES, Config
from ..data.graph_builder import (
    EDGE_FEATURE_NAMES,
    NODE_FEATURE_NAMES,
    GraphBuilder,
    HostHistory,
)
from ..models.net import GraphSentinelNet, build_model
from .ema_scaler import EMAScaler
from .sdn import FlowRule, SDNTranslator


@dataclass
class Detection:
    ip: str
    attack_class: str
    threat_score: float
    class_probs: Dict[str, float]
    out_degree: int
    in_degree: int
    window_start: float
    window_end: float


@dataclass
class FlowVerdict:
    """One REAL flow, scored by the edge head.

    WHY THIS EXISTS (added 2026-09-13 after a backend integration audit).

    Until now the only things that left this engine were ``detections`` -- built
    entirely from the NODE head -- and ``rules``, which the SDN translator emits
    only for flows that clear a per-class confidence floor AND a node-head
    corroboration gate. So the edge head, which is the deliverable of this
    model, had no way out of the API at all.

    That is backwards. On the held-out test split the edge head scores
    macro F1 0.7042 and binary F1 0.9974; the node head scores binary F1 0.1407
    with PR-AUC below the base rate for three of four attack classes. A backend
    consuming this engine was being handed the weak head and denied the strong
    one.

    Reverse (mirror) edges are excluded -- they carry no independent flow, only
    the same flow pointing the other way so messages can travel both directions.
    """

    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: int
    attack_class: str
    confidence: float          # P(argmax class)
    threat_score: float        # 1 - P(BENIGN); the binary gate applies here
    class_probs: Dict[str, float]


@dataclass
class WindowResult:
    window_start: float
    window_end: float
    n_flows: int
    n_hosts: int
    detections: List[Detection] = field(default_factory=list)
    rules: List[FlowRule] = field(default_factory=list)
    drift: Optional[dict] = None
    latency_ms: float = 0.0
    #: Per-flow verdicts from the EDGE head. This is the field a backend should
    #: consume; ``detections`` is node-level and much weaker (see FlowVerdict).
    flows: List[FlowVerdict] = field(default_factory=list)
    #: True when the window held fewer than cfg.graph.min_edges_per_graph flows,
    #: so no graph could be built and nothing was scored. Silence and "nothing
    #: found" must not look the same to an operator.
    unscored: bool = False

    def to_dict(self) -> dict:
        return {
            "window_start": self.window_start,
            "window_end": self.window_end,
            "n_flows": self.n_flows,
            "n_hosts": self.n_hosts,
            "latency_ms": self.latency_ms,
            "drift": self.drift,
            "unscored": self.unscored,
            "flows": [f.__dict__ for f in self.flows],
            "detections": [d.__dict__ for d in self.detections],
            "rules": [r.to_dict() for r in self.rules],
            "openflow": [r.to_openflow() for r in self.rules],
        }


class InferenceEngine:
    """Stateful, window-at-a-time inference with persistent host memory."""

    def __init__(
        self,
        model: GraphSentinelNet,
        cfg: Config,
        edge_scaler: Optional[EMAScaler] = None,
        node_scaler: Optional[EMAScaler] = None,
        translator: Optional[SDNTranslator] = None,
        device: Optional[torch.device] = None,
        threat_threshold: float = 0.75,
    ):
        self.cfg = cfg
        self.device = device or torch.device("cpu")
        self.model = model.to(self.device).eval()
        self.edge_scaler = edge_scaler
        self.node_scaler = node_scaler
        self.translator = translator or SDNTranslator()
        self.threat_threshold = threat_threshold
        self.builder = GraphBuilder(cfg, history=HostHistory(capacity=cfg.model.memory_capacity))
        self._buffer: List[dict] = []
        self._window_end: Optional[float] = None
        self.stats = {"windows": 0, "flows": 0, "detections": 0, "rules": 0}

    # ------------------------------------------------------------------
    @classmethod
    def from_artifacts(
        cls,
        model_dir: str | Path,
        device: Optional[torch.device] = None,
        **kwargs,
    ) -> "InferenceEngine":
        """Load weights + model card + scalers from an export directory."""
        model_dir = Path(model_dir)
        card = json.loads((model_dir / "model_card.json").read_text(encoding="utf-8"))
        cfg = Config.from_dict(card["config"])
        model = build_model(cfg)
        state = torch.load(model_dir / "weights.pt", map_location="cpu", weights_only=False)
        model.load_state_dict(state["model"] if "model" in state else state)

        # GUARD: CLASS_NAMES is a MUTABLE module-level list that
        # Config.from_dict rewrites in place, and both _detections() and
        # sdn.translate() index into it. Anything that read it before the
        # Config existed holds the stale six-class list, where the indices
        # collide catastrophically:
        #     index 1  DDoS      -> Volumetric_Flood
        #     index 3  Botnet    -> BruteForce
        #     index 4  SSHBrute  -> Botnet
        # A BruteForce flow read through the stale list is labelled Botnet,
        # and Botnet carries the most aggressive mitigation in the policy
        # table (drop_and_quarantine) at the lowest confidence floor. Failing
        # here is the only acceptable outcome.
        expected = card.get("outputs", {}).get("classes")
        if expected and list(CLASS_NAMES) != list(expected):
            raise RuntimeError(
                "Class list mismatch after loading the model card.\n"
                f"  card says : {expected}\n"
                f"  live list : {list(CLASS_NAMES)}\n"
                "CLASS_NAMES is mutated in place by Config.from_dict; some "
                "module read it before that happened. Import order is wrong, "
                "and every class label downstream would be silently shifted."
            )

        edge_scaler = node_scaler = None
        if (model_dir / "edge_scaler.json").exists():
            edge_scaler = EMAScaler.load(model_dir / "edge_scaler.json")
        if (model_dir / "node_scaler.json").exists():
            node_scaler = EMAScaler.load(model_dir / "node_scaler.json")

        return cls(model, cfg, edge_scaler, node_scaler, device=device, **kwargs)

    # ------------------------------------------------------------------
    def ingest(self, flows: Sequence[dict] | pd.DataFrame) -> List[WindowResult]:
        """Push flows in; get a result each time a window closes.

        Windows close on wall-clock, so a quiet minute still produces a (small)
        graph and a busy minute does not silently grow without bound.
        """
        records = (
            flows.to_dict("records") if isinstance(flows, pd.DataFrame) else list(flows)
        )
        results: List[WindowResult] = []
        w = self.cfg.graph.window_seconds

        for rec in records:
            t = float(rec.get("t", rec.get("Timestamp", time.time())))
            if self._window_end is None:
                self._window_end = (int(t) // w + 1) * w
            while t >= self._window_end:
                if self._buffer:
                    results.append(self._close_window())
                self._window_end += w
            self._buffer.append(rec)
        return results

    def flush(self) -> Optional[WindowResult]:
        return self._close_window() if self._buffer else None

    # ------------------------------------------------------------------
    def _close_window(self) -> WindowResult:
        t0 = time.perf_counter()
        df = pd.DataFrame(self._buffer)
        self._buffer = []
        w_end = float(self._window_end or df["t"].max())
        w_start = w_end - self.cfg.graph.window_seconds

        df = self._coerce(df)
        graphs = self.builder.build(df, update_history=True, verbose=False)
        if not graphs:
            # The builder returns nothing when the window holds fewer than
            # cfg.graph.min_edges_per_graph flows (default 8). Those flows are
            # NOT scored, and a caller must be able to tell that apart from
            # "scored, found nothing" -- otherwise a quiet-but-unscored minute
            # reads as a clean bill of health.
            return WindowResult(w_start, w_end, len(df), 0, latency_ms=0.0,
                                unscored=True)
        data = graphs[0]

        drift = None
        if self.edge_scaler is not None:
            ea = data.edge_attr.numpy()
            report = self.edge_scaler.partial_fit(ea, t=w_end)
            data.edge_attr = torch.from_numpy(self.edge_scaler.transform(ea))
            drift = report.__dict__
        if self.node_scaler is not None:
            nx = data.x.numpy()
            self.node_scaler.partial_fit(nx, t=w_end)
            data.x = torch.from_numpy(self.node_scaler.transform(nx))

        data = data.to(self.device)
        out = self.model.predict(data, now=int(w_end))

        node_ips = [_int_to_ip(int(i)) for i in data.node_ip_int.cpu().tolist()]
        detections = self._detections(out, data, node_ips, w_start, w_end)

        rules: List[FlowRule] = []
        if "edge_probs" in out and "node_probs" in out:
            rules = self.translator.translate(
                edge_probs=out["edge_probs"],
                node_probs=out["node_probs"],
                edge_index=data.edge_index,
                node_ips=node_ips,
                dst_ports=_port_numbers(df, "Destination Port", data),
                src_ports=_port_numbers(df, "Source Port", data),
                protocols=_port_numbers(df, "Protocol", data),
                real_edge_mask=data.real_edge_mask.cpu().numpy(),
                window_start=w_start,
                window_end=w_end,
            )

        self.stats["windows"] += 1
        self.stats["flows"] += len(df)
        self.stats["detections"] += len(detections)
        self.stats["rules"] += len(rules)

        flows = self._flow_verdicts(out, data, node_ips, df)

        return WindowResult(
            window_start=w_start,
            window_end=w_end,
            n_flows=len(df),
            n_hosts=int(data.num_nodes),
            detections=detections,
            rules=rules,
            drift=drift,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            flows=flows,
        )

    def _flow_verdicts(self, out, data, node_ips, df) -> List["FlowVerdict"]:
        """Edge-head verdict for every REAL flow in the window.

        No threshold is applied here on purpose. The engine reports what the
        model said; deciding what clears a gate is the caller's policy, and
        baking a threshold in at this layer is how an operating point ends up
        duplicated in three places with three different values.
        """
        if "edge_probs" not in out:
            return []
        ep = out["edge_probs"].detach().cpu().numpy()
        mask = getattr(data, "real_edge_mask", None)
        idx = (np.where(np.asarray(mask.cpu()))[0] if mask is not None
               else np.arange(ep.shape[0]))
        if idx.size == 0:
            return []

        ei = data.edge_index.cpu().numpy()
        dports = _port_numbers(df, "Destination Port", data)
        sports = _port_numbers(df, "Source Port", data)
        protos = _port_numbers(df, "Protocol", data)

        verdicts: List[FlowVerdict] = []
        for e in idx.tolist():
            probs = ep[e]
            k = int(probs.argmax())
            verdicts.append(
                FlowVerdict(
                    src_ip=str(node_ips[int(ei[0, e])]),
                    dst_ip=str(node_ips[int(ei[1, e])]),
                    src_port=int(sports[e]),
                    dst_port=int(dports[e]),
                    protocol=int(protos[e]),
                    attack_class=CLASS_NAMES[k],
                    confidence=float(probs[k]),
                    threat_score=float(1.0 - probs[0]),
                    class_probs={c: float(probs[j])
                                 for j, c in enumerate(CLASS_NAMES)},
                )
            )
        return verdicts

    def _detections(self, out, data, node_ips, w_start, w_end) -> List[Detection]:
        if "node_probs" not in out:
            return []
        probs = out["node_probs"].cpu().numpy()
        threat = out["node_threat"].cpu().numpy()
        pred = out["node_pred"].cpu().numpy()
        # Count REAL flows only. edge_index also holds the reverse mirror of every
        # flow (added so messages travel both ways), so counting it whole makes
        # out_degree == in_degree for every host -- which hides the single most
        # diagnostic fact in the output: a scanner has huge fan-OUT and almost no
        # fan-in, a DDoS victim the reverse.
        mask = getattr(data, "real_edge_mask", None)
        ei = data.edge_index[:, mask] if mask is not None else data.edge_index
        out_deg = torch.bincount(ei[0].cpu(), minlength=data.num_nodes).numpy()
        in_deg = torch.bincount(ei[1].cpu(), minlength=data.num_nodes).numpy()

        hits = np.where(threat >= self.threat_threshold)[0]
        order = hits[np.argsort(-threat[hits])]
        return [
            Detection(
                ip=node_ips[i],
                attack_class=CLASS_NAMES[int(pred[i])],
                threat_score=float(threat[i]),
                class_probs={c: float(probs[i, j]) for j, c in enumerate(CLASS_NAMES)},
                out_degree=int(out_deg[i]),
                in_degree=int(in_deg[i]),
                window_start=w_start,
                window_end=w_end,
            )
            for i in order.tolist()
        ]

    @staticmethod
    def _coerce(df: pd.DataFrame) -> pd.DataFrame:
        if "t" not in df.columns:
            df["t"] = pd.to_datetime(df["Timestamp"]).astype("int64") // 10**9
        if "y" not in df.columns:
            df["y"] = 0  # unlabelled at inference time
        for col in ("Source IP", "Destination IP"):
            df[col] = df[col].astype(str)
        return df.sort_values("t").reset_index(drop=True)


def _int_to_ip(v: int) -> str:
    return ".".join(str((v >> s) & 0xFF) for s in (24, 16, 8, 0))


def _port_numbers(df: pd.DataFrame, col: str, data) -> np.ndarray:
    """Align a raw per-flow column to the (possibly mirrored) edge ordering."""
    n_real = int(data.real_edge_mask.sum().item())
    vals = (
        pd.to_numeric(df[col], errors="coerce").fillna(0).to_numpy(dtype=np.int64)
        if col in df.columns
        else np.zeros(n_real, dtype=np.int64)
    )
    vals = vals[:n_real] if len(vals) >= n_real else np.pad(vals, (0, n_real - len(vals)))
    total = data.edge_index.size(1)
    return np.concatenate([vals, vals])[:total] if total > n_real else vals

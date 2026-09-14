# [WSL2]
"""HTTP client for the GraphSentinel v2 inference service.

WHY HTTP AND NOT AN IMPORT

`InferenceEngine` is stateful: it holds a flow buffer, a 60 s window boundary,
and a persistent host-memory module keyed by IP. The backend has two concurrent
entry points — the `MininetMonitor` daemon thread and `/api/v1/analyze` request
handlers — which in-process would interleave into ONE shared window buffer with
no coordination. That is a correctness bug, not a deployment preference. The
service owns that lifecycle in a single process.

It also keeps torch out of the backend image, and keeps `ML/graphsentinel_v2`
importable-from-nowhere: no `sys.path` insertion of the kind that already rotted
into dead code at `inference_service._load_model_class()`.

WHY THERE IS NO FALLBACK

When the service is unreachable this client reports UNAVAILABLE and the caller
stops producing scores. It does NOT fall back to `_heuristic_predict()`. A
hand-tuned formula emitting numbers that look like model output, into the same
incidents table, that then block IPs, is worse than an outage: the operator
cannot tell the two apart from the API response. The v1 path keeps its own
fallback; nothing here inherits it.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings
from app.services.flow_mapping import map_flows

_log = logging.getLogger("graphsentinel.inference_v2")

#: How many recent windows the unscored rate is averaged over.
_UNSCORED_HISTORY = 200


class InferenceUnavailable(RuntimeError):
    """The inference service could not be reached or returned an error.

    Callers must treat this as "no scores this poll", never as "no threats".
    """


@dataclass
class FlowVerdict:
    """One scored flow from the EDGE head. Mirrors the engine's FlowVerdict.

    The node head is deliberately not represented here. Its test binary F1 is
    0.1407 with PR-AUC below the base rate for three of four attack classes; it
    is not fit for any decision and must not be exposed.
    """

    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: int
    attack_class: str
    confidence: float
    threat_score: float          # 1 - P(BENIGN)
    class_probs: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, d: dict[str, Any]) -> "FlowVerdict":
        return cls(
            src_ip=str(d.get("src_ip", "")),
            dst_ip=str(d.get("dst_ip", "")),
            src_port=int(d.get("src_port") or 0),
            dst_port=int(d.get("dst_port") or 0),
            protocol=int(d.get("protocol") or 0),
            attack_class=str(d.get("attack_class", "")),
            confidence=float(d.get("confidence") or 0.0),
            threat_score=float(d.get("threat_score") or 0.0),
            class_probs={str(k): float(v) for k, v in (d.get("class_probs") or {}).items()},
        )


@dataclass
class WindowOutcome:
    """One closed window as the backend sees it."""

    window_start: float
    window_end: float
    n_flows: int
    n_hosts: int
    #: True when the window held fewer flows than the builder's
    #: `min_edges_per_graph` floor, so NO graph was built and nothing was
    #: scored. An unscored window is NOT a clean bill of health.
    unscored: bool
    flows: list[FlowVerdict] = field(default_factory=list)
    latency_ms: float = 0.0

    @classmethod
    def from_payload(cls, d: dict[str, Any]) -> "WindowOutcome":
        return cls(
            window_start=float(d.get("window_start") or 0.0),
            window_end=float(d.get("window_end") or 0.0),
            n_flows=int(d.get("n_flows") or 0),
            n_hosts=int(d.get("n_hosts") or 0),
            unscored=bool(d.get("unscored", False)),
            # `flows` is the EDGE head. `detections` in the same payload is the
            # NODE head and is deliberately never read.
            flows=[FlowVerdict.from_payload(f) for f in (d.get("flows") or [])],
            latency_ms=float(d.get("latency_ms") or 0.0),
        )


class InferenceClient:
    """Process-wide client for the v2 inference service."""

    _instance: "InferenceClient | None" = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "InferenceClient":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Drop the singleton. Used by tests; never call from request handlers."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.gs2_service_url).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.gs2_request_timeout_seconds
        self._client = httpx.Client(timeout=self.timeout)
        self.last_error: str | None = None
        self.last_success_at: float | None = None
        # Rolling record of whether each recent window was scored, so /health can
        # report the unscored RATE rather than just the last window's flag.
        self._window_log: deque[bool] = deque(maxlen=_UNSCORED_HISTORY)
        self._counters = {"windows": 0, "unscored": 0, "flows_sent": 0, "map_errors": 0}
        #: True once the service's /contract has been checked against the
        #: backend's validated card. Scoring does not proceed until it is.
        self.contract_verified: bool = False

    # ------------------------------------------------------------------
    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # noqa: BLE001 - closing must never raise into a caller
            pass

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._client.post(url, json=payload)
            response.raise_for_status()
            self.last_error = None
            self.last_success_at = time.time()
            return response.json()
        except httpx.HTTPStatusError as exc:
            self.last_error = f"{exc.response.status_code} from {url}: {exc.response.text[:200]}"
            raise InferenceUnavailable(self.last_error) from exc
        except (httpx.HTTPError, ValueError) as exc:
            self.last_error = f"{type(exc).__name__} contacting {url}: {exc}"
            raise InferenceUnavailable(self.last_error) from exc

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._client.get(url)
            response.raise_for_status()
            self.last_error = None
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            self.last_error = f"{type(exc).__name__} contacting {url}: {exc}"
            raise InferenceUnavailable(self.last_error) from exc

    # ------------------------------------------------------------------
    def fetch_contract(self) -> dict[str, Any]:
        """GET /contract — the service's own copy of model_card.json.

        Used at startup to confirm the service is serving the SAME contract the
        backend validated on disk. Two different cards would mean the backend
        maps logit indices with one class list while the service labels with
        another.
        """
        return self._get("/contract")

    def submit(self, flows: list[Any], observed_at: float | None = None) -> list[WindowOutcome]:
        """POST a batch of FlowRecords; return any windows that closed.

        An empty list of outcomes means "no window closed yet", NOT "nothing
        found" — the engine buffers until a 60 s boundary is crossed.

        Raises InferenceUnavailable if the service cannot be reached. The caller
        must stop scoring; it must not substitute a heuristic.
        """
        mapped, errors = map_flows(flows, observed_at=observed_at)
        if errors:
            # Visible in logs by requirement: a silently dropped flow is a
            # missed detection, not a tidy no-op.
            self._counters["map_errors"] += len(errors)
            for message in errors[:10]:
                _log.warning("flow dropped before inference: %s", message)
            if len(errors) > 10:
                _log.warning("... and %d more flows dropped this batch", len(errors) - 10)

        if not mapped:
            return []

        payload = self._post("/flows", {"flows": mapped})
        self._counters["flows_sent"] += len(mapped)

        outcomes = [WindowOutcome.from_payload(r) for r in (payload.get("results") or [])]
        for outcome in outcomes:
            self._counters["windows"] += 1
            self._window_log.append(outcome.unscored)
            if outcome.unscored:
                self._counters["unscored"] += 1
                _log.warning(
                    "window [%.0f,%.0f] held %d flows, below the graph builder's "
                    "minimum — NOT SCORED. This is not a clean window.",
                    outcome.window_start, outcome.window_end, outcome.n_flows,
                )
        return outcomes

    def flush(self) -> WindowOutcome | None:
        """POST /flush — force-close the current partial window."""
        payload = self._post("/flush", {})
        result = payload.get("result")
        if not result:
            return None
        outcome = WindowOutcome.from_payload(result)
        self._counters["windows"] += 1
        self._window_log.append(outcome.unscored)
        if outcome.unscored:
            self._counters["unscored"] += 1
        return outcome

    # ------------------------------------------------------------------
    @property
    def unscored_rate(self) -> float | None:
        """Fraction of recent windows that could not be scored.

        None until at least one window has closed. A meaningful rate here means
        the capture is too sparse for a 60 s window, and the operator needs to
        know that rather than read silence as safety.
        """
        if not self._window_log:
            return None
        return sum(1 for u in self._window_log if u) / len(self._window_log)

    def probe(self) -> bool:
        """Ask the service whether it is up AND has a model loaded.

        The service's /health returns 503 until `from_artifacts` has succeeded,
        so a 200 here means "can score", not merely "socket open". A live probe
        is needed because a quiet network never POSTs anything, and "no request
        has succeeded yet" must not read as "service down".
        """
        try:
            response = self._client.get(f"{self.base_url}/health", timeout=min(self.timeout, 3.0))
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def health(self) -> dict[str, Any]:
        rate = self.unscored_rate
        return {
            "service_url": self.base_url,
            "reachable": self.probe(),
            "last_error": self.last_error,
            "last_success_at": self.last_success_at,
            "windows_seen": self._counters["windows"],
            "windows_unscored": self._counters["unscored"],
            "unscored_rate": None if rate is None else round(rate, 4),
            "flows_sent": self._counters["flows_sent"],
            "flows_dropped_in_mapping": self._counters["map_errors"],
        }

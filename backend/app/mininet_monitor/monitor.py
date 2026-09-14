# [WSL2]
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.mininet_monitor.flow_parser import parse_ovs_flows
from app.services.analysis_pipeline import analyze_flows
from app.websocket.events import emit_analysis_events


class MininetMonitor:
    def __init__(self, sio, gs2_state=None):
        self.sio = sio
        self.interval = settings.poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        # Error.md #11: track poll history so /health can tell the operator
        # whether capture is live, empty, or failing — instead of the UI
        # just silently showing whatever graph state happened to be last.
        self.last_poll_at: str | None = None
        self.last_flow_count: int = 0
        self.last_error: str | None = None
        # v2 scoring runs alongside v1 on the same real flows. Additive: a
        # failure here must never stop the v1 poll, and v2 never falls back to
        # a heuristic when its service is down.
        self.gs2_state = gs2_state
        self.last_v2_error: str | None = None
        self.last_v2_windows: int = 0

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2)

    def health(self) -> dict[str, Any]:
        return {
            "last_poll_at": self.last_poll_at,
            "last_flow_count": self.last_flow_count,
            "last_error": self.last_error,
            "v2_last_error": self.last_v2_error,
            "v2_windows_closed": self.last_v2_windows,
        }

    def _score_v2(self, flows: list, observed_at: float) -> None:
        """Submit the same real flows to the v2 path. Never raises into the poll.

        A quiet poll produces no closed window — the engine buffers until a 60s
        boundary is crossed — so "no windows" here is normal and is NOT a
        finding. A window that closes BELOW the graph builder's minimum flow
        count comes back `unscored`, which is surfaced rather than read as clean.
        """
        state = self.gs2_state
        if state is None or not state.ready:
            return
        # Imported lazily so a backend without the v2 artefacts still starts.
        from app.services.analysis_pipeline_v2 import score_flows

        result = score_flows(flows, state, observed_at=observed_at)
        if not result.get("available"):
            self.last_v2_error = result.get("reason")
            return
        self.last_v2_error = None
        self.last_v2_windows += result.get("closed_windows", 0)

    def _run(self) -> None:
        print(f"[Monitor] Polling OVS every {self.interval}s")
        while not self._stop_event.is_set():
            try:
                observed_at = time.time()
                flows = parse_ovs_flows(settings.enforcement_switch)
                # Always analyze — even an empty batch — so graph state
                # reflects "no current traffic" instead of leaving stale
                # threats/nodes on screen after traffic actually stops.
                result = analyze_flows(flows)
                asyncio.run(emit_analysis_events(self.sio, result))
                # v2 runs on the SAME real flows, sharing this poll's
                # observation time: FlowRecord carries no timestamp, and `t`
                # drives both windowing and five of the model's features.
                # Isolated so a v2 failure cannot take down the v1 poll.
                try:
                    self._score_v2(flows, observed_at)
                except Exception as exc:  # noqa: BLE001 - must not kill the thread
                    self.last_v2_error = str(exc)
                    print(f"[Monitor] v2 scoring error: {exc}")
                self.last_poll_at = datetime.now(timezone.utc).isoformat()
                self.last_flow_count = len(flows)
                self.last_error = None
            except Exception as exc:
                self.last_error = str(exc)
                print(f"[Monitor] Tick error: {exc}")
            time.sleep(self.interval)


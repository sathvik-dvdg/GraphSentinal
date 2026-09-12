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
    def __init__(self, sio):
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
        }

    def _run(self) -> None:
        print(f"[Monitor] Polling OVS every {self.interval}s")
        while not self._stop_event.is_set():
            try:
                flows = parse_ovs_flows(settings.enforcement_switch)
                # Always analyze — even an empty batch — so graph state
                # reflects "no current traffic" instead of leaving stale
                # threats/nodes on screen after traffic actually stops.
                result = analyze_flows(flows)
                asyncio.run(emit_analysis_events(self.sio, result))
                self.last_poll_at = datetime.now(timezone.utc).isoformat()
                self.last_flow_count = len(flows)
                self.last_error = None
            except Exception as exc:
                self.last_error = str(exc)
                print(f"[Monitor] Tick error: {exc}")
            time.sleep(self.interval)


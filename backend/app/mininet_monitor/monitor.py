# [WSL2]
from __future__ import annotations

import asyncio
import threading
import time

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

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        print(f"[Monitor] Polling OVS every {self.interval}s")
        while not self._stop_event.is_set():
            try:
                flows = parse_ovs_flows(settings.enforcement_switch)
                if flows:
                    result = analyze_flows(flows)
                    asyncio.run(emit_analysis_events(self.sio, result))
            except Exception as exc:
                print(f"[Monitor] Tick error: {exc}")
            time.sleep(self.interval)


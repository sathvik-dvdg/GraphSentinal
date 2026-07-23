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
    def __init__(self, sio, loop):
        self.sio = sio
        self.loop = loop  # the Uvicorn main event loop — sio was created on this loop
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
                    # Schedule sio.emit() on the main Uvicorn loop where sio was created.
                    # asyncio.run() would spin up a foreign loop — AsyncServer internals are
                    # bound to self.loop, making that pattern a silent failure on every tick.
                    future = asyncio.run_coroutine_threadsafe(
                        emit_analysis_events(self.sio, result), self.loop
                    )
                    future.result(timeout=10)  # propagate exceptions; 10s hard ceiling
            except Exception as exc:
                print(f"[Monitor] Tick error: {exc}")
            time.sleep(self.interval)

# [WSL2]
from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.mininet_monitor.flow_parser import parse_ovs_flows
from app.models.schemas import FlowRecord
from app.services.analysis_pipeline import analyze_flows
from app.websocket.events import emit_analysis_events

_log = logging.getLogger("graphsentinel.monitor")

# ── v2 provenance gate ────────────────────────────────────────────────────────
# The ONLY source the v2 path accepts. An allowlist, not a denylist: a source
# added later that forgets to tag its flows must be refused, not admitted.
V2_ALLOWED_SOURCE = "ovs"

# What FlowRecord itself assigns when a flow carries no `data_source`. Read from
# the schema rather than restated, so an untagged flow is judged by exactly the
# value validation would give it -- and that value is not "ovs", so it is refused.
_UNTAGGED_SOURCE = FlowRecord.model_fields["data_source"].default

# While refusal persists, repeat the WARNING at most this often. Every poll would
# be 720 lines an hour, which teaches people to ignore it.
_REFUSAL_REMINDER_SECONDS = 60.0

# last_poll_state values, reported under /health -> monitor.v2_provenance.
V2_SUBMITTED = "submitted"
V2_REFUSED_NON_OVS = "refused_non_ovs"
V2_NOTHING_TO_SCORE = "nothing_to_score"
V2_DISABLED = "v2_disabled"


def _source_of(flow: Any) -> Any:
    """The provenance tag of one flow, with FlowRecord's default for a missing tag.

    Deliberately reads only this field rather than validating the whole record:
    a flow whose provenance is "ovs" but whose IP is malformed is a data problem,
    handled by flow_mapping dropping that one flow with a logged reason. It must
    not be reported as a provenance refusal of the entire poll.
    """
    if isinstance(flow, dict):
        return flow.get("data_source", _UNTAGGED_SOURCE)
    return getattr(flow, "data_source", _UNTAGGED_SOURCE)


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
        # v2 scoring runs alongside v1 on the same poll. Additive: a failure
        # here must never stop the v1 poll, and v2 never falls back to a
        # heuristic when its service is down.
        self.gs2_state = gs2_state
        self.last_v2_error: str | None = None
        self.last_v2_windows: int = 0
        # Provenance gate state -- deliberately separate from the client's
        # unscored_rate. "Refused: input not from OVS" and "nothing to score"
        # must never look alike.
        self.v2_last_poll_state: str = V2_DISABLED
        self.v2_batches_refused_non_ovs: int = 0
        self.v2_flows_refused_non_ovs: int = 0
        self.v2_last_refused_sources: dict[str, int] = {}
        self.v2_last_refused_at: str | None = None
        self._v2_refusing_since: float | None = None
        self._v2_last_refusal_warning: float | None = None
        # Injectable so the once-a-minute reminder can be tested without sleeping.
        self._clock = time.monotonic

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
            "v2_provenance": {
                "last_poll_state": self.v2_last_poll_state,
                "allowed_source": V2_ALLOWED_SOURCE,
                "batches_refused_non_ovs": self.v2_batches_refused_non_ovs,
                "flows_refused_non_ovs": self.v2_flows_refused_non_ovs,
                "last_refused_sources": dict(self.v2_last_refused_sources),
                "last_refused_at": self.v2_last_refused_at,
            },
        }

    def _set_v2_state(self, new_state: str) -> None:
        """Record the poll's v2 outcome, logging when refusal ENDS.

        Without the recovery line a reader sees the refusal warnings stop and
        cannot tell recovery from a dead monitor.
        """
        if self.v2_last_poll_state == V2_REFUSED_NON_OVS and new_state != V2_REFUSED_NON_OVS:
            since = self._v2_refusing_since
            lasted = (self._clock() - since) if since is not None else 0.0
            _log.info(
                "v2 provenance gate: stopped refusing after %.0fs; now %s",
                lasted, new_state,
            )
            self._v2_refusing_since = None
            self._v2_last_refusal_warning = None
        self.v2_last_poll_state = new_state

    def _refuse_v2(self, sources: Counter, n_flows: int) -> None:
        """Refuse the whole batch before anything leaves the process. Loudly."""
        now = self._clock()
        tally = {str(k): int(v) for k, v in sources.items()}
        self.v2_batches_refused_non_ovs += 1
        self.v2_flows_refused_non_ovs += n_flows
        self.v2_last_refused_sources = tally
        self.v2_last_refused_at = datetime.now(timezone.utc).isoformat()

        if self.v2_last_poll_state != V2_REFUSED_NON_OVS:
            self._v2_refusing_since = now
            self._v2_last_refusal_warning = now
            _log.warning(
                "v2 provenance gate: REFUSING poll -- input not from OVS "
                "(sources %s, %d flows). Nothing from this poll reaches the "
                "inference service. This is not a quiet network.",
                tally, n_flows,
            )
        elif (self._v2_last_refusal_warning is None
              or now - self._v2_last_refusal_warning >= _REFUSAL_REMINDER_SECONDS):
            self._v2_last_refusal_warning = now
            since = self._v2_refusing_since if self._v2_refusing_since is not None else now
            _log.warning(
                "v2 provenance gate: still refusing after %.0fs -- input not "
                "from OVS (last poll sources %s).",
                now - since, tally,
            )
        self.v2_last_poll_state = V2_REFUSED_NON_OVS

    def _score_v2(self, flows: list, observed_at: float) -> None:
        """Hand this poll's flows to the v2 path -- only if they came from OVS.

        Never raises into the poll.

        THE GATE. `parse_ovs_flows` can return randomised flows from
        `demo_flows()` in place of a real poll (DEMO_FALLBACK_FLOWS), and
        `map_flow` does not carry `data_source` into the record the service
        receives, so the service cannot tell. The check therefore happens here,
        at the single producer, before anything is mapped or sent:

          * allowlist -- `data_source == "ovs"`, never `!= "demo"`;
          * fail closed -- an untagged flow gets FlowRecord's default, which is
            not "ovs", so it is refused;
          * whole batch -- `parse_ovs_flows` never mixes sources, so a mixed
            batch means something upstream changed; none of it is salvaged.

        The service request carries no provenance field, by construction: the
        check reads the tag here, so it does not depend on a mapping surviving a
        refactor. And it fails in the loud direction -- if a refactor ever stops
        `flow_parser` tagging real flows "ovs", every poll is refused with a
        WARNING rather than randomised input being admitted. Deleting the gate
        itself is what `tests/test_v2_provenance_gate.py` exists to catch.

        A quiet poll produces no closed window -- the engine buffers until a 60s
        boundary is crossed -- so "no windows" is normal, not a finding. A window
        that closes BELOW the graph builder's minimum flow count comes back
        `unscored`, which is surfaced rather than read as clean.
        """
        state = self.gs2_state
        if state is None or not state.ready:
            self._set_v2_state(V2_DISABLED)
            return
        if not flows:
            self._set_v2_state(V2_NOTHING_TO_SCORE)
            return

        sources = Counter(_source_of(f) for f in flows)
        if any(src != V2_ALLOWED_SOURCE for src in sources):
            self._refuse_v2(sources, len(flows))
            return

        self._set_v2_state(V2_SUBMITTED)
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
                # v2 sees this poll's flows ONLY if they came from OVS: with
                # DEMO_FALLBACK_FLOWS on, `flows` can be randomised output of
                # demo_flows(), which _score_v2 refuses before anything is sent.
                # Accepted flows share this poll's observation time: FlowRecord
                # carries no timestamp, and `t` drives windowing and five of the
                # model's features. Isolated so a v2 failure cannot take down
                # the v1 poll.
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


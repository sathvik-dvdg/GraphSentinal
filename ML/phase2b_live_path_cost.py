"""
PHASE 2b — what the live capture path costs, measured rather than argued.

WHY THIS ALSO COVERS THE OVS RE-COUNTING QUESTION.

INTEGRATION.md §5 said the poll re-counting effect "cannot be measured by
PHASE 2b -- CICIDS2017 rows are distinct flows". True of the rows as they
stand, and it does not have to stay true. The mechanism is fully specified by
the backend's own code: `ovs-ofctl dump-flows` returns the whole flow TABLE
every `poll_interval_seconds`, so a table entry that lives D seconds is
submitted repeatedly, each time carrying CUMULATIVE counters. That is a
deterministic transformation and it can be applied to real CICIDS2017 flows.

This is not mock data. Every byte, packet, port, address and timestamp comes
from the real CSV; the transformation reproduces a documented behaviour of the
real capture path -- the same category as pinning `fwd_packet_ratio` to 1.0 for
the degradation test. Fabricating traffic would be inventing the input; this
replays a real input the way the real pipeline presents it.

    baseline     the sample as-is, full feature set          (reference)
    degraded     features the live path cannot supply        (§5 parity table)
    recounted    each flow resubmitted as the poll would     (§5 open issue)
    live         both together                               (what you'd ship)

FOUR CORRECTIONS from the review of the first draft, all of which made the
damage look smaller than it is:

  1. NO TOTAL POLL CAP. The first version capped at 12 polls because a 60 s
     window cannot hold more than 12. But a 120 s flow spans two windows and
     appears in ~24 polls; the per-window limit already follows from the
     timestamps, so capping the total silently dropped the second window's
     resubmissions. Only a far-away safety cap remains, and the script reports
     whether anything hit it.

  2. POLL-GRID TIMESTAMPS. monitor.py stamps every flow in one poll with that
     poll's single observed_at. The first version used each flow's own start
     plus k x POLL, preserving sub-second offsets the live path wipes out --
     and those offsets are exactly what re-counting damages (dt_since_pair,
     dt_since_src, the node inter-flow timing features, window_position). Each
     flow's first poll is now rounded UP to the grid and steps by POLL, so
     flows seen in the same poll share one timestamp, as they really would.

  3. PER-ORIGINAL-FLOW METRICS. Duplication changes the population being
     scored: a 60 s flow is scored 12 times and a 1 s flow once, so a
     per-submission F1 mixes real damage with extra weight on long flows --
     and flow length varies by class. Both are now reported: per submission
     AND per original flow (probabilities pooled by mean across that flow's
     submissions). The mapping back to original flows is exact, and the script
     ABORTS rather than guess if a window was subsampled.

  4. IDLE TIMEOUT. OVS keeps reporting an entry until its idle timeout expires,
     with frozen counters, so real re-counting is heavier than ceil(D / POLL).
     IDLE_TIMEOUT defaults to 0 -- the OPTIMISTIC estimate. Set it from
     ovs_dump_flows.txt once that exists; do not guess a value.

THREE FURTHER CORRECTIONS from the second review:

  5. COMMON-FLOW DELTAS. The four variants do not score the same flows. A
     window below `min_edges_per_graph` is not scored at all; re-counting makes
     windows denser, so `recounted` and `live` score flows `baseline` skips.
     `_window_bounds` also anchors its windows to the input's FIRST timestamp,
     and re-counting moves that timestamp onto the poll grid, so the window
     boundaries shift between variants too. Pooling fixed the duplicate
     weighting but not this: a delta could move on coverage alone. The headline
     table is now computed on the flows scored by ALL FOUR variants, and each
     variant's coverage is reported beside it. The all-flows table is kept as a
     secondary view.

     The residual, stated rather than hidden: a common flow may sit in a
     differently-composed window under re-counting. That is not an artefact --
     grouping by poll instead of by flow start is what the live path really
     does -- so it belongs inside the measurement, not outside it.

  6. IDLE-PERIOD FIDELITY. OVS reports `duration=` as time since the entry was
     INSTALLED, and it keeps growing while an idle entry lingers with frozen
     counters. `Flow Bytes/s` and `Flow Packets/s` are recomputed by the live
     path from the cumulative counters (see `capture.py::_finalise`), so they
     DECAY through the idle period. The first version froze duration at the
     flow's end and carried the CSV's rates through unchanged. Both are fixed.
     At IDLE_TIMEOUT=0 this changes nothing; the moment a real idle timeout is
     set from ovs_dump_flows.txt, the old code would have quietly understated
     the damage.

     The decaying divide is `flow_mapping.py::map_flow`, which divides OVS's
     cumulative `byte_count` by OVS's `duration_sec`. NOT `capture.py::
     _finalise` -- that is the scapy path, and its `dur` is last-minus-first
     packet, the length of the traffic, which does not grow while an entry
     lingers. An earlier draft cited it and was wrong about which code decays.

  8. FIRST POLL STRICTLY AFTER THE START. `ceil(t0 / POLL) * POLL` puts the
     first poll AT t0 whenever t0 is a multiple of the poll interval, emitting
     a near-empty submission for an entry that did not exist yet. CICIDS2017
     timestamps are truncated -- `t` is datetime64[s], and three of
     `preprocess._TS_FORMATS` have no seconds field at all -- so t0 is a FLOOR
     of the true start and a poll exactly on it almost always preceded the
     flow. At second resolution this hit 20% of flows; on a minute-resolution
     slice it hits 100%, adding one spurious submission per flow and making
     `recounted` and `live` look worse for a reason that has nothing to do
     with polling. `floor(t0 / POLL) * POLL + POLL` removes every one of them
     and is bit-identical for flows that do not start on the grid. The run
     reports the timestamp resolution of the slice so a reader can see which
     case it was in.

  7. WHAT A ZERO IDLE TIMEOUT HIDES. With IDLE_TIMEOUT=0 a flow shorter than
     the gap to the next poll is still counted once here, because it must be
     scored to appear at all. A genuinely zero-idle entry would never be seen
     by any poll. The practical consequence: most PortScan flows are
     sub-second, so PortScan gets NO duplication at all by construction. A
     small PortScan delta in the `recounted` column is therefore not evidence
     that PortScan survives re-counting -- it is evidence that this
     configuration did not re-count PortScan. Read it only after IDLE_TIMEOUT
     has been set from real data.

Run from the repo root:
    python ML/phase2b_live_path_cost.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "ML" / "graphsentinel_v2"))

SAMPLE = REPO / "ML" / "testdata" / "cicids2017_sample.csv"
MODEL_DIR = REPO / "ML"

POLL_SECONDS = 5        # backend/.env POLL_INTERVAL_SECONDS
IDLE_TIMEOUT = 0        # see correction 4. 0 = optimistic. Set from real data.
MAX_POLLS_SAFETY = 720  # 1 hour at 5 s. A safety valve, NOT the window limit.

# Live-path parity, from INTEGRATION.md §5. Indices are resolved from the
# card's own ordering below rather than hardcoded.
PINNED_ONE = ["fwd_packet_ratio", "byte_asymmetry"]
ZEROED = ["log_max_fwd_len", "log_max_bwd_len", "syn_ratio", "rst_ratio",
          "ack_ratio", "psh_ratio", "log_iat_mean", "iat_burstiness"]

BAR = "=" * 78

if not SAMPLE.exists():
    raise SystemExit(
        f"missing {SAMPLE}\n"
        "This script needs the real CICIDS2017 slice and will not substitute\n"
        "anything for it. Spec: TrafficLabelling_ variant (85 cols, Flow ID\n"
        "first), contiguous rows in timestamp order, headers verbatim."
    )

# ------------------------------------------------- the sensitivity gate ----
# INTEGRATION.md makes this a rule: the sensitivity control gates the
# measurement, and a 2b result obtained without it says nothing. A rule written
# only in prose rots -- this is the same argument as the provenance gate at
# _score_v2, so it is enforced the same way, in code, failing closed.
#
# Run 1 is why. On a density-selected sample every delta was +0.0000 AND
# zeroing all twenty edge features changed 0 of 15,833 predictions: the sample
# could not have shown damage of any size. Without this gate that zero reads as
# "the live path is free".
FORCE = "--force-uninformative" in sys.argv
SENS = REPO / "ML" / "phase2b_sensitivity.json"
_sample_sha = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
_gate = "passed"

def _gate_fail(msg: str) -> None:
    global _gate
    if not FORCE:
        raise SystemExit(
            f"SENSITIVITY GATE: {msg}\n\n"
            f"  Run  python ML/phase2b_sensitivity_check.py  first.\n"
            f"  If its all_zero_edge_features.argmax_changed is 0, this sample\n"
            f"  cannot measure edge-feature damage and 2b's output is\n"
            f"  uninformative whatever it says -- build a sample with attack and\n"
            f"  benign traffic in the same windows instead.\n\n"
            f"  To record an uninformative run deliberately, as run 1 was, pass\n"
            f"  --force-uninformative. The results file is then stamped as such.")
    _gate = f"OVERRIDDEN ({msg})"
    print(f"\n  !! SENSITIVITY GATE OVERRIDDEN: {msg}")
    print( "  !! Every number below is UNINFORMATIVE about the live path.\n")

# A results file for a DIFFERENT sample is a separate run's record. Refuse
# rather than warn: a warning printed immediately before `out.write_text`, at
# the end of a run, cannot be acted on -- and it would fire on exactly the file
# it is meant to protect, since run 1's record predates the sample_sha256 stamp
# and would be replaced anyway. Same rule as the gate itself: fail closed.
OVERWRITE = "--overwrite" in sys.argv
_out = REPO / "ML" / "phase2b_results.json"
if _out.exists() and not OVERWRITE:
    try:
        _prev = json.loads(_out.read_text(encoding="utf-8")).get("sample_sha256")
    except Exception:
        _prev = None
    if _prev != _sample_sha:
        _why = _prev or ("sha not recorded -- predates the stamp, so this is "
                         "most likely run 1")
        raise SystemExit(
            f"{_out.name} already holds a run on a DIFFERENT sample "
            f"({_why}).\n\n"
            f"  Running now would replace that record. Keep it first:\n"
            f"    git mv ML/phase2b_results.json ML/phase2b_sensitivity.json "
            f"ML/phase2b_runs/<name>/\n"
            f"  and update the paths INTEGRATION.md cites.\n\n"
            f"  To replace it deliberately, pass --overwrite.")

if not SENS.exists():
    _gate_fail(f"{SENS.name} does not exist")
else:
    _s = json.loads(SENS.read_text(encoding="utf-8"))
    _si = _s.get("inputs", {}).get("sample", {})
    _changed = _s.get("all_zero_edge_features", {}).get("argmax_changed")
    if _si.get("sha256") != _sample_sha:
        _gate_fail(f"{SENS.name} was run on a different sample "
                   f"({str(_si.get('sha256'))[:12]}... vs {_sample_sha[:12]}...)")
    elif _s.get("inputs", {}).get("weights_sha256") != hashlib.sha256(
            (MODEL_DIR / "weights.pt").read_bytes()).hexdigest():
        _gate_fail(f"{SENS.name} was run against different weights")
    elif _s.get("inputs", {}).get("model_card_sha256") != hashlib.sha256(
            (MODEL_DIR / "model_card.json").read_bytes()).hexdigest():
        # The card's config shapes the graphs the control ran on -- window
        # length, the 8-flow floor, the taxonomy. Same weights with an edited
        # card would let a stale control through.
        _gate_fail(f"{SENS.name} was run against a different model card")
    elif not _changed:
        _gate_fail(f"the control reports argmax_changed = {_changed}: zeroing "
                   f"ALL edge features changes no prediction on this sample")
    else:
        # `argmax_changed` is counted over REAL EDGES -- the flows in windows
        # that were actually scored -- not over rows surviving preprocessing.
        # They are equal only when every window clears min_edges_per_graph, as
        # on run 1's sample. On a mixed-window sample some windows fall below
        # the floor, rows exceed edges, and dividing by rows would understate
        # the sample's sensitivity.
        _n_edges = _s.get("real_edges") or 0
        _share = (_changed / _n_edges) if _n_edges else float("nan")
        print(f"  sensitivity gate: passed -- {_changed:,} of {_n_edges:,} "
              f"predictions ({_share:.2%}) move when all edge features are "
              f"zeroed.")
        print(f"  That share is this sample's RESOLUTION: 2b cannot show damage "
              f"finer than it.")
        print(f"  The gate sets no minimum. Any bar would be a judgement, not a "
              f"fitted number --")
        print(f"  the same reason no 'degraded after N failures' threshold was "
              f"hard-coded. Read it.")
        _gate = f"passed ({_changed} of {_n_edges} predictions move)"

from graphsentinel.config import CLASS_NAMES, CLASS_TO_IDX, Config  # noqa: E402
from graphsentinel.data import preprocess as pre  # noqa: E402
from graphsentinel.data.graph_builder import (  # noqa: E402
    EDGE_FEATURE_NAMES, GraphBuilder, HostHistory,
)
from graphsentinel.models.net import build_model  # noqa: E402
from graphsentinel.evaluate import multiclass_metrics  # noqa: E402

# ------------------------------------------------------------------ model ---
card = json.loads((MODEL_DIR / "model_card.json").read_text(encoding="utf-8"))
cfg = Config.from_dict(card["config"])
cfg.base_dir = str(MODEL_DIR)
assert list(CLASS_NAMES) == list(card["outputs"]["classes"]), "class list drift"
assert list(EDGE_FEATURE_NAMES) == list(card["inputs"]["edge_features"]["names"])

model = build_model(cfg)
_state = torch.load(MODEL_DIR / "weights.pt", map_location="cpu", weights_only=False)
model.load_state_dict(_state["model"] if "model" in _state else _state)
model.eval()

PIN_IDX = [EDGE_FEATURE_NAMES.index(n) for n in PINNED_ONE]
ZERO_IDX = [EDGE_FEATURE_NAMES.index(n) for n in ZEROED]
print(f"model loaded | classes {CLASS_NAMES}")
print(f"poll {POLL_SECONDS}s | idle_timeout {IDLE_TIMEOUT}s "
      f"({'OPTIMISTIC -- real re-counting is heavier' if not IDLE_TIMEOUT else 'from measurement'})")
print(f"live path pins {PINNED_ONE} -> 1.0, zeroes {len(ZEROED)} others")

# ------------------------------------------------------------------- data ---
raw = pd.read_csv(SAMPLE, low_memory=False, encoding="latin-1", on_bad_lines="skip")
raw.columns = [str(c).strip() for c in raw.columns]
raw["Label"] = raw["Label"].astype(str).str.strip().map(pre.RAW_LABEL_MAP)
raw = raw[raw["Label"].notna()].copy()
raw["Timestamp"] = pre._parse_timestamps(raw["Timestamp"])
raw = raw[raw["Timestamp"].notna()].sort_values("Timestamp", kind="mergesort")
raw["t"] = raw["Timestamp"].to_numpy(dtype="datetime64[s]").astype("int64")
raw = pre.clean(raw, cfg, verbose=False)
raw["y"] = raw["Label"].map(CLASS_TO_IDX).astype("int64")
raw = pre.clip_outliers(raw, cfg, cfg.data.edge_feature_cols + cfg.data.volumetric_cols)
raw = raw.reset_index(drop=True)
raw["flow_uid"] = np.arange(len(raw), dtype=np.int64)

N_TOTAL = len(raw)
PRESENT = sorted(raw["y"].unique().tolist())
print(f"\nsample: {N_TOTAL:,} rows over "
      f"{(raw['t'].max()-raw['t'].min())/60:.1f} min")
for k in range(len(CLASS_NAMES)):
    n = int((raw["y"] == k).sum())
    print(f"  {CLASS_NAMES[k]:<18s}{n:>8,}" + ("" if n else "   (absent -- will report n/a)"))

_dur = np.maximum(pd.to_numeric(raw["Flow Duration"], errors="coerce").fillna(0)
                  .to_numpy() / 1e6, 1e-3)
print(f"  flow duration: median {np.median(_dur):.1f}s  p95 {np.percentile(_dur,95):.1f}s  "
      f"max {_dur.max():.1f}s")
_sub_poll = float((_dur < POLL_SECONDS).mean())
print(f"  {_sub_poll:.1%} of flows are shorter than one {POLL_SECONDS}s poll "
      f"-- see correction 7")

# Timestamp resolution. `t` is a FLOOR of the true start, so a poll landing
# exactly on it preceded the flow -- correction 8. How often that would have
# happened depends on how coarsely the slice is stamped.
_tv = raw["t"].to_numpy()
_on_minute = float((_tv % 60 == 0).mean())
_on_grid = float((_tv % POLL_SECONDS == 0).mean())
print(f"  timestamp resolution: {_on_minute:.1%} of starts fall on a whole "
      f"minute, {_on_grid:.1%} on the {POLL_SECONDS}s poll grid")
if _on_minute > 0.99:
    print("    -> this slice is stamped to the MINUTE. Sub-minute ordering "
          "inside it is file order,")
    print("       not real time, and every start would have collided with a "
          "poll under the old rule.")


def recount_like_the_poll(df: pd.DataFrame) -> pd.DataFrame:
    """Resubmit every flow the way `ovs-ofctl dump-flows` would.

    An entry is visible for (duration + IDLE_TIMEOUT) seconds and appears in
    every poll during that span, carrying counters accumulated SO FAR -- not a
    delta. After the flow itself ends, counters FREEZE while the entry lingers
    for the idle timeout, but `duration=` KEEPS GROWING -- OVS reports time
    since the entry was installed, not the length of the traffic. The live
    path recomputes `Flow Bytes/s` and `Flow Packets/s` from the cumulative
    counters over that duration (`flow_mapping.py::map_flow` divides OVS's
    cumulative `byte_count` by OVS's `duration_sec`), so both rates DECAY
    through the idle period. All three behaviours are reproduced here.

    The rates are scaled from the CSV's own values rather than recomputed from
    the byte and packet columns. Algebraically the two are the same thing --
    rate_k = total * frac / reported_dur = csv_rate * elapsed / reported_dur --
    but scaling keeps the identity exact at IDLE_TIMEOUT=0, so re-counting is
    the only thing that moves between `baseline` and `recounted`, rather than
    CICFlowMeter's own rounding of the rate columns.

    Timestamps land on the poll grid: all flows seen in the same poll share
    that poll's observed_at, which is what monitor.py does. Counters accumulate
    linearly over the flow's lifetime -- the neutral assumption; a bursty flow
    would re-count harder at the start.

    The first poll is the first grid point STRICTLY AFTER the start, because
    CICIDS2017 timestamps are truncated and a poll landing exactly on t0
    preceded the flow (correction 8).

    One consequence worth knowing rather than discovering: with IDLE_TIMEOUT=0
    the entry vanishes the instant the flow ends, so the LAST poll usually
    lands before the final counters are reached. A 30 s flow starting at t=3 is
    polled at 5,10,...,30 and reports 27 s of traffic, never 30. That is a real
    property of polling, not an artefact -- and another reason the
    IDLE_TIMEOUT=0 case is the optimistic one.
    """
    t0 = df["t"].to_numpy(dtype=np.float64)
    dur = np.maximum(pd.to_numeric(df["Flow Duration"], errors="coerce")
                     .fillna(0).to_numpy() / 1e6, 1e-3)
    visible = dur + IDLE_TIMEOUT

    # First poll STRICTLY AFTER the start, not at-or-after (correction 8).
    # `t` is a floor of the true start -- datetime64[s] at best, and three of
    # preprocess._TS_FORMATS carry no seconds field at all -- so a poll landing
    # exactly on t0 came before the flow existed.
    first = np.floor(t0 / POLL_SECONDS) * POLL_SECONDS + POLL_SECONDS
    n_polls = np.clip(
        np.floor((t0 + visible - first) / POLL_SECONDS).astype(int) + 1,
        1, MAX_POLLS_SAFETY)
    hit_cap = int((n_polls >= MAX_POLLS_SAFETY).sum())

    counter_cols = [c for c in ("Total Fwd Packets", "Total Backward Packets",
                                "Total Length of Fwd Packets",
                                "Total Length of Bwd Packets")
                    if c in df.columns]
    base = {c: pd.to_numeric(df[c], errors="coerce").fillna(0).to_numpy()
            for c in counter_cols}
    rate_cols = [c for c in ("Flow Bytes/s", "Flow Packets/s") if c in df.columns]
    rate = {c: pd.to_numeric(df[c], errors="coerce").fillna(0).to_numpy()
            for c in rate_cols}

    out = []
    for k in range(int(n_polls.max())):
        sel = n_polls > k
        if not sel.any():
            continue
        part = df[sel].copy()
        obs = first[sel] + k * POLL_SECONDS            # the poll's own clock
        # OVS `duration=` -- time since install, clamped to the entry's own
        # lifetime so the forced single submission of a sub-poll flow (see
        # correction 7) reports that flow's real final state instead of an
        # idle period it never had.
        since_install = np.clip(obs - t0[sel], 1e-3, visible[sel])
        elapsed = np.minimum(since_install, dur[sel])    # traffic seen so far
        frac = np.clip(elapsed / dur[sel], 0.0, 1.0)
        for c in counter_cols:
            part[c] = base[c][sel] * frac              # frozen once elapsed==dur
        for c in rate_cols:
            # cumulative counters divided by a still-growing duration
            part[c] = rate[c][sel] * (elapsed / since_install)
        part["t"] = obs.astype(np.int64)
        part["Flow Duration"] = since_install * 1e6
        out.append(part)

    dup = (pd.concat(out, ignore_index=True)
           .sort_values("t", kind="mergesort").reset_index(drop=True))
    polls_per_window = POLL_SECONDS and int(cfg.graph.window_seconds / POLL_SECONDS)
    print(f"  re-counting: {len(df):,} flows -> {len(dup):,} submissions "
          f"({len(dup)/max(len(df),1):.1f}x); polls/flow median "
          f"{int(np.median(n_polls))}, max {int(n_polls.max())} "
          f"(a {cfg.graph.window_seconds}s window holds {polls_per_window})")
    print(f"  {float((n_polls == 1).mean()):.1%} of flows are submitted exactly "
          f"once -- they are NOT re-counted at this idle timeout")
    if hit_cap:
        print(f"  !! {hit_cap} flow(s) hit MAX_POLLS_SAFETY={MAX_POLLS_SAFETY}; "
              f"their re-counting is UNDER-estimated")
    return dup


def score(df: pd.DataFrame, degrade: bool, tag: str):
    """Score every window, and map each scored edge back to its ORIGINAL flow.

    The mapping replicates the builder's own ordering: build() sorts by t with
    a stable mergesort, resets the index, and slices contiguous [lo, hi) window
    bounds out of that order. Reproducing the same sort and calling the same
    _window_bounds gives the exact row for every real edge. If a window was
    subsampled (n_edges > max_edges_per_graph) the correspondence breaks, and
    this ABORTS rather than report a silently wrong mapping.

    Returns the pooled per-flow probabilities as well as the metrics, because
    the variants do not cover the same flows and the honest comparison is made
    on the intersection (correction 5).
    """
    builder = GraphBuilder(cfg, history=HostHistory(capacity=cfg.model.memory_capacity))
    graphs = builder.build(df.copy(), update_history=True, verbose=False)
    if not graphs:
        print(f"  {tag:<10s} NO GRAPHS -- every window below min_edges_per_graph")
        return None

    ordered = df.sort_values("t", kind="mergesort").reset_index(drop=True)
    uid_all = ordered["flow_uid"].to_numpy()
    bounds = {(round(s, 3), round(e, 3)): (lo, hi)
              for lo, hi, s, e in builder._window_bounds(
                  ordered["t"].to_numpy(dtype=np.float64))}

    model.reset_memory()
    ys, ps, uids = [], [], []
    with torch.no_grad():
        for g in graphs:
            key = (round(float(g.window_start), 3), round(float(g.window_end), 3))
            if key not in bounds:
                raise SystemExit(f"{tag}: window {key} not found in bounds -- "
                                 "the mapping assumption is wrong, refusing to guess")
            lo, hi = bounds[key]
            m = getattr(g, "real_edge_mask", None)
            n_real = int(m.sum()) if m is not None else int(g.edge_index.size(1))
            if n_real != hi - lo:
                raise SystemExit(
                    f"{tag}: window {key} has {n_real} real edges but the slice "
                    f"holds {hi - lo}. The window was subsampled "
                    f"(max_edges_per_graph={cfg.graph.max_edges_per_graph}), so "
                    f"edges can no longer be mapped to flows. Reduce the slice "
                    f"or raise the cap; do not trust a guessed mapping.")

            if degrade:
                g.edge_attr = g.edge_attr.clone()
                g.edge_attr[:, PIN_IDX] = 1.0
                g.edge_attr[:, ZERO_IDX] = 0.0
            out = model.predict(g, now=int(g.window_end))
            p, ey = out["edge_probs"], g.edge_y
            if m is not None:
                p, ey = p[m], ey[m]
            if not len(ey):
                continue
            ps.append(p.numpy())
            ys.append(ey.numpy())
            uids.append(uid_all[lo:hi])

    if not ps:
        return None
    y, p, u = np.concatenate(ys), np.vstack(ps), np.concatenate(uids)

    per_sub = multiclass_metrics(y, p.argmax(1), p, "edge_")

    # Pool each original flow's submissions by MEAN probability, the standard
    # way to combine repeated observations of one object.
    order = np.argsort(u, kind="stable")
    u_s, p_s, y_s = u[order], p[order], y[order]
    uniq, starts = np.unique(u_s, return_index=True)
    sums = np.add.reduceat(p_s, starts, axis=0)
    counts = np.diff(np.append(starts, len(u_s))).reshape(-1, 1)
    pooled = sums / counts
    y_flow = y_s[starts]
    per_flow = multiclass_metrics(y_flow, pooled.argmax(1), pooled, "edge_")

    print(f"  {tag:<10s} {len(graphs):>4} windows | {len(y):>8,} submissions "
          f"-> {len(uniq):>8,} original flows "
          f"({len(y)/max(len(uniq),1):.1f}x, coverage {len(uniq)/max(N_TOTAL,1):.1%})")
    return {"per_submission": per_sub, "per_flow": per_flow,
            "n_submissions": int(len(y)), "n_flows": int(len(uniq)),
            "n_windows": len(graphs), "coverage": len(uniq) / max(N_TOTAL, 1),
            "_uids": uniq, "_probs": pooled, "_y": y_flow}


print(f"\n{BAR}\n  SCORING\n{BAR}")
recounted = recount_like_the_poll(raw)
RESULTS = {
    "baseline":  score(raw, False, "baseline"),
    "degraded":  score(raw, True, "degraded"),
    "recounted": score(recounted, False, "recounted"),
    "live":      score(recounted, True, "live"),
}

# ------------------------------------------------------- common-flow view ---
# Correction 5: the variants do not score the same flows, so a raw delta mixes
# real damage with a change in which flows got scored at all. Restrict to the
# flows every variant scored.
COMMON = None
if all(RESULTS.values()):
    COMMON = RESULTS["baseline"]["_uids"]
    for r in RESULTS.values():
        COMMON = np.intersect1d(COMMON, r["_uids"], assume_unique=True)
    for name, r in RESULTS.items():
        sel = np.isin(r["_uids"], COMMON, assume_unique=True)
        yc, pc = r["_y"][sel], r["_probs"][sel]
        if name == "baseline":
            Y_COMMON = yc
        elif not np.array_equal(yc, Y_COMMON):
            raise SystemExit(
                f"{name}: labels disagree with baseline on the common flows. "
                "The flow_uid mapping is wrong somewhere; refusing to report.")
        r["per_flow_common"] = multiclass_metrics(yc, pc.argmax(1), pc, "edge_")
        r["n_common"] = int(sel.sum())
    PRESENT_COMMON = sorted(np.unique(Y_COMMON).tolist())
else:
    PRESENT_COMMON = PRESENT


def show(view: str, title: str, present, note: str = ""):
    print(f"\n{BAR}\n  {title}\n{BAR}")
    if note:
        print(f"  {note}")
    print("  " + f"{'variant':<12s}"
          + "".join(f"{c[:10]:>12s}" for c in CLASS_NAMES)
          + f"{'MACRO':>9s}{'vs base':>9s}")
    b = (RESULTS["baseline"] or {}).get(view, {}).get("edge_macro_f1", float("nan"))
    for name, r in RESULTS.items():
        if not r or view not in r:
            print(f"  {name:<12s}  (no result)")
            continue
        m = r[view]
        row = "  " + f"{name:<12s}"
        for k, c in enumerate(CLASS_NAMES):
            # A class with no rows in this slice has no F1. Printing 0.0000
            # would look measured; it is not.
            row += f"{'n/a':>12s}" if k not in present else \
                   f"{m.get(f'edge_f1_{c}', float('nan')):>12.4f}"
        mf = m.get("edge_macro_f1", float("nan"))
        row += f"{mf:>9.4f}{mf - b:>+9.4f}"
        print(row)
    return b


print(f"\n{BAR}\n  COVERAGE -- which flows each variant actually scored\n{BAR}")
print(f"  sample holds {N_TOTAL:,} flows. A window below "
      f"min_edges_per_graph={cfg.graph.min_edges_per_graph} is not scored at all,")
print(f"  and re-counting both densifies windows and shifts their boundaries.")
print("  " + f"{'variant':<12s}{'scored':>12s}{'coverage':>11s}{'in common':>12s}")
for name, r in RESULTS.items():
    if not r:
        print(f"  {name:<12s}  (no result)")
        continue
    print(f"  {name:<12s}{r['n_flows']:>12,}{r['coverage']:>10.1%}"
          f"{r.get('n_common', 0):>12,}")
if COMMON is not None:
    print(f"\n  {len(COMMON):,} flows scored by all four variants "
          f"({len(COMMON)/max(N_TOTAL,1):.1%} of the sample). The headline table")
    print("  below uses only those, so coverage cannot move the delta.")
else:
    print("\n  !! a variant produced no result -- no common-flow comparison "
          "is possible")

if COMMON is not None:
    b_common = show(
        "per_flow_common",
        "EDGE F1 -- COMMON FLOWS ONLY (the headline)", PRESENT_COMMON,
        note="Only flows every variant scored. This is the number to quote.")
b_flow = show("per_flow", "EDGE F1 -- ALL FLOWS EACH VARIANT SCORED", PRESENT,
              note="Secondary: differing coverage contributes to these deltas.")
b_sub = show("per_submission", "EDGE F1 -- PER SUBMISSION (what the model sees)",
             PRESENT,
             note="Diagnostic only: over-weights long flows, and flow length "
                  "varies by class.")

print(f"\n{BAR}\n  WHAT THIS MEANS\n{BAR}")
print("  NOT comparable to test_report.json: that covers the full episode-split")
print("  test set (227,325 edges); this is a small contiguous slice, a different")
print("  population. The DELTAS are the output.\n")
print("  Read the COMMON FLOWS table. The all-flows table lets coverage move the")
print("  delta; the per-submission table over-weights long flows.\n")
if PRESENT != list(range(len(CLASS_NAMES))):
    absent = [CLASS_NAMES[k] for k in range(len(CLASS_NAMES)) if k not in PRESENT]
    print(f"  Classes absent from this slice (n/a above, EXCLUDED from macro):")
    print(f"    {', '.join(absent)}\n")

HEADLINE = "per_flow_common" if COMMON is not None else "per_flow"


def d(name, view=HEADLINE):
    r = RESULTS.get(name)
    b = (RESULTS["baseline"] or {}).get(view, {}).get("edge_macro_f1", float("nan"))
    return (r[view].get("edge_macro_f1", float("nan")) - b) if r else float("nan")


for k, what in (("degraded", "features the live path cannot supply"),
                ("recounted", f"the {POLL_SECONDS}s poll resubmitting each flow"),
                ("live", "both together -- what you would actually ship")):
    print(f"  {k:<10s} {d(k):>+8.4f}   {what}")

live = d("live")
print()
print("  The bands below are MY judgment calls, not measured cut-offs:")
if live != live:
    print("  Incomplete -- a variant produced no graphs. A slice too sparse for")
    print(f"  {cfg.graph.window_seconds}s windows measures nothing.")
elif live > -0.05:
    print("  Small cost. Record it in INTEGRATION.md and continue -- with the")
    print("  caveat that this is one contiguous slice, not the full test set.")
elif live > -0.20:
    print("  A real cost. Ship only with this number beside every metric, and")
    print("  treat fixing the ingestion as the next priority.")
else:
    print("  COLLAPSE. Do not ship this as a detector. Fix the ingestion:")
    print("    * add a timestamp and directional counters to FlowRecord, and")
    print("    * de-duplicate per window on the OVS match/cookie, or take")
    print("      per-poll counter deltas instead of cumulative totals.")

if RESULTS.get("recounted") and RESULTS.get("degraded"):
    r, g = d("recounted"), d("degraded")
    print()
    print(f"  Re-counting {r:+.4f} vs missing features {g:+.4f} -> fix "
          f"{'poll de-duplication' if r < g else 'the ingestion fields'} first.")
if not IDLE_TIMEOUT:
    print()
    print(f"  IDLE_TIMEOUT is 0, so every re-counting number above is the")
    print(f"  OPTIMISTIC case. Real entries linger past the flow with frozen")
    print(f"  counters and a growing duration. Set IDLE_TIMEOUT from")
    print(f"  ovs_dump_flows.txt and re-run.")
    print(f"  In particular a sub-poll flow is submitted once here, so short-lived")
    print(f"  classes -- PortScan above all -- are not re-counted AT ALL in this")
    print(f"  run. Do not read their small delta as resilience (correction 7).")

out = _out          # checked for a foreign record before scoring started
out.write_text(json.dumps({
    "note": ("small contiguous slice; deltas are the result, not the absolutes. "
             "per_flow_common is the honest view -- it holds the scored "
             "population fixed across variants. per_flow lets coverage move "
             "the delta; per_submission over-weights long flows."),
    "headline_view": HEADLINE,
    "sensitivity_gate": _gate,
    "sample_sha256": _sample_sha,
    "poll_seconds": POLL_SECONDS, "idle_timeout": IDLE_TIMEOUT,
    "idle_timeout_is_optimistic": not IDLE_TIMEOUT,
    "n_flows_in_sample": N_TOTAL,
    "n_flows_common_to_all_variants": int(len(COMMON)) if COMMON is not None else None,
    "classes_present": [CLASS_NAMES[k] for k in PRESENT],
    "classes_present_common": [CLASS_NAMES[k] for k in PRESENT_COMMON],
    "pinned_to_one": PINNED_ONE, "zeroed": ZEROED,
    "results": {k: {kk: vv for kk, vv in (v or {}).items()
                    if not kk.startswith("_")} or None
                for k, v in RESULTS.items()},
}, indent=2, default=float), encoding="utf-8")
print(f"\n  saved -> {out}")

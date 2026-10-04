# GraphSentinel v2 — backend integration

What is wired in, where each number came from, and what this system must not
claim. Written for engineers working on this repo.

**Measured numbers about the model live in `MODEL_BEHAVIOUR.md`**, which is their
single source; the timestamp investigation and its counts live in
`ML/TIMESTAMP_FIX.md`. This document owns the mechanics: contracts, wiring, what
calls what. Where it needs a measurement it points there. A test
(`tests/test_figures_guard.py`) fails if a key figure is restated here. Anything
not traceable is marked `TODO: unverified` rather than given a plausible value.

---

## 1. Artefacts

The model retrained under the fixed timestamp parse, installed 2026-10-04.
Digests are from `ML/MANIFEST.json` and `ML/PROVENANCE.json`, and were verified
against the files on disk at install (`tests/test_artifacts.py` re-checks them).

| File | Bytes | sha256 | In git? |
|---|---:|---|---|
| `ML/model_card.json` | 10,355 | `734943afb43e45c636d50ff8c14cd0c81ce8b2875c1418aa754d09116d8db7b9` | ✅ tracked |
| `ML/test_report.json` | 70,261 | `08acb2e4bf72a33ed77e827a0471f7723cc85a17f162267a9c98f42e2e3e4aab` | ✅ tracked |
| `ML/MANIFEST.json` | 2,548 | — | ✅ tracked |
| `ML/PROVENANCE.json` | — | — | ✅ tracked: session, bundle commit, environment, every artefact's digest |
| `ML/weights.pt` | 76,178,357 | `3db34022bcbab0501ceec50f4050319d997fd5abbb66430f4a75508e65054709` | ❌ **gitignored** |
| `ML/model.ts` | 76,272,252 | `6ff399088b24f81a582a6b187d41e66053de4dbe5e4374ef28959fe8e1737a5c` | ❌ **gitignored** |

The epoch-31 model's files are in `ML/prefix_epoch31/` (its binaries locally
only, gitignored), and its Phase 2b run in `ML/phase2b_runs/`.

### Why the weights are not in git

`weights.pt` and `model.ts` are 72.7 MiB each. Git cannot delta-compress them,
so every re-export would add ~145 MiB to history **permanently**, removable only
by rewriting history. For scale, the largest blob otherwise tracked in this repo
is 596 KB. Both files are under GitHub's 100 MB hard block, so a plain commit
*would* push — that is the trap.

This repo has never used Git LFS. `.gitattributes` sets only `eol=lf` for
`*.sh`; there are no `filter=lfs` rules and `git lfs ls-files` is empty.
**`git lfs pull` will not work here** — if you were sent that way by an old
message, that path is a dead end (`backend/check_env.py` has been corrected).

### How to get the weights

Ask a teammate for `weights.pt` and place it at `ML/weights.pt`. Then verify:

```bash
sha256sum ML/weights.pt
# must print 3db34022bcbab0501ceec50f4050319d997fd5abbb66430f4a75508e65054709
```

`ML/model.ts` is the TorchScript export and is **not on the integration path** —
`InferenceEngine.from_artifacts()` reads `model_card.json` + `weights.pt` only.
You do not need `model.ts` to run the stack.

Without `weights.pt` the inference container stays unhealthy, the backend
reports `ml_v2.client.reachable: false`, and **no scores are produced**. That is
the intended behaviour — see §5.

---

## 2. The contract

`ML/model_card.json`, `contract_version` **`2.0.0`**.

**Class list, in order.** The order *is* the contract: the model emits logits
indexed positionally, so a reordered list silently relabels every prediction.

| index | class |
|---:|---|
| 0 | `BENIGN` |
| 1 | `Volumetric_Flood` |
| 2 | `PortScan` |
| 3 | `BruteForce` |
| 4 | `Botnet` |

16 node features and 20 edge features, also order-sensitive. Neither list is
hardcoded in the backend; both are read from the card at runtime.

### Startup check

`app/services/model_contract.py` refuses to boot on any of:

- `model_card.json` missing, unreadable, or not valid UTF-8/JSON
- `contract_version` != `2.0.0`
- `outputs.classes` missing, empty, duplicated, or without `BENIGN`
- a declared feature `count` that disagrees with the number of names listed
- **class or feature ORDER changed** while `contract_version` stayed `2.0.0`,
  caught by a sha256 fingerprint over the ordered names
  (`EXPECTED_CONTRACT_FINGERPRINT`)

On the fingerprint and the "never hardcode a class list" rule: it is a hash, not
a list. No backend code enumerates class or feature names — every label and
index still comes from the card at runtime. Comparing names as a *set* cannot
catch a reorder; this can. Changing the classes, the features, or either order
is a contract change: bump `EXPECTED_CONTRACT_VERSION` and the fingerprint
together.

---

## 3. Measured performance

**Owned by `MODEL_BEHAVIOUR.md`.** Flow and host classification, the comparison
with the epoch-31 model, and why the numbers moved: §4 and §5 there. Per-class
confusion and the PortScan/BruteForce finding: §5.4. What may and may not be
claimed: §10.

What this document adds is where the numbers come from, mechanically:

- **Headline numbers come from `ML/test_report.json` (TEST).**
  `ML/model_card.json`'s `metrics` block uses identical key names for
  VALIDATION numbers and says so in `metrics_split`.
- **`edge_macro_f1_all_classes` is the key that compares across runs.**
  `edge_macro_f1` averages only the classes present in the test split, and the
  installed model's test split holds no Botnet edges.
- **The model in `ML/` is the one retrained on 2026-10-03** under the fixed
  timestamp parse (best epoch 18, weights sha256 `3db34022…`). The epoch-31 model
  and every file that described it are in `ML/prefix_epoch31/`.
- **The node head is not used.** The backend discards `WindowResult.detections`
  unread; host-level attribution is not a claim this system makes.
- **Split protocol:** `config.data.split_strategy` is `episode`; *"train and test
  can share a burst; these are NOT novel-attack numbers."* The config's
  `holdout_attacks: ['Botnet']` is read only by `_split_attack_holdout`, which
  this strategy never calls. How the split behaves on this dataset:
  `MODEL_BEHAVIOUR.md` §5.

---

## 4. Operating points

### The artefact

| File | Bytes | sha256 |
|---|---:|---|
| `ML/threshold_study.json` | 2,517 | `e068a714598c1dad0e0e4c7a6d9d7d1201b3fa7238637535a4974d12bca2cb8a` |
| `ML/threshold_flow_level.csv` | 511 | `0fc56ff9394b9e673ef84a0cc58925d17c64814bd5df14bfff59814b2156afa2` |
| `ML/threshold_window_level.csv` | 2,976 | `ffc05b5bd16e3575d19f15520123a0378dc3b7344aa9a4a331b5421b899529e6` |

`.gitattributes` marks top-level `ML/*.json` and `ML/*.csv` as `-text`, so these
digests keep matching the checked-out files. Produced by the lifted threshold
cell (`ML/colab/cells/threshold_study.py`) in the retrain session, against the
epoch-18 checkpoint: `fitted_on: "validation split"`, `checkpoint_epoch: 18`.
The epoch-31 study is `ML/prefix_epoch31/threshold_study.json`.

**Fitted on validation, applied to test: in this run those are different
populations.** Validation's attack windows are almost free of benign traffic and
test's are almost all mixed (`MODEL_BEHAVIOUR.md` §5.1). And for PortScan the
split cut falls inside one timestamp (14:55), so that minute is in train,
validation and test alike (`MODEL_BEHAVIOUR.md` §5.3). **The checkpoint and every operating
point in this file were chosen on a split that is almost pure and, for
PortScan, overlaps training.** That is the largest single threat to this
section.

### What the backend reads

`app/services/operating_points.py` reads **exactly three top-level scalars**
(`:42-44`, `:121-123`), and those three names are present in the file.

| Operating point | Value | Key |
|---|---:|---|
| binary attack gate on `1 - P(BENIGN)` | 0.5 | `binary_gate` |
| alert rule: flows over the gate | ≥ 5 | `alert_min_flows` |
| alert rule: window | 60 s | `alert_window_seconds` |

It does **not** read `flow_level` or `per_class_min_conf`. The loader accepts
this file as it stands and reports it `verified`. It is read only when v2 is
enabled, which it currently is nowhere (`config.py` defaults to `false`, and
compose sets `"false"`). Even with v2 enabled, the path creates no incidents:
alerting is not implemented. `alerting_enabled` stays `false` whether or not
the file loads (`V2_ALERTING_IMPLEMENTED = False` in `inference_v2.py`), and
every report carries the reason. `flows_over_gate` is reported for inspection
only.

**Treat `binary_gate: 0.5` as provisional. Do not wire it to anything that
alerts.** The study script appended `{0.5, 0.8, 0.85, 0.9, 0.95, 0.99}` to its
quantile search grid so the report could show the hardcoded defaults beside the
fitted values. It then passed that same grid to `idxmax`, so an appended value
could be returned as the fitted answer, with ties broken to the lowest
threshold. The script's author confirms this is a bug in the script, and the
retrain ran the same cell, so it is still there. Two of this study's four
numbers sit exactly on that list: the binary gate 0.5 and Botnet 0.5
(Volumetric_Flood's 0.4571 and PortScan's 0.8706 are data quantiles). The epoch-31
study had three. The file's own label, `binary_criterion: "max F1 on
validation"`, may therefore overstate how fitted the gate is.
`grid_and_determinism_check.py` (parts A and B, run outside this repo) refits
without the appended values. `TODO: unverified` until it comes back.

**The binary gate's validation precision and recall are not in the file.** The
cell prints them (`ML/retrain_logs/threshold_study_output.txt`: precision
0.9998, recall 0.9947, FPR 0.000054 on validation), but the JSON does not store
them. `0.5` is one of the six fixed values `grid_for` adds to its quantile grid,
not a data quantile. When
several thresholds tie on F1, `idxmax` picks the lowest.

`InferenceEngine`'s default `threat_threshold=0.75` is a **package default, not
a fitted value**, and is not adopted. The engine applies no threshold to
`WindowResult.flows`; the gate is applied in the backend, where its provenance
is recorded.

### Flow level, binary gate 0.5

From `flow_level` in the JSON (identical to `threshold_flow_level.csv`):

| Set | Flows | Attack flows | Precision | Recall | FPR | F1 |
|---|---:|---:|---:|---:|---:|---:|
| test | 226,342 | 51,921 | 0.99211 | 0.99973 | 0.002368 (413 of 174,421) | 0.99590 |
| monday | 500,531 | 0 | n/a | n/a | **0.000120** (60 of 500,531) | n/a |
| thursday | 426,958 | 2,111 | 0.06694 | 0.97300 | **0.06739** (28,629 of 424,847) | 0.12527 |

### Window level, ≥ 5 flows in 60 s

From `threshold_window_level.csv`, `min_flows=5`. **This run only; not
comparable with the epoch-31 table** (see §3).

| Set | Windows | Attack windows | Alerted | TP | FP | FN | Precision | Recall | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| test | 207 | 35 | 32 | 31 | 1 | 4 | 0.9688 | 0.8857 | 0.0058 |
| monday | 486 | 0 | 2 | 0 | 2 | 0 | n/a | n/a | 0.0041 (2 of 486) |
| thursday | 485 | 96 | 84 | 71 | 13 | 25 | 0.8452 | 0.7396 | 0.0334 (13 of 389) |

The test population excludes Botnet entirely (§3), which the model does not
detect: the recall figure says nothing about Botnet.

### Monday and Thursday disagree on the false-alarm rate

Under the same 0.5 gate, flow-level FPR is **0.000120 on Monday and 0.0674 on
Thursday**. At window level, Monday raises **2 false alerts in 486 windows** and
Thursday 13 in 389 non-attack windows. The honest false-alarm range lies between
the two days, and which one a live network resembles is unknown. Some of
Thursday's "false positives" may be real attacks labelled BENIGN; possible, not
established. **Thursday's recall is not evidence of novel-attack detection**:
0.973 at precision 0.067, so 28,629 of its 30,683 flow alarms are false.

### ⚠️ The `shuffled` control is uninformative. Do not cite it

The `shuffled` rows permute `edge_attr` **within each graph**. On pure-class
windows that barely changes any edge, which is why the epoch-31 run's shuffled
rows were identical to test. On this run's mixed windows they differ a little
(flow-level recall 0.9996, window precision 0.72 against 0.97), and still do not
measure dependence on flow features. The instrument for that is the global
shuffle in `ML/probes.json` (`edge_macro_f1` over the four classes present, −0.1565
when features are permuted across windows) and the zeroing ablation (−0.0265).

### Per-class SDN confidence floors: fitted, but not used

Fit rule: fire only when `argmax == class` and `P(class) >= min_conf`.

| Class | Fitted `min_conf` | Val prec | Val rec | Test prec | Test rec | Test F1 |
|---|---:|---:|---:|---:|---:|---:|
| Volumetric_Flood | 0.4571 | 1.0000 | 0.7980 | 0.9804 | 1.0000 | 0.9901 |
| PortScan | 0.8706 | 0.9995 | 0.9937 | **0.0000** | **0.0000** | **0.0000** |
| BruteForce | not fitted | — | — | — | — | — |
| Botnet | 0.5000 | 0.0000 | 0.0000 | 0.0000 | n/a | 0.0000 |

**The backend does not read these, and none is to be adopted.** PortScan is the
composition mismatch in one row: 99.6% of correct validation predictions clear
its floor, 0.0% on test. BruteForce cannot be fitted ("0 predicted, 582 true in
validation": the model labels validation BruteForce as PortScan). Botnet's 0.5 is
the grid floor, not a fit. The epoch-31 study's Volumetric_Flood anomaly (0.0 on
test at 0.80) does not recur: see §6 for what the deployed floors let through.

### Run-to-run variation: present, unmeasured

**Every figure in this section and in §3 carries run-to-run variation of
unmeasured size.** The retrain is one run. The evidence that variation exists
comes from the epoch-31 study (files in `ML/prefix_epoch31/`), where two runs
of the same study disagree:

Cell 33 of `ML/GraphSentinel_Training.ipynb` prints and stores the same object
for each flow-level row (lines 308-315), so within one run the console output
and the stored row cannot differ. Yet the notebook's saved console output and
`threshold_study.json` do differ. Printed rounding still pins down one integer
count for each, so the differences are exact:

| Set, flow level at gate 0.5 | Notebook's saved output | `threshold_study.json` |
|---|---:|---:|
| test, false positives | 13 | 13 |
| monday, false positives | **3** (FPR printed `0.000006`) | **1** (FPR 0.0000020) |
| thursday, false positives | 31,262 (FPR printed `0.073584`) | 31,258 |
| thursday, true positives | 1,880 (recall printed `0.8906`) | 1,879 |
| shuffled, false positives | 10 (FPR printed `0.000057`) | 11 |

These are two different runs, a few edges apart. The author attributes this to
non-deterministic CUDA scatter operations, and reports Botnet F1 moving from
0.0635 to 0.0000 across identical training reruns (`TODO: unverified`: that
record is not in this repo). The same mechanism explains BruteForce's 302 against 301 above, so that
discrepancy is a symptom of variation, not an unexplained anomaly.
`grid_and_determinism_check.py` part C scores the test split twice in one
process to bound it. Until then, quote no figure here more precisely than a few
edges can move it.

### The ≥5-flow rule and the 8-flow floor

These are **not** in conflict. `min_edges_per_graph = 8` is how many flows a
window needs before a graph is built **at all**; ≥5 is how many of those must
clear the gate. A 20-flow window with 6 over the gate alerts correctly. They
interact only below 8 total flows, where nothing is scored — reported as
`unscored`, never as clean. See §5.

---

## 5. Architecture

```
ovs-ofctl dump-flows  →  flow_parser  →  MininetMonitor (5s poll)
                                              │
                    ┌─────────────────────────┴──────────────────────┐
                    ▼                                                ▼
            v1 path (unchanged)                      v2 path (this integration)
        analysis_pipeline.analyze_flows           analysis_pipeline_v2.score_flows
        GraphSAGE, binary, heuristic labels           │  HTTP
        keeps its heuristic fallback                  ▼
                                            graphsentinel-inference container
                                            graphsentinel.inference.service:app
                                            InferenceEngine.from_artifacts()
```

### Why HTTP rather than an in-process import

`InferenceEngine` is **stateful**: a flow buffer, a 60 s window boundary, and a
persistent host-memory module keyed by IP. The backend has two concurrent entry
points — the `MininetMonitor` daemon thread and `/api/v1/analyze` handlers —
which in-process would interleave into one shared window buffer with no
coordination. That is a correctness bug, not a deployment preference.

It also keeps torch out of the backend image and avoids `sys.path` injection of
the kind that already rotted into dead code at
`inference_service._load_model_class()` (see §8).

### One producer: `/api/v1/analyze` is deliberately NOT wired to v2

HTTP gives the engine a single owning process; it does **not**, by itself,
prevent interleaving. If both the monitor and `/api/v1/analyze` POSTed to the
service, they would still land in its one window buffer and its one persistent
host memory. What prevents that is having exactly **one producer** of the live
stream. Only `MininetMonitor` feeds v2. Manual and simulated `/analyze`
submissions would be stamped with the current time and pollute live windows and
host history, so they stay on the v1 path. Scoring ad-hoc batches with v2 would
need a separate, memory-isolated engine instance — not built.

### Open: OVS poll re-counting (unmeasured)

`ovs-ofctl dump-flows` returns the flow **table** on every 5 s poll. A long-lived
table entry is therefore submitted again on every poll — ~12 times per 60 s
window — each time with **cumulative** counters, as if it were a new flow. The
likely effects: inflated `log_out_degree` / `log_in_degree`, byte totals and
`burst_score`; `log_dt_since_pair` pinned near the 5 s poll interval; and a
network with only two real flows clearing the 8-flow `unscored` floor
artificially.

**The damage can be estimated from CICIDS2017 without the OVS capture.** The
mechanism is specified entirely by this backend's own code: an entry alive for
D seconds is re-submitted on every 5 s poll, carrying cumulative counters and
stamped with the poll's observation time. Replaying real CICIDS2017 rows through
that transformation invents no traffic, just as pinning `fwd_packet_ratio` to 1.0
doesn't. `ML/phase2b_live_path_cost.py` does this.

**How it is measured.** The headline delta is computed only on flows scored by
all four variants (baseline, degraded, recounted, live), with each variant's
coverage reported beside it. Re-counting densifies windows and shifts their
boundaries, so the variants don't score the same flows, and a delta over all
flows could move on coverage alone. Each flow's repeated submissions are pooled
into one prediction, so long flows don't count more than short ones.

Limits:

- **It is an estimate that errs optimistic.** It assumes one OVS table entry per
  CICFlowMeter flow, and by default ignores idle timeouts (`IDLE_TIMEOUT=0`).
  Real entries outlive their last packet and keep being reported, so actual
  re-counting is at least as heavy.
- **At `IDLE_TIMEOUT=0`, sub-poll flows are never re-counted.** A flow shorter
  than one 5 s poll is scored, but submitted only once, so the figure contains
  **no re-counting damage for it at all**. Most PortScan flows are sub-second,
  so a small PortScan delta at this setting is not evidence that PortScan
  survives re-counting. Read the per-class figures only once `IDLE_TIMEOUT` has
  been set from real data.
- **Poll alignment depends on timestamp resolution.** CICIDS2017 starts are
  truncated, so the first poll is taken strictly after the recorded start. On
  a minute-stamped slice every start would otherwise have collided with a poll
  boundary. The run reports the resolution of the slice it was given.
- **Choosing the fix still needs the capture.** Per-poll counter deltas keyed on
  the OVS match/cookie, or per-window de-duplication, has to be decided against
  `ML/testdata/ovs_dump_flows.txt`, which shows real entry granularity and real
  `idle_timeout` values.

**The estimate has been run and cannot settle this.** On the delivered sample,
re-counting moved nothing, but neither did removing every edge feature (see
"PHASE 2b run 1 (density-selected sample): uninformative" below). At `IDLE_TIMEOUT=0`,
re-counting turned 15,833 flows into only 37,195 submissions (2.3×,
`phase2b_results.json`), far lighter than a real idle timeout would give. **v2
scores on live OVS traffic are still not interpretable.**

### No fallback in the client, by design

When the inference service is unreachable the backend reports **unavailable and
stops producing scores**. It does **not** fall back to `_heuristic_predict()`.
A hand-tuned formula emitting numbers that look like model output, into the same
incidents table, that then block IPs, is worse than an outage — an operator
cannot tell the two apart from the response. The v1 path keeps its own fallback;
nothing in the v2 client inherits it.

**That guarantee covers the client, and the provenance gate below covers what
is upstream of it.** Until 2026-09-14 the parser had a fallback of its own that
defeated the argument above.

### Fixed: randomised flows could reach v2

**The defect.** `parse_ovs_flows` wrapped the whole daemon call in one `try`
and ended with `return demo_flows() if settings.demo_fallback_flows else []`.
With `DEMO_FALLBACK_FLOWS` on, it returned randomised attack traffic
(`demo_flows()`) whenever a poll produced nothing parseable:

- when the daemon was unreachable, refused, or timed out;
- when the daemon returned an empty response, invalid JSON, or an error status;
- and, **with no log line at all**, when the dump succeeded but held no IP or
  ARP flows. That is a healthy quiet network, or a dump holding only a
  table-miss rule.

The committed Docker configuration turns the flag on (`.env.docker:67`), and
Docker has no Mininet, so every poll in the default stack yielded randomised
flows. Nothing downstream could tell. The poll returned normally, so
`last_error` read `None`. `map_flow` does not carry `data_source` into the
service request. A monitor comment claimed v2 ran "on the SAME real flows".

**The fix, in two parts.**

1. **Provenance gate at the monitor** (commit `2adaec5`). `_score_v2` checks
   every flow's `data_source` before anything is mapped or sent:
   - it is an allowlist: only `"ovs"` passes;
   - an untagged flow takes `FlowRecord`'s default `"manual"` and is refused;
   - a batch containing any non-OVS flow is refused whole.

   Refusal has its own state under `/health → monitor.v2_provenance`, separate
   from `unscored_rate`:
   - `last_poll_state` is one of `submitted`, `refused_non_ovs`,
     `nothing_to_score` or `v2_disabled`;
   - refusal counters and the last source tally.

   Refusal logs a WARNING at onset and at most once a minute after, and one
   INFO line when it ends, naming how long it lasted. The service request
   carries no provenance field.

2. **Demo substitution moved out of the parser** (commit `37a4060`, next
   subsection). Substitution now happens only when a poll **failed**. A
   successful poll that parsed nothing stays empty.

**Still contained.** `GS2_ENABLED` remains `"false"` in `docker-compose.yml`.
The gate would make enabling it safe, but v2 stays off while the operating
points are provisional (§4). v1 still ingests substituted flows and records
incidents from them tagged `data_source="demo"`; that behaviour predates this
integration.

### `unscored` windows

A window below the 8-flow floor returns `unscored: true` with `flows: []`.
**An unscored window is not a clean bill of health.** The backend surfaces it
per window and tracks the rate over the last 200 windows at
`/health → ml_v2.client.unscored_rate`. A meaningful rate there means the
capture is too sparse for a 60 s window, **or** that polls are failing. A full
outage closes no windows at all, so the rate simply stops moving. Read it
together with the poll status below.

### Poll status: failed polls are visible

Until commit `37a4060`, `parse_ovs_flows` swallowed every failure and returned
normally, so a daemon outage looked exactly like quiet traffic
(`last_flow_count = 0`, `last_error = None`).

Now `flow_parser.poll_ovs_flows()` returns a `PollResult` and never invents
traffic. Its status is one of:

- `ok`: the daemon answered and at least one flow parsed;
- `ok_empty`: the daemon answered but nothing parsed;
- `failed`: any error, recorded in `error`.

It also reports `lines_in_dump`, so a dump holding only a table-miss rule is
visible as such.

The monitor applies demo policy explicitly, **only on `failed`**, and reports
these under `/health → monitor`:

- `last_poll_status`, `consecutive_failures`, `last_successful_poll_at`;
- `last_lines_in_dump`, `last_demo_substituted`, `poll_counts`;
- `last_error`, which keeps the real failure even while demo flows are served.

The overall `status` is deliberately unchanged. "Degraded after N failures"
would be an operating point, and none has been fitted.

Tests cover the `failed` path against a real closed port. Tests for `ok` and
`ok_empty` are **blocked** on real dump output (`ML/testdata/ovs_dump_flows.txt`)
and are deliberately not written against hand-made dump lines.

### Flow mapping — two load-bearing mappings

`app/services/flow_mapping.py`. Four of the sixteen node features die silently
if either is dropped in a refactor:

- **`byte_count` → `Total Length of Fwd Packets`** — the graph builder derives
  `total_bytes_all` from *only* the Fwd/Bwd length columns. Drop it and node
  features 9 (`log_total_bytes_out`) and 10 (`log_total_bytes_in`) become 0.0
  for every host.
- **a real timestamp → `t`** — `FlowRecord` has no timestamp field, so the
  caller supplies the poll's observation time. `t` drives node features 11/12
  and edge features 14/15/16.

Both are asserted in `backend/tests/`.

### Feature parity: what the live path can actually supply

Audited against `compute_edge_features`; `numeric_columns()` zero-fills absent
columns.

| | count | which |
|---|---:|---|
| **edge, derivable** | 10 | `log_duration_s`, `log_total_packets`, `log_total_bytes`, `avg_packet_size`, `log_dt_since_pair`, `log_dt_since_src`, `window_position`, `direction_flag`, `log_bytes_per_s`, `log_packets_per_s` |
| **edge, pinned constant** | 2 | `fwd_packet_ratio` → **1.0**, `byte_asymmetry` → **+1.0** (OVS gives no directional split) |
| **edge, zeroed** | 8 | `log_max_fwd_len`, `log_max_bwd_len`, `log_iat_mean`, `iat_burstiness`, and `syn/rst/ack/psh_ratio` whenever `tcp_flags` is 0 — the normal case, since `dump-flows` does not print per-packet TCP flags |
| **node** | 16 | all derivable, given the two mappings above. Two (`log_windows_seen`, `burst_score`) are cold-start dependent until `HostHistory` warms. |

`fwd_packet_ratio` and `byte_asymmetry` are *pinned at 1.0*, not zeroed — worse
than a zero in one respect, because 1.0 is a legitimate in-distribution value
meaning "purely unidirectional", so the model cannot distinguish a genuinely
one-way flow from an artefact of our ingestion.

### Rule: the sensitivity control gates PHASE 2b

**The sensitivity control gates the measurement. A PHASE 2b result obtained
without it says nothing.**

On any new sample, run `ML/phase2b_sensitivity_check.py` **before**
`ML/phase2b_live_path_cost.py`, and read
`all_zero_edge_features.argmax_changed` in `ML/phase2b_sensitivity.json`:

- **0 means the sample cannot measure edge-feature damage.** Zeroing every edge
  feature changed no prediction, so no 2b delta on that sample, zero or
  otherwise, is evidence about the live path. Do not run 2b on it, or record
  its output as uninformative.
- **Above 0 means the sample can register damage.** 2b's deltas on it are worth
  reading.

**Enforced in code, not only here.** `phase2b_live_path_cost.py` refuses to
start, before loading the model, in any of these cases:

- `phase2b_sensitivity.json` is missing;
- it was run on a different sample, different weights or a different model card
  (all three compared by sha256);
- it reports `argmax_changed = 0`.

When the gate passes, the script prints that count as a share of real edges.
That share is the sample's resolution: 2b cannot show damage finer than it. The
gate sets no minimum, because any bar would be a judgement rather than a fitted
number. `--force-uninformative` runs anyway and stamps the results file
`sensitivity_gate: OVERRIDDEN (...)`.

It also refuses to start if `phase2b_results.json` already holds a run on a
different sample, so a new run cannot silently replace an earlier record. Move
the earlier run under `ML/phase2b_runs/<name>/` first, or pass `--overwrite`.

The first run below is the reason this rule exists.

### PHASE 2b run 1 (density-selected sample, epoch-31 model): uninformative

Files: `ML/phase2b_runs/run1_prefix_density_sample/`.

**The run.** `ML/phase2b_live_path_cost.py` ran on the v1 sample
(sha256 `abe50f86fbf12eae94800acc1e44f9eadd3c6a79ea2541310d90c56569e0d910`):
20,000 rows, 15,833 after preprocessing, 19 windows. Every delta is **+0.0000**
in that run's `phase2b_results.json`. The degraded, recounted and live
variants all equal baseline on the common-flow view, with 100% coverage.

**Why that zero proves nothing.** `ML/phase2b_sensitivity_check.py` is the
control that can fail, and it wrote that run's `phase2b_sensitivity.json`:

- **The degradation does reach the model.** Edge features change on 100% of
  edges and edge probabilities move by up to 0.233, so this is not a no-op bug.
- **But the sample doesn't need edge features.** Zeroing **all 20** edge
  features, far more damage than the live path does, changes **0 of 15,833**
  predictions. On this sample the classes are separable from ports, protocol
  and graph structure alone. The measurement cannot detect edge-feature damage
  here, whatever that damage is.

**Why this sample is so easy.** The blocks were selected for attack density,
not for windows that mix attack and benign traffic, so each attack class landed
in one or two near-pure minutes. The sample holds five contiguous 4,000-row
blocks from four days, and every timestamp is minute-resolution:

- Volumetric_Flood is two blocks (DDoS, DoS Hulk), each inside a single minute,
  with no BENIGN traffic in the same minute.
- PortScan is 3,984 rows inside a single minute.

A window that is one class end to end can be separated from destination port,
protocol and graph structure alone, which is what the all-zero control found.

**This run's record is kept deliberately**, beside run 2 rather than replaced
by it. Together the two runs are the argument for the control.

### PHASE 2b run 2 (mixed-window sample, retrained model)

Files: `ML/phase2b_results.json`, `ML/phase2b_sensitivity.json`, sample
`ML/testdata/cicids2017_sample.csv` (sha256 `2655e288…`), all from the
2026-10-04 Colab pass.

**The sample** is built by `ML/make_testdata_sample.py`, which searches windows,
not rows: per attack class, the run of 60 s windows holding the most windows with
at least `min_edges_per_graph` flows, the class, and BENIGN traffic. 18,264 rows,
58 windows, **52 of them MIXED**. It is 90.8% BENIGN; PortScan has 196 rows and
Botnet 168, so their figures carry their denominators.

**The control passed**: zeroing all 20 edge features moves 41 of 18,264
predictions. That is 0.22% on a 91%-benign slice and is **not** a measure of the
model's dependence on flow features; the full-test probes are (§4).

**Result, common flows, baseline → live** (`IDLE_TIMEOUT = 0`, so re-counting is
the optimistic case):

| Class | Baseline | Live | Change |
|---|---:|---:|---:|
| BENIGN | 0.9940 | 0.9941 | +0.0001 |
| Volumetric_Flood | 0.9670 | 0.9568 | −0.0102 |
| PortScan (196 rows) | 0.5208 | 0.3984 | **−0.1224** |
| BruteForce | 0.9234 | 0.9344 | +0.0110 |
| Botnet (168 rows) | 0.0000 | 0.0000 | 0 of 168 correct |
| Macro | 0.6811 | 0.6567 | −0.0243 |

**The macro cost is almost all PortScan**, the class that already fails its
gate on test. "Small cost" is true only at macro level. Missing features (−0.0232)
cost more than re-counting (−0.0038). Sub-poll flows are submitted once at
`IDLE_TIMEOUT = 0`, so short-lived classes, PortScan above all, are not
re-counted at all here.

**What stays unknown.** The §3 figures still describe the model on CICIDS2017
flows with the full feature set. The model's accuracy **on flows from this
capture path remains unmeasured.**

**Confidence of correct predictions on the run-2 sample**
(`ML/phase2b_sensitivity.json`):

| Class | Correct | p05 | p50 | p95 | ≥ 0.85 | ≥ 0.90 |
|---|---:|---:|---:|---:|---:|---:|
| Volumetric_Flood | 895 | 0.9369 | 0.9435 | 0.9539 | 100.0% | 95.9% |
| PortScan | 69 of 196 | 0.4714 | 0.6277 | 0.8096 | 0.0% | 0.0% |
| BruteForce | 404 | 0.7082 | 0.8920 | 0.9363 | 82.4% | 36.4% |
| Botnet | 0 of 168 | n/a | n/a | n/a | n/a | n/a |

It agrees with the test-split measurement in §6: Volumetric_Flood clears its 0.90
floor, PortScan does not reach 0.85. (Run 1's table, where Volumetric_Flood
reached 0.90 0.0% of the time, is the epoch-31 model on the v1 sample.)

---

## 6. Mitigation policy

`app/services/mitigation_policy.py`, built from the card's class list at
startup, validated, reported at `/health`, and **the only source of actions and
floors** (wired 2026-10-04, dry-run):

1. The backend sends `MitigationPolicy.wire()` with every `/flows` and `/flush`
   request.
2. The service's `SDNTranslator` has no table of its own. Without a policy it
   makes no rule; a policy naming a class outside the live taxonomy is refused
   with HTTP 422.
3. Every attack-classified flow that does not become a rule is returned as
   withheld, with its reason: `class_suppressed`, `below_floor`, `allowlisted`,
   `node_corroboration_absent`, `rule_cap`, or `no_policy`.
4. The service echoes the digest of the policy it applied. The backend accepts
   the rules only when the echo matches its own digest, and when the service
   reports `dry_run=True`. It logs rules admitted and each withholding reason.
   The digest, each class's floor and `dry_run` are published at `/health` under
   `ml_v2.policy`, so an operator can see which policy is in force.
5. No rule is installed. `SDNTranslator.install()` writes nothing in dry-run and
   refuses outside it, and no v2 rule reaches `EnforcementAgent` or
   `SelfHealingEngine` (`backend/tests/test_v2_rule_wiring.py`).

Before 2026-10-04 the backend built this policy and passed it nowhere. Rules were
made inside the service by the package's own six-class table (below), returned,
and discarded by the backend. That table is deleted.

The package's own `MITIGATION_POLICY` (deleted 2026-10-04) was keyed on the **old six-class taxonomy**
and was measured against the live contract as:

```
idx class              has policy?                   action
  1  Volumetric_Flood  NO  -- can NEVER fire a rule  -
  2  PortScan          YES                           drop
  3  BruteForce        NO  -- can NEVER fire a rule  -
  4  Botnet            YES                           drop_and_quarantine
DEAD keys (no such class): ['DDoS', 'SSHBrute', 'DoSHulk']
```

`translate()` does `.get(cls)` and `continue`s on `None`, silently. The only two
classes that could fire were the model's best (PortScan) and its worst (Botnet).

The replacement enforces two invariants at startup, both fatal:

1. every non-BENIGN class in the card **must** have an entry;
2. every entry **must** name a class in the card.

| class | action | note |
|---|---|---|
| `Volumetric_Flood` | `meter` | rate-limit, not drop — the victim still serves everyone else |
| `PortScan` | `drop` | short TTL. Mostly predicted as BruteForce and vice versa (§3) |
| `BruteForce` | `drop_port` | the model does not separate it from PortScan (§3) |
| `Botnet` | **`alert_only`** | never enforced; see §7 |

"Deliberately not enforced" is an explicit `alert_only` entry, never an absent
key, so a decision and an oversight cannot look the same.

### What these floors let through

**Owned by `MODEL_BEHAVIOUR.md`:** §6 for the test split (offline; what clears
each floor, the false-action ceiling, and why PortScan mislabelled as BruteForce
never becomes a rule), and §1 for the live run on the Phase 2b sample
(`ML/live_rule_check.py` → `ML/live_rule_check.json`).

The mechanical points that belong here:

- The offline counts apply the edge-head floor only. The translator also requires
  node corroboration (below), which can only remove rules, so every count of a
  wrong action there is an upper bound.
- One rule covers a (source, destination, protocol) pair per window, so admitted
  rules are far fewer than flows above a floor.
- **No floor moves.** Botnet's 1.01 is a **disabled rule**, not a threshold anyone
  should tune. PortScan's floor is not reached on either population; that is
  reported, not adjusted.

### The confidence floors are unfitted

A rule fires only when `argmax == class` **and** `P(class) >= min_conf`. The
`min_conf` values in `mitigation_policy.py` are **inherited from the training
package's old table and fitted to nothing**:

| Class | `min_conf` in `mitigation_policy.py` | Fitted value in `threshold_study.json` |
|---|---:|---:|
| `Volumetric_Flood` | 0.90 | 0.4571 |
| `PortScan` | 0.85 | 0.8706 |
| `BruteForce` | 0.85 | not fitted |
| `Botnet` | 1.01 (a disabled rule; `alert_only`) | 0.5000 (grid floor) |

`mitigation_policy.py` does not read `per_class_min_conf`, so the fitted values
have no effect, and §4 says why none is safe to adopt. Unfitted as they are, the
inherited floors are what make the measurement above come out as it does.

### Enforcement is dry-run

`SDNTranslator.dry_run` stays `True`. No `min_conf` has been lowered to make
rules appear.

> **TODO before enforcement could ever be enabled:** the allowlist must cover
> **gateways, DNS, and the SDN controller itself**. It currently holds only
> `255.255.255.255` and `0.0.0.0`. An IDS with write access to the network is a
> denial-of-service tool if it is wrong.

### Node corroboration suppresses rules; it never generates them

`SDNTranslator` has `require_node_corroboration=True`: a rule is emitted only if
the edge head clears the class's `min_conf` **and** the source host's node-head
threat is at least `node_threshold` (0.60). The node head is weak (test binary
F1 0.4475), so it is fair to ask whether rules rest on a bad signal. They do
not. Corroboration is an AND, so the emitted rules are always a **subset** of
what the edge head alone would emit. A weak node head can remove rules; it
cannot add one. The gate makes enforcement rarer, not wronger. It fails safe.

The cost is on the detection side. The gate suppresses rules for real attacks
as readily as for false ones, so "no rule" says even less than it would without
it. When enforcement is eventually considered, the realistic choice is between
this weak but conservative gate and no gate at all. The gate is the better
default. This is the only place the node head influences anything, and it can
only veto.

---

## 7. Claims this backend must not make

Not in code, comments, logs, API responses, the UI, or a demo script:

1. **Zero-day or novel-attack detection.** The split is `episode`; train and
   test can share an attack burst. `MANIFEST.json`: *"these are NOT
   novel-attack numbers."*
2. **Real-time performance.** Nothing has been measured against a latency
   budget; the monitor polls on a 5 s timer.
3. **Production readiness.**
4. **Host/node-level attack attribution.** Node head test binary F1 0.4475.
5. **Botnet detection.** The test split holds no Botnet edges; on the Phase 2b
   sample 0 of 168 are correct. The epoch-31 model predicted all 266 of its test
   Botnet edges BENIGN.
6. **Per-class attack identification for PortScan or BruteForce.** The model
   does not separate them (§3).

### If a Botnet label is returned

It is **unreliable** and must be presented as such. The backend attaches a
`reliability` note to any verdict carrying that label, surfaces it at
`/health → ml_v2.unreliable_classes`, and never enforces on it.

---

## 8. Known issues and deliberate deferrals

### Three-way torch split

| Where | torch | torch-geometric | pandas | numpy | python |
|---|---|---|---|---|---|
| Model exported from (retrain, 2026-10-03; `model_card.json.framework` + Cell A preflight) | **2.11.0+cu130** | 2.8.0.post1 (preflight) | not recorded | not recorded | 3.13.15 |
| Epoch-31 model (`ML/prefix_epoch31/model_card.json`) | 2.11.0+cu128 | not recorded | not recorded | not recorded | 3.13.15 |
| Local dev / pytest on this machine | **2.13.0+cpu** | **2.8.0** | 2.3.3 | 2.2.6 | 3.10.10 |
| Inference container (`docker/inference.Dockerfile`) | **2.4.0** | **2.5.0** | 2.3.3 (pinned) | 2.2.6 (pinned) | 3.12 |
| `backend/requirements.txt` pins | `>=2.4.1` | `==2.5.0` | `==2.2.0` | `==1.26.0` | — |

**pandas is pinned in the inference Dockerfile for a reason.** The package's
`requirements.txt` says `pandas>=2.0`, and the first unpinned container build
resolved **pandas 3.0.5**. That major release changed copy-on-write and default
string dtypes, and the engine builds every window through pandas. The container
now uses the pandas/numpy versions the package suite passed on locally. The model
card doesn't record which pandas the model was trained with, so whether training
ran pandas 2 or 3 is unknown.

Local is well ahead of the container pin and disagrees with `requirements.txt`
on `torch-geometric` outright (2.8.0 installed vs 2.5.0 pinned). **Local test
runs and the container are not exercising the same code.**

`InferenceEngine.from_artifacts()` loads weights with **`weights_only=False`**.
It works on 2.13.0 locally. Loading the model inside the container on 2.4.0 is a
required verification step — see §10.

### Deliberate deferral: new taxonomy strings are not written on-chain

`Incident.attack_type` in SQLite receives the model's label with its provenance.
The **on-chain** `attack_type` stays on the existing vocabulary until the
taxonomy is settled, because chain writes are irreversible and the taxonomy is
not final. This is a decision, not an oversight.

### Threshold endpoint

`PATCH /api/v1/settings` still moves `threat_threshold`, and the UI may call it.
Its scope is now explicit: it moves the **v1/heuristic gate only**. The v2 gate
is an operating point fitted against measured precision and is not stored on
`settings`, so there is structurally nothing there to reassign — not a guard
that can be forgotten. `GET /api/v1/settings` reports the model gate read-only
with its provenance (`ml_binary_gate`, `ml_binary_gate_source`,
`ml_gate_mutable: false`), and the audit entry records `scope:
v1_heuristic_gate_only`.

### Pre-existing, not introduced here

- `tests/test_r07_ml_evaluation_ovs_robustness.py::test_production_default_threshold_is_conservative_075`
  used to **fail on machines whose local `backend/.env` sets `0.40`**, and pass on
  a fresh clone: `backend/.env` is untracked, and the test read the effective
  setting rather than the default its name promises. Since 2026-10-04 it checks
  the declared default and the two tracked templates (`.env.example`,
  `.env.docker`), all `0.75`. No threshold was changed. The local `0.40` remains
  a per-machine choice. Three different values exist across `config.py` (0.75),
  `backend/.env` (0.40) and `.env.docker` (0.75), plus `0.75`/`0.50` inline in
  `threat_analyzer.py`, `graph_state.py` and `alerts.py`.
- `MODEL_SOURCE_PATH` is dead config in all three environments — no `model.py`
  exists at any configured path, so `_load_model_class()` always falls through
  to the bundled class.
- `SCALER_PATH` is dead — `use_scaler_for_inference` is false everywhere and
  `NODE_FEATURES.md` says the scaler is not used at inference.
- `Error.md` is a 6-byte file containing only a BOM, yet is cited by name in
  ~30 comments and has a test file named after it.
- **A missing flow duration has two different defaults across three sites.**
  `flow_parser.py:92` falls back to `"5.0"` when a dump line has no `duration=`,
  while `schemas.py:35` (`duration_sec`, `default=1.0`) and
  `flow_mapping.py:134` (`_num(..., 1.0)`) use `1.0`. The `5.0` is the most
  plausible-looking wrong value available: it equals the poll interval, so
  `Flow Bytes/s` becomes `byte_count / 5.0` and nothing downstream can tell it
  was a default. In the repo, a dump line never seems to lack `duration=`:
  - the daemon runs `sudo ovs-ofctl dump-flows <switch>` without `--no-stats`
    (`enforcement_daemon.py:79`);
  - the only lines marked as verbatim real captures, both from this project's
    topology (`test_error_md_regressions.py:463-478`), carry `duration=`;
  - lines without it appear only in hand-written test fixtures.

  `ML/testdata/ovs_dump_flows.txt` will confirm or refute this. Whichever
  default is right, the three sites should agree.

### Scaling

`model_card.json` says `scaling.mode: ema_streaming` and instructs loading
`edge_scaler.json` / `node_scaler.json`. **Neither file was exported**, and
`from_artifacts` silently leaves both scalers `None`. This is **not** a
mismatch: `train.py` and `evaluate.py` never reference `EMAScaler` (the only
scaler in training is `torch.amp.GradScaler`, which is AMP loss scaling), so the
model was trained and tested on raw builder output, which is self-normalising by
construction. Running with no scaler is faithful to training. Cards exported
after 2026-09-13 carry `scaling.used_in_this_export: false`.

---

## 9. Running it

**Start with `RUN_GUIDE.md`**: both start-up paths, and the nine-check verification
(`python ML/verify_stack.py`).

```bash
docker compose up --build            # start order: blockchain → inference → backend → frontend
```

Ports: inference `8081→8080`, backend `8001→8000`, frontend `5174`,
blockchain `8546`.

**The backend does not wait for the inference service to be healthy**, only for
it to have started (`condition: service_started`). That is deliberate. The
backend is designed to run with the service down: an unreachable service is
non-fatal at boot and yields no v2 scores (§5). On a fresh clone without the
gitignored `weights.pt`, the inference container never becomes healthy, and a
health gate would stop the backend from ever starting, demo mode included. A
**mismatched** contract from a reachable service is still fatal.

Backend env (set in `docker-compose.yml`):

| var | value | meaning |
|---|---|---|
| `GS2_ENABLED` | **`false`** | v2 path off in the default stack. The provenance gate (§5) now makes enabling it safe; it stays off while the operating points are provisional (§4) |
| `GS2_SERVICE_URL` | `http://inference:8080` | compose-internal DNS |
| `GS2_MODEL_DIR` | `/app/ML` | where `model_card.json` is read from |
| `GS2_REQUIRE_CONTRACT` | `true` | refuse to boot on a bad contract |

Check it came up:

```bash
curl -s localhost:8001/health | jq .ml_v2
```

---

## 10. Verification status

| Check | Status |
|---|---|
| Contract loads from real artefacts; classes/features match the card in order | ✅ verified |
| Startup refuses: missing card, corrupt JSON, wrong `contract_version`, missing `BENIGN`, contradictory feature count, **reordered** or **truncated** class list, reordered features | ✅ verified, all 8 |
| Policy: every card class has an entry; every entry names a card class; `Botnet` is `alert_only` | ✅ verified |
| `SDNTranslator().dry_run is True` | ✅ verified |
| Package suite (`ML/graphsentinel_v2`, local, Windows) | ✅ **98 passed, 7 skipped, 0 failed**. All 7 skips are training-only dependencies (`pyarrow`, and two tests guarded as training-only) that the inference path doesn't need |
| Backend suite, full (2026-10-04) | ✅ **233 passed, 3 skipped, 0 failed**: the threshold test points at the declared default (§8); 6 new tests pin the policy wiring and what `/health` publishes about it (§6) |
| Backend suite, full, after the gate, poll status, compose and contract changes (2026-09-14) | ✅ **226 passed, 3 skipped, 1 failure that predates this work**. The 226 are the previous 208 plus 18 new tests: 7 provenance gate, 4 poll status, 7 service contract. The failure is `test_production_default_threshold_is_conservative_075`: it expects `0.75` but `backend/.env` sets `0.40`, it passes with `THREAT_THRESHOLD=0.75`, and nothing in this integration touches it |
| **Retrained model loads inside the container on torch 2.4.0** | ✅ **verified 2026-10-04**: image rebuilt (Docker's data disk had been lost). Output committed: `ML/retrain_logs/container_load_output.txt` (script `ML/container_load_check.py`); summary in `MODEL_BEHAVIOUR.md` §2 |
| Retrained model, inference service over HTTP | ✅ verified 2026-10-04: healthy after ~45 s, `/health` 200, `/contract` 2.0.0 with the card's class order |
| **Epoch-31 model loaded inside the container on torch 2.4.0** | ✅ **verified 2026-09-14**: python 3.12.14, torch `2.4.0+cpu`, torch_geometric 2.5.0, pandas 2.3.3, numpy 2.2.6. `from_artifacts` succeeds with `weights_only=False`, weights sha256 matches `MANIFEST.json`, the parameter count the card states, class list matches in order, `dry_run=True` |
| Inference service over HTTP, in the container | ✅ verified: `/health` returns 200 once the model has loaded (~45 s), Docker healthcheck `healthy`, `/contract` serves version 2.0.0 and the card's class order |
| Backend client against the live service | ✅ verified: `probe()` reports true when the service is up and false on a dead port. The contract check accepts the live `/contract`, and refuses it once the classes are reordered or the version is changed to 2.1.0. With the service down, `score_flows` returns `available: false` and no windows, with no fallback |
| Malformed flow (bad IP, missing `dst_port`) dropped per-flow with a logged reason; rest of batch kept | ✅ verified |
| Service `/contract` cross-checked against the backend's card at boot and before the first scoring | ✅ wired and verified against the live service (see above) |
| **PHASE 2b: cost of missing live-path features** (§5) | ⚠️ **run 2 measured, on a small slice.** Control passed (41 of 18,264 move); live costs −0.0243 macro, almost all PortScan (−0.1224, 196 rows). Run 1 (epoch-31, density sample) stays as the record of why the control exists |
| **OVS poll re-counting: size of the damage** (§5) | ⚠️ **ran, uninformative** for the same reason, and at the optimistic `IDLE_TIMEOUT=0` |
| **OVS poll re-counting: choice of fix** (§5) | ❌ **open** — needs `ML/testdata/ovs_dump_flows.txt` for real entry granularity and `idle_timeout` |
| **Randomised flows reaching v2** (§5) | ✅ **fixed** (`2adaec5`): allowlist provenance gate at the monitor. 7 tests with real `demo_flows()` output and a verbatim captured OVS line; a denylist version and a deleted gate are both caught. `GS2_ENABLED` stays `false` while the operating points are provisional |
| **Poll failures looking like quiet traffic** (§5) | ✅ **fixed** (`37a4060`): `PollResult`, and demo substitution only on `failed`. The `failed` path is tested against a real closed port. ❌ `ok`/`ok_empty` tests blocked on `ovs_dump_flows.txt` |
| **Backend starts without a healthy inference service** (§9) | ✅ `4071505`. Unreachable at boot is non-fatal; a mismatched or malformed served contract is fatal (`ContractError`), with 7 tests |
| **Operating points** (§4) | ⚠️ **provisional.** `binary_gate` 0.5 sits on a fixed value appended to the search grid; run-to-run variation is unmeasured. Awaiting `grid_and_determinism_check.py` (run outside this repo). v2 reports `alerting_enabled: false` |
| **`Volumetric_Flood → meter` can fire** (§6) | ✅ **measured**, on the test split and live on the sample: `MODEL_BEHAVIOUR.md` §6 and §1 |
| **End-to-end on real OVS flows** | ❌ **blocked** — needs `ML/testdata/ovs_dump_flows.txt` |
| **Retrained model installed** | ✅ 2026-10-04, after the container load. Epoch-31 files in `ML/prefix_epoch31/` |
| **What the backend floors would let through** (§6) | ✅ measured on test: at most 2 of 389 benign-as-attack and at most 118 of 20,976 wrong-class edges clear their floors; Volumetric_Flood is the only enforceable class. Floors unchanged |
| **Backend mitigation policy wired to rule generation** (§6) | ✅ **wired, dry-run** (2026-10-04). The policy travels with every request; the service's six-class table is deleted; rules are accepted only under the backend's own digest; withholdings logged with reasons. Tests: `ML/graphsentinel_v2/tests/test_sdn_policy.py`, `backend/tests/test_v2_rule_wiring.py`, both failing without the wiring. Live: 58 of 58 windows echoed the digest; 12 rules, all on correct flows (`ML/live_rule_check.json`) |
| **PortScan floor reachable** (§6) | ❌ **no.** 0 of 68 correct live predictions reach 0.85 on the sample; 0.0% on the test split. Reported, not adjusted |
| **`UNRELIABLE_CLASSES`** | ⚠️ annotates only. With the policy now live, suppressing PortScan and BruteForce would mean something; proposed as its own change |
| **PortScan split boundary** (§4) | ⚠️ **named limitation.** Minute 14:55 is in train, validation and test; validation is not independent of training for PortScan. Measurements queued for the next Colab pass |

The rows marked ❌ are still open. The plumbing is verified end to end in the
container. What remains unmeasured is the model's accuracy on flows from this
capture path, and until that is measured the v2 path must not be presented as a
detector.

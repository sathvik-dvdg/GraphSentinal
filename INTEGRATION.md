# GraphSentinel v2 — backend integration

What is wired in, where each number came from, and what this system must not
claim. Written for engineers working on this repo.

Every performance figure below is traceable to a file in this repo. Anything
not traceable is marked `TODO: unverified` rather than given a plausible value.

---

## 1. Artefacts

Digests are from `ML/MANIFEST.json` and were verified against the files on disk
on 2026-09-13.

| File | Bytes | sha256 | In git? |
|---|---:|---|---|
| `ML/model_card.json` | 9,792 | `d9637ea6b6846779ebdebcf763832b97341e1b752d68737fc430acca1ff3b996` | ✅ tracked |
| `ML/test_report.json` | 91,658 | `308cb5e03dab69e7d0f08fd3272fed92bc3e9adedc027eab0bca914d85cbbd8b` | ✅ tracked |
| `ML/MANIFEST.json` | 1,650 | — | ✅ tracked |
| `ML/weights.pt` | 76,178,229 | `0dbbaf388dbffc2ce0753553b346e520b3aa0b557cdb6c618792f51eb0a38989` | ❌ **gitignored** |
| `ML/model.ts` | 76,277,094 | `2efbb012389977ee987ffabc0e01c47ed41328924784e37c46c3353631a72272` | ❌ **gitignored** |

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
# must print 0dbbaf388dbffc2ce0753553b346e520b3aa0b557cdb6c618792f51eb0a38989
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

### Read this before quoting any number

`model_card.json`'s `metrics` block and `test_report.json`'s `metrics` block use
**identical key names for different numbers**. `test_report.json` records
`best_val_metric = 0.7567619377362611`, which is exactly the card's
`metrics.edge_macro_f1`.

> **`model_card.json.metrics` = VALIDATION (best epoch 31).
> `test_report.json.metrics` = TEST. Headline numbers come from
> `test_report.json`.**

Cards exported after 2026-09-13 carry a `metrics_split` key that says so. The
card currently in `ML/` predates that fix, so the rule above applies to it.

### Edge head (the deliverable), TEST split

Source: `ML/test_report.json` → `edge_classification_report`.

| class | precision | recall | F1 | support |
|---|---:|---:|---:|---:|
| BENIGN | 0.99848 | 0.99995 | 0.99922 | 175,269 |
| Volumetric_Flood | 0.99981 | 0.98235 | 0.99100 | 27,191 |
| PortScan | 0.96085 | 1.00000 | 0.98003 | 23,807 |
| BruteForce | 1.00000 | 0.38005 | 0.55078 | 792 |
| Botnet | 0.0 | 0.0 | **0.0** | 266 |

`edge_macro_f1` 0.7042 · `edge_binary_f1` 0.9974 · `edge_binary_pr_auc` 0.99974
· `edge_recall_at_fpr_0.001` 0.9955.

### Node head — NOT USED

`node_binary_f1` **0.1407**; node PR-AUC by class: `Volumetric_Flood` 0.0628,
`PortScan` 1.0, `BruteForce` 0.0516, `Botnet` 0.0075 — below base rate for three
of four attack classes. The backend discards `WindowResult.detections` unread.
Host-level attribution is not a claim this system makes.

### Split protocol

`config.data.split_strategy` is `episode`. `ML/MANIFEST.json` states it plainly:
*"episode — train and test can share a burst; these are NOT novel-attack
numbers."* The config also carries `holdout_attacks: ['Botnet']`, but that key is
only read by `_split_attack_holdout`, which the `episode` strategy never calls —
it is **dormant config with no effect on this run**. Botnet was in training and
still scores 0.0.

---

## 4. Operating points

### The artefact

| File | Bytes | sha256 |
|---|---:|---|
| `ML/threshold_study.json` | 2,662 | `abed80b3de3399fd1f2e28c574c4893332a33c847d610bb92077f9235bfa48d8` |
| `ML/threshold_flow_level.csv` | 509 | `f237b62b0b8f386a248438e6649a411d7dad9acb57067f041eeeaf76acafda41` |
| `ML/threshold_window_level.csv` | 2,491 | `efdc7d6a3b612ce180630d9dfef6e4f1d08400ed6892b0c54c3e34434e20cec4` |

All three are committed byte for byte: `.gitattributes` marks top-level
`ML/*.json` and `ML/*.csv` as `-text`, so git never rewrites their line endings
and these digests keep matching the checked-out files.

It was produced by cell 33 of `ML/GraphSentinel_Training.ipynb`. The file
records its own provenance: `fitted_on: "validation split"`,
`binary_criterion: "max F1 on validation"`, `checkpoint_epoch: 31`,
`split_protocol: "episode"`, and the caveat *"thresholds fitted on validation
and reported on test/monday/thursday; monday has no attacks so only FPR is
meaningful; thursday is unseen families with no class label"*.

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
threshold. The script's author confirms this is a bug in the script. Three of
the study's four numbers sit exactly on that list: the binary gate 0.5,
Volumetric_Flood 0.8, and Botnet 0.5. The file's own label,
`binary_criterion: "max F1 on validation"`, may therefore overstate how fitted
the gate is. `grid_and_determinism_check.py` (parts A and B, run outside this
repo) refits without the appended values and measures how wide the F1 plateau
around each value is. `TODO: unverified` until it comes back.

**The binary gate's validation precision and recall are not in the file.** The
pair 0.9910 / 0.9989 quoted earlier is still not traceable to any file. `0.5` is
also one of the six fixed values that `grid_for` adds to its quantile grid
(`0.5, 0.8, 0.85, 0.9, 0.95, 0.99`, cell 33 line 226), not a data quantile. When
several thresholds tie on F1, `idxmax` picks the lowest.

`InferenceEngine`'s default `threat_threshold=0.75` is a **package default, not
a fitted value**, and is not adopted. The engine applies no threshold to
`WindowResult.flows`; the gate is applied in the backend, where its provenance
is recorded.

### Flow level, binary gate 0.5

From `flow_level` in the JSON (identical to `threshold_flow_level.csv`):

| Set | Flows | Attack flows | Precision | Recall | FPR | F1 |
|---|---:|---:|---:|---:|---:|---:|
| test | 227,325 | 52,056 | 0.99975 | 0.99489 | 0.0000742 (13 of 175,269) | 0.99731 |
| monday | 500,530 | 0 | n/a | n/a | **0.0000020** (1 of 500,530) | n/a |
| thursday | 426,958 | 2,111 | 0.05670 | 0.89010 | **0.07357** (31,258 of 424,847) | 0.10662 |

On test, the 266 attack flows the gate misses equal, in count, the 266 Botnet
edges that `test_report.json` records as predicted BENIGN.

### Window level, ≥ 5 flows in 60 s

From `threshold_window_level.csv`, rows with `min_flows=5`:

| Set | Windows | Attack windows | Alerted | TP | FP | FN | Precision | Recall | FPR | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| test | 265 | 80 | 25 | 25 | 0 | **55** | 1.0000 | **0.3125** | 0.0000 | 0.4762 |
| monday | 486 | 0 | 0 | 0 | 0 | 0 | n/a | n/a | 0.0000 (0 of 486) | n/a |
| thursday | 485 | 96 | 77 | 67 | 10 | 29 | 0.8701 | 0.6979 | 0.0257 (10 of 389) | 0.7746 |

**On test, the rule alerts on 25 of 80 attack windows: 55 attack windows
produce no alert.** Precision 1.0000 is the flattering half; recall 0.3125 is
what an operator lives with. Lowering the rule does not recover recall: at
`min_flows=1`, recall is only 0.3250 (26 of 80), at precision 0.7647. The
misses are therefore not a tuning problem. Since every attack flow the gate
misses at flow level is a Botnet flow, one explanation is windows whose only
attack traffic is Botnet. That is a hypothesis; these files don't break windows
down by class.

### Monday and Thursday disagree on the false-alarm rate

Under the same 0.5 gate, flow-level FPR is **0.0000020 on Monday and 0.07357 on
Thursday**, over four orders of magnitude apart. At window level with ≥ 5 flows,
Monday raises **0 false alerts in 486 windows** and Thursday raises **10 in 389
non-attack windows**.

"Zero false alerts on a full working day" is true, and it is one day. The honest
false-alarm range lies between these two, and which one a live network resembles
is unknown. Thursday is not all benign: it carries 2,111 attack-labelled flows
from families the model never trained on. Some of its "false positives" may be
real attacks that CICIDS2017's ground truth labels BENIGN. That is possible, not
established.

**Thursday's recall is not evidence of novel-attack detection.** Its flow-level
recall of 0.890 comes at precision 0.0567: 31,258 of its 33,137 flow-level
alarms (94.3%) are false.

### ⚠️ The `shuffled` control is uninformative. Do not cite it

The file carries a fourth `flow_level` entry, `dataset: "shuffled"`, plus
`shuffled` rows in `threshold_window_level.csv`. It reports precision 0.99979,
recall 0.99489, F1 0.99733, with TP (51,790) and FN (266) **identical** to
`test`. At `min_flows=5` its window rows are identical to test too. The notebook
prints beside it: *"shuffled should collapse. If its recall stays high, the
model is not reading the edge features and every other number is suspect."*
**That interpretation does not apply to this control.**

- **What the control actually does.** Cell 33 loops
  `for g in graphs["test"]` and permutes `h.edge_attr` **within each graph**.
- **What the notebook claims it does.** Cell 32's markdown table says the
  features are permuted *"across windows"*, which is not what the code does.
- **Why it cannot fail.** According to the notebook's author, a 60 s window in
  this capture is overwhelmingly one class, so shuffling features among a
  window's own edges barely changes any edge. The author reports replacing it,
  during separate ablation work, with a global shuffle that *did* degrade the
  model. That result is not in this repo.

So the row is neither alarming nor reassuring. The dangerous misreading is to
take it as evidence that the pipeline is sound. No one should cite it.

### Per-class SDN confidence floors: fitted, but not used

`per_class_min_conf` holds one fitted floor per class. The fit uses the same
firing rule the SDN layer applies: fire only when `argmax == class` and
`P(class) >= min_conf` (cell 33 lines 416, 440). Values from the file, rounded:

| Class | Fitted `min_conf` | Val prec | Val rec | Test prec | Test rec | Test F1 |
|---|---:|---:|---:|---:|---:|---:|
| Volumetric_Flood | 0.8000 | 1.0000 | 1.0000 | **0.0000** | **0.0000** | **0.0000** |
| PortScan | 0.7083 | 0.9968 | 0.9974 | 0.9998 | 0.9999 | 0.9998 |
| BruteForce | 0.4540 | 0.9965 | 0.6597 | 1.0000 | 0.3813 | 0.5521 |
| Botnet | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

**The backend does not read these.** `mitigation_policy.py` still carries the
inherited, unfitted floors (see §6). Three things about the file itself:

- **Volumetric_Flood reads 0.0 on test, which contradicts §3.** There,
  `test_report.json` gives precision 0.99981 and recall 0.98235 at plain argmax.
  `pr_table` returns NaN when nothing fires (line 236), and the file keeps NaN
  when it occurs (Monday's recall is stored as `NaN`). So the 0.0 means
  something **did** fire at ≥ 0.80, and none of it was correct. Under
  investigation; `mitigation_policy.py` is unchanged until the result is known.
- **This file and `test_report.json` did not score the same predictions.** The
  rule fires only on argmax predictions, so on identical predictions gated
  recall can never exceed argmax recall. Yet BruteForce's gated test recall is
  302 of 792 here, against 301 of 792 at argmax in `test_report.json`. §3's
  headline numbers and these operating points come from different inference
  passes over the same edges, and will not reconcile exactly. See "Run-to-run
  variation" below.
- **`fitted: true` does not mean a fit happened.** It is set whenever the
  validation set contains at least one predicted and at least one true edge for
  the class (lines 411, 446). Botnet's F1 is 0 at every threshold, so `idxmax`
  returns the lowest grid value, and its 0.5 is the grid floor, not a fit.
  Volumetric_Flood's 0.8 and the binary gate's 0.5 are both among the fixed grid
  values. Only PortScan and BruteForce landed on data quantiles.

### Run-to-run variation: present, unmeasured

**Every figure in this section and in §3 carries run-to-run variation of
unmeasured size.** The repo already holds two runs of the same study that
disagree.

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

### PHASE 2b run 1 (density-selected sample): uninformative

**The run.** `ML/phase2b_live_path_cost.py` ran on
`ML/testdata/cicids2017_sample.csv` (sha256 `abe50f86fbf12eae94800acc1e44f9eadd3c6a79ea2541310d90c56569e0d910`,
not committed): 20,000 rows, 15,833 after preprocessing, 19 windows. Every delta
is **+0.0000** in `ML/phase2b_results.json`. The degraded, recounted and live
variants all equal baseline on the common-flow view, with 100% coverage.

**Why that zero proves nothing.** `ML/phase2b_sensitivity_check.py` is the
control that can fail, and it writes `ML/phase2b_sensitivity.json`:

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

**The replacement sample** is built by a Colab cell
(`make_testdata_sample.py`, not in this repo) that searches windows rather than
rows. It keeps the run of consecutive 60 s windows holding the most "usable"
windows: at or above `min_edges_per_graph`, with both target-class and BENIGN
traffic. Ties go to the fewest rows, so an adjacent pure burst isn't swept in.
Mixed windows are necessary, not sufficient, so that sample must also pass the
rule above before any 2b number from it is believed.

**This run's record is kept deliberately.** When a new sample's run is added,
it goes beside this one, not in its place. Together the two runs are the
argument for the control.

**What stays unknown.** The §3 figures still describe the model on CICIDS2017
flows with the full feature set. The model's accuracy **on flows from this
capture path remains unmeasured.**

**What this sample does show, about the SDN floors** (`phase2b_sensitivity.json`,
confidence of correct predictions only):

| Class | Correct | p05 | p50 | p95 | ≥ 0.80 | ≥ 0.85 | ≥ 0.90 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Volumetric_Flood | 4,614 | 0.6939 | 0.7154 | 0.7231 | 1.0% | 0.0% | **0.0%** |
| PortScan | 3,981 | 0.8338 | 0.9370 | 0.9425 | 99.8% | 89.2% | 88.4% |
| BruteForce | 382 | 0.7472 | 0.9478 | 0.9588 | 80.1% | 79.8% | 77.0% |
| Botnet | 0 of 544 | n/a | n/a | n/a | n/a | n/a | n/a |

On this sample, `Volumetric_Flood → meter` at its 0.90 floor in
`mitigation_policy.py` **cannot fire**: not one correct prediction reaches it.
This is a different population from the test split §4 reports on, so the §6
note on that row waits for the test-split confidence check. The direction
agrees with the 0.0 test recall in `threshold_study.json`.

---

## 6. Mitigation policy

`app/services/mitigation_policy.py`, built from the card's class list at
startup, passed to `SDNTranslator`. The module global is never mutated.

The package's own `MITIGATION_POLICY` is keyed on the **old six-class taxonomy**
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
| `PortScan` | `drop` | short TTL; strongest class (test F1 0.9800) |
| `BruteForce` | `drop_port` | test recall 0.3801 — misses ~2/3 of real brute force |
| `Botnet` | **`alert_only`** | never enforced; see §7 |

"Deliberately not enforced" is an explicit `alert_only` entry, never an absent
key, so a decision and an oversight cannot look the same.

### The confidence floors are unfitted

A rule fires only when `argmax == class` **and** `P(class) >= min_conf`. The
`min_conf` values in `mitigation_policy.py` are **inherited from the training
package's old table and fitted to nothing**:

| Class | `min_conf` in `mitigation_policy.py` | Fitted value in `threshold_study.json` |
|---|---:|---:|
| `Volumetric_Flood` | 0.90 | 0.8000 |
| `PortScan` | 0.85 | 0.7083 |
| `BruteForce` | 0.85 | 0.4540 |
| `Botnet` | 1.01 (unreachable; `alert_only`) | 0.5000 |

`mitigation_policy.py` does not read `per_class_min_conf`, so the fitted values
have no effect. They are also not yet safe to adopt: see §4, where the
Volumetric_Flood floor scores 0.0 on test, and Botnet's value is a grid floor
rather than a fit. The study's "current" column lists Botnet at 0.80. That is
the training package's old table; the backend's Botnet entry is `alert_only` at
1.01.

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
F1 0.1407), so it is fair to ask whether rules rest on a bad signal. They do
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
4. **Host/node-level attack attribution.** Node head test binary F1 0.1407.
5. **Botnet detection.** Test F1 **0.0000**, PR-AUC 0.0024, all 266 test edges
   predicted BENIGN, unstable across identical reruns.

### If a Botnet label is returned

It is **unreliable** and must be presented as such. The backend attaches a
`reliability` note to any verdict carrying that label, surfaces it at
`/health → ml_v2.unreliable_classes`, and never enforces on it.

---

## 8. Known issues and deliberate deferrals

### Three-way torch split

| Where | torch | torch-geometric | pandas | numpy | python |
|---|---|---|---|---|---|
| Model exported from (`model_card.json.framework`) | **2.11.0+cu128** | not recorded | not recorded | not recorded | 3.13.15 |
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
  **fails**: it asserts `threat_threshold == 0.75` while `backend/.env` sets
  `0.40`. Three different values exist across `config.py` (0.75),
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
| Backend suite, full, after the gate, poll status, compose and contract changes (2026-09-14) | ✅ **226 passed, 3 skipped, 1 failure that predates this work**. The 226 are the previous 208 plus 18 new tests: 7 provenance gate, 4 poll status, 7 service contract. The failure is `test_production_default_threshold_is_conservative_075`: it expects `0.75` but `backend/.env` sets `0.40`, it passes with `THREAT_THRESHOLD=0.75`, and nothing in this integration touches it |
| **Model loads inside the container on torch 2.4.0** | ✅ **verified 2026-09-14**: python 3.12.14, torch `2.4.0+cpu`, torch_geometric 2.5.0, pandas 2.3.3, numpy 2.2.6. `from_artifacts` succeeds with `weights_only=False`, weights sha256 matches `MANIFEST.json`, 654,851 parameters as the card states, class list matches in order, `dry_run=True` |
| Inference service over HTTP, in the container | ✅ verified: `/health` returns 200 once the model has loaded (~45 s), Docker healthcheck `healthy`, `/contract` serves version 2.0.0 and the card's class order |
| Backend client against the live service | ✅ verified: `probe()` reports true when the service is up and false on a dead port. The contract check accepts the live `/contract`, and refuses it once the classes are reordered or the version is changed to 2.1.0. With the service down, `score_flows` returns `available: false` and no windows, with no fallback |
| Malformed flow (bad IP, missing `dst_port`) dropped per-flow with a logged reason; rest of batch kept | ✅ verified |
| Service `/contract` cross-checked against the backend's card at boot and before the first scoring | ✅ wired and verified against the live service (see above) |
| **PHASE 2b: cost of missing live-path features** (§5) | ⚠️ **run 1 uninformative.** All deltas +0.0000 on the density-selected sample, but zeroing all 20 edge features also changes 0 of 15,833 predictions. A mixed-window sample is being generated; per the §5 rule, its sensitivity control runs **before** 2b |
| **OVS poll re-counting: size of the damage** (§5) | ⚠️ **ran, uninformative** for the same reason, and at the optimistic `IDLE_TIMEOUT=0` |
| **OVS poll re-counting: choice of fix** (§5) | ❌ **open** — needs `ML/testdata/ovs_dump_flows.txt` for real entry granularity and `idle_timeout` |
| **Randomised flows reaching v2** (§5) | ✅ **fixed** (`2adaec5`): allowlist provenance gate at the monitor. 7 tests with real `demo_flows()` output and a verbatim captured OVS line; a denylist version and a deleted gate are both caught. `GS2_ENABLED` stays `false` while the operating points are provisional |
| **Poll failures looking like quiet traffic** (§5) | ✅ **fixed** (`37a4060`): `PollResult`, and demo substitution only on `failed`. The `failed` path is tested against a real closed port. ❌ `ok`/`ok_empty` tests blocked on `ovs_dump_flows.txt` |
| **Backend starts without a healthy inference service** (§9) | ✅ `4071505`. Unreachable at boot is non-fatal; a mismatched or malformed served contract is fatal (`ContractError`), with 7 tests |
| **Operating points** (§4) | ⚠️ **provisional.** `binary_gate` 0.5 sits on a fixed value appended to the search grid; run-to-run variation is unmeasured. Awaiting `grid_and_determinism_check.py` (run outside this repo). v2 reports `alerting_enabled: false` |
| **`Volumetric_Flood → meter` can fire** (§6) | ❌ **in doubt.** Test gated recall is 0.0 in `threshold_study.json`; on the 2b sample, 0.0% of correct predictions reach the 0.90 floor. §6 note awaits `vf_confidence_check.py` on the test split |
| **End-to-end on real OVS flows** | ❌ **blocked** — needs `ML/testdata/ovs_dump_flows.txt` |

The rows marked ❌ are still open. The plumbing is verified end to end in the
container. What remains unmeasured is the model's accuracy on flows from this
capture path, and until that is measured the v2 path must not be presented as a
detector.

# GraphSentinel — Measured Behaviour of the Installed Model

**Status:** authoritative. This file is the single source for every measured number
about the model. Other documents describe mechanics (`INTEGRATION.md`), the
timestamp investigation (`TIMESTAMP_FIX.md`) and how to run things (`RUNNING.md`);
where they mention a measurement they cite this file rather than restating it.

**Scope:** behaviour of the model and pipeline **as they exist in this codebase**.
No new experiments, with one exception made on 2026-10-04: §1.2, an offline
re-scoring of the v1 model. Every figure below is traceable to a committed artefact, named
at the end of its section. Nothing here is estimated, projected or rounded from
memory.

**Model under description:** epoch 18 checkpoint, retrained under the fixed
timestamp parse, installed in `ML/` after a container load check.
Weights sha256 matches `MANIFEST.json`. 654,851 parameters.

---

## 1. What the system does, and where the loop stops

```
Mininet / OVS  →  flow export  →  60 s windows  →  IP-as-node graph
      →  GATv2 edge + node heads  →  per-flow class + confidence
      →  rule generation (confidence-gated)  →  SDN translator  →  switch
      →  blockchain audit  →  React dashboard
```

Everything up to and including **per-flow class and confidence** is wired, tested
and verified inside the inference container.

### 1.1 Two detection paths, and this file measures only one

The backend runs **two** models. Everything in this file from §2 onward describes
the second. The first is the one that acts.

| | **v1 — in-process** | **v2 — inference service** |
|---|---|---|
| model | GraphSAGE, 7 features, two classes | GATv2, five classes, 654,851 parameters (§2) |
| when it runs | every monitor poll and every `POST /analyze`, always | in addition to v1, when `GS2_ENABLED` is true, and only on flows tagged `ovs` |
| starts by default under Compose | yes | yes since 2026-10-04 (`docker-compose.yml`); before that it needed a local override |
| creates incidents | yes | no |
| blocks hosts | yes — `SelfHealingEngine.block_ip` → `EnforcementAgent` | no |
| writes to the chain | yes | no |
| gating | one threshold (`THREAT_THRESHOLD`); severity bands hard-coded | the backend's policy, digest-echoed, per-class floors |
| dry-run | **no** | **yes**, and it refuses outside it |
| measured in this file | **no** | yes |

**The path that enforces is the path this file does not measure, and the path this
file measures enforces nothing.** Turning v2 on does not turn v1 off: the monitor
calls v1's `analyze_flows` on every poll and then, separately, offers the same
flows to v2 (`mininet_monitor/monitor.py`).

**v1 is not dry-run.** With `ENFORCEMENT_MODE=ovs` the agent sends each block to
`backend/scripts/enforcement_daemon.py`, which runs `ovs-ofctl add-flow` with
`priority=1000,ip,nw_src=<ip>,actions=drop` on the switch. Under Compose the
tracked `.env.docker` sets `ENFORCEMENT_MODE=simulated`, so the agent logs the
block and applies nothing; that setting, and the absence of Mininet on the
development machine, are the only reasons no drop rule was installed during the
runs behind this file. v1's incidents and chain writes happen in either mode.

Every statement below that says "dry-run", "no rule is installed" or "nothing
reaches a switch" is a statement about **v2 only**.

**Why v1 is kept, and what it is kept as.** v1 is the only thing in the system
that creates an incident, blocks a host or writes to the chain; v2 creates no
incidents and is dry-run by design. Remove v1 and the system demonstrates neither
self-healing nor a single write to the audit trail: the dashboard would show
scores and nothing else. v2 cannot take over yet, for a reason that has nothing
to do with its accuracy: it receives only flows tagged `data_source == "ovs"`, the
provenance gate refuses everything else and refuses whole batches, and this
machine has no Mininet. On the current setup v2 is offered no flow at all; it is
exercised only by sending the committed sample to the service directly (§1.3).
So v1 stays as the demonstration of the self-healing **mechanism** — detect →
block → chain → dashboard — and **no claim is made about its detection quality**
anywhere. §1.2 is why, and it is not "v1 is weak": on the six attacking hosts of
the one sample it has been scored on, with every feature present, 11 of the 21
sources it would block sent no attack flow — one wrong block for every right one
is not deployable unattended — and it reaches none of the Bot rows, which are
four fifths of the positive rows, so it cannot be presented as a detector.

**What would have to happen for v2 to replace it.** Future work, in this order.
None of it is attempted here, and none of it should be before step 1:

1. Mininet and OVS available, so the provenance gate admits real flows. The
   Mininet run is therefore not only the unverified link of §1.3; it is the
   prerequisite for v2 acting on anything.
2. v2's **binary** decision drives incident creation and the chain write. The
   binary edge figure (§4.1) supports that where the class head does not.
3. The class chooses only the *action*, and only above its floor. That part
   already holds: none of the 17,909 PortScan edges mislabelled BruteForce
   reaches 0.85 (§6).
4. `dry_run` stays true for the switch until the allowlist covers gateways, DNS
   and the controller and a rule has been validated against a controller.

What each object and field is called along the v1 path is mapped in
`NAMING_MAP.md`; the defects found in that path are in `AUDIT_2026-10-04.md`.

### 1.2 The one measurement of v1: what OVS's missing features cost

v1 reads seven features per flow. An OVS flow dump has no direction split and no
TCP flags, so on live traffic three of them are constants: `fwd_ratio` = 1.0,
`byte_asymmetry` = +1.0, `syn_ratio` = 0. The §7 sample was scored twice with the
installed v1 weights and the backend's own feature builder, once as the training
notebook built the features and once with those three forced to the constants:

| at the tracked 0.75 threshold | offline features | OVS constants |
|---|---:|---:|
| precision | 0.9487 | 0.7994 |
| recall | 0.1326 | 0.3094 |
| benign flows scored as attacks | 12 | 130 |
| sources over the threshold | 21 | 45 |
| of those, sources that sent no attack flow | 11 | 31 |

794 of 18,264 flows change side. **On OVS-shaped input v1 would block nearly three
times as many sources that sent no attack flow.** v1 must not be presented as a
detector on OVS traffic.

**Lost information, not a shifted operating point.** Recall rises while precision
falls, which one threshold cannot tell apart from a model that has simply become
more aggressive. Threshold-free, and at the precision the offline features had:

| | offline features | OVS constants |
|---|---:|---:|
| average precision, per flow (base rate 0.0917) | 0.6292 | 0.5737 |
| average precision, per source and window (1,900 rows, base rate 0.0332) | 0.3394 | 0.2967 |
| lowest flow threshold with precision ≥ 0.9487, and recall there | 0.6159 → 0.2790 | **none reaches it** |
| lowest source threshold with precision ≥ 0.4762, and recall there | 0.7798 → 0.1587 | 0.9815 → 0.0159 |

Average precision falls at both levels, and on OVS input **no threshold at all**
recovers the flow precision the offline features gave at 0.75. At the source
level, the unit the backend blocks, matching the offline precision costs nine
tenths of the recall (10 sources found against 1). Re-tuning the threshold does
not repair this; the three features carried information the model used. That
leaves retraining — on OVS-shaped features, or as a four-feature model — or
documenting the limit. There is no variance estimate: one sample, one run.

**What v1 does at the unit it blocks — on six attacking hosts.** Everything in
this paragraph rests on **n = 6**: only 6 of the 810 distinct sources in the
sample sent any attack flow, one of them (172.16.0.1) sent every slowloris,
PortScan and SSH-Patator flow, and the other five are the Bot hosts. These are
observations about six hosts, not estimates of a rate. What is blocked is a
(window, source) row; 63 of the 1,900 rows have a source that sent an attack flow
in that window, which is the 0.0332 base rate in the table, so the source-level
average precision of 0.3394 is about ten times chance. With every feature
present, at the tracked threshold, counted from the scores:

- **v1 is blind to one entire class.** None of the 50 Bot rows is over the
  threshold: 0 of 50, for all five hosts. Its ceiling is therefore the 13 rows of
  the one other attacker, 13 of 63, before any tuning.
- **Of the 13 rows it can reach it finds 10.** All 10 are that one host's.
- **It is wrong about as often as it is right.** Beside those 10 are 11 rows
  whose source sent no attack flow: 10 of 21, precision 0.4762, roughly one wrong
  block for every right one.

So: real ranking signal, most of what it is able to see found, precision that
cannot be deployed unattended, and four fifths of the positive rows invisible to
it. Lowering the threshold does not help (the last row of the table: 0.7798 finds
the same 10); the threshold is not wasting the signal, the signal stops. On
OVS-shaped input the picture is worse and less clean: 6 of that host's 13 rows,
and 8 Bot rows over the threshold although under one percent of Bot flows are,
so those rows are over it on the hosts' other traffic. One sample, one run, and
the ceiling caveat below applies to all of it.

**The offline column is a ceiling, not an estimate.** This is not v1's test set,
which is not in the repository; it is a small, 90.8%-benign slice that may overlap
v1's training rows. Overlap with training can only flatter a model, so on traffic
like this sample these are bounds, with every feature present and before OVS
removes three: v1 recalls **at most** 0.1326 of the attack flows at 0.75, and
**at least** 11 of the 21 sources it would block sent no attack flow. They are
bounds for this population, not for every dataset: v1's own held-out figures
(`ML/GraphSage-model/test_results.json`) were measured on a different split that
cannot be re-run here.

*Source: `ML/b08_ovs_constants.json`, written by `ML/b08_ovs_constants_check.py`.*

### 1.3 The v2 loop, in dry-run

**The v2 loop is closed in code, in dry-run** (commit `9a4b114`, 2026-10-04):

- the backend's validated `MitigationPolicy` is the **only** source of actions and
  floors. It is sent with every request to the inference service;
- the service's translator has **no table of its own**. The six-class table it
  used to carry (Volumetric_Flood and BruteForce never fired; PortScan `drop` at
  0.85; Botnet `drop_and_quarantine` at 0.80) is deleted. Without a policy no rule
  is made; a policy naming a class outside the live taxonomy is refused;
- every attack-classified flow that does not become a rule is returned as
  **withheld**, with its reason (`class_suppressed`, `below_floor`, `allowlisted`,
  `node_corroboration_absent`, `rule_cap`, `no_policy`);
- the service echoes the digest of the policy it applied, and the backend accepts
  rules only when that digest is its own and the service reports `dry_run`;
- no **v2** rule is installed: `SDNTranslator.install()` writes nothing in dry-run
  and refuses outside it, and no v2 rule reaches the enforcement agent or the
  self-healing engine. This says nothing about v1 (§1.1).

**On real flows, through the live container** (the §7 sample, 18,264 flows): 58 of
58 windows echoed the backend's policy digest; **12 rules admitted, all on
correctly classified flows** (8 BruteForce `drop_port`, 4 Volumetric_Flood
`meter`); 0 on benign or wrong-class flows; withheld: BruteForce 131 and
Volumetric_Flood 102 and PortScan 68 below floor, Botnet 1 suppressed. **No correct
PortScan prediction reached its 0.85 floor** (0 of 68; p50 0.631) — reported, not
adjusted.

**Unverified link: the backend's own ingestion path.** The result above was
obtained by sending the sample to the inference service directly, with the
backend's policy. It verifies the loop **from the inference service outward**. The
path a real flow takes — OVS → the backend's monitor → the provenance gate → the
v2 client → rules accepted by the backend — has **not been exercised end to end**
with the installed model: the monitor admits OVS flows only, and the machine these
measurements were made on has no Mininet. Each stage is covered by tests
(`backend/tests/test_v2_provenance_gate.py`, `backend/tests/test_v2_rule_wiring.py`);
the chain as a whole is not. It needs one Mininet run on Linux or WSL2
(`RUN_GUIDE.md` §11).

What may be said about mitigation: rule generation under a validated policy works
end to end **in dry-run**, verified at the service boundary. No v2 rule has been installed on a switch, the allowlist
does not yet cover gateways, DNS and the controller, and no rule has been validated
against a controller. "Self-healing" of live traffic by the measured model is
**not** demonstrated; the blocking the dashboard shows is v1's (§1.1).

*Source: `INTEGRATION.md` §6, `ML/live_rule_check.json`,
`ML/graphsentinel_v2/tests/test_sdn_policy.py`, `backend/tests/test_v2_rule_wiring.py`.*

---

## 2. The model

| | |
|---|---|
| architecture | `GATv2Conv` with `edge_dim`, jumping knowledge, LayerNorm, residual blocks |
| parameters | 654,851 |
| heads | edge head (flow, 5-way) + node head (host, 5-way, same output size as the edge head) |
| classes, in contract order | `BENIGN, Volumetric_Flood, PortScan, BruteForce, Botnet` |
| loss | focal, with effective-number class-balanced alpha; `edge_loss_weight = 2.0` |
| host memory | bounded three-tier (heavy / tail / subnet), `GRUCell`, LRU + TTL — **untrained** |
| trained on | torch 2.11.0+cu130, PyG 2.8.0.post1, Tesla T4 |
| inference on | Python 3.12.15, torch 2.4.0+cpu, PyG 2.5.0, pandas 2.3.3, numpy 2.2.6 |
| checkpoint | **epoch 18** of 30 run (40 configured, early stop at 30) |

The class order is a contract, not a convenience: `apply_taxonomy()` mutates
`CLASS_NAMES[:]` and `RAW_LABEL_MAP` in place, and `default_config()` resets them.

**The host memory is untrained.** It is v2's only; v1 has no memory at all. It
exists to carry per-host state **across** 60-second windows, so that a host that
scanned in one window is still known in the next: it is the temporal half of the
architecture. It is instantiated, bounded and exercised, but no training signal
reaches it, so its `GRUCell` weights are at initialisation and what it injects is
initialisation-valued state. It must not be described as learned state.

What its ablation supports (§8), and no more:

> The host memory is untrained. Disabling it changes macro F1 by +0.0188, with no
> variance estimate, so the measurement does not establish that the memory harms
> the model — only that it does not help it. Most of the larger pre-fix figure
> (+0.1270) was the timestamp defect.

The memory stays on. Every figure in this file was measured with it on; turning
it off would invalidate them for a change the probe cannot justify.

**Graph construction.** IP-as-node, flow-as-edge, 60-second non-overlapping
windows. A window needs `min_edges_per_graph = 8` to become a graph; windows above
`max_edges_per_graph = 200,000` are subsampled. Reverse mirror edges are added and
masked by `real_edge_mask`, so mirror edges never enter a loss or a metric.

**Container load, verified.** Weights sha256 matches the manifest; 654,851
parameters load; class order and `dry_run` correct; a fixed 40-flow window scores
40 of 40 with probabilities equal to the local torch 2.13 run **to six decimals**;
the service is healthy in ~45 s, `/health` returns 200, `/contract` serves 2.0.0.

*Source: `model_card.json`, `MANIFEST.json`, `PROVENANCE.json`,
`ML/retrain_logs/container_load_output.txt` (output of `ML/container_load_check.py`).*

---

## 3. The data, and the defect found in it

Dataset: CICIDS2017, `TrafficLabelling_` variant — 85 columns, retains Source IP,
Destination IP and Timestamp. Eight files, **2,830,743 rows**.

### 3.1 The 12-hour clock defect

**Measured over all 2,830,743 rows: no file contains any hour ≥ 13, and no file
contains an AM/PM token.** Six of the eight contain hours 1–5, which on a
business-hours capture can only be afternoon traffic. The two morning-only files
(Friday-Morning, Thursday-Morning-WebAttacks) hold hours 8–12, which read
identically on both clocks; they are **format-indeterminate**, and the fix
correctly moves 0 rows in them.

Rows placed at the wrong hour by the original parse:

| | rows | share |
|---|---:|---:|
| training files | **960,315** of 1,841,857 | **52.1%** |
| all eight files | **1,471,716** of 2,830,743 | **52.0%** |

Two independent confirmations of the capture day. Friday's three files tile with a
one-minute handoff, and three other days close to a contiguous working day:

| capture | after the fix | under the old parse |
|---|---|---|
| Friday-Morning | 08:59 → 12:59 | 08:59 → 12:59 |
| Friday-Afternoon-PortScan | 13:00 → 15:29 | 01:00 → 03:29 |
| Friday-Afternoon-DDos | 15:30 → 17:02 | 03:30 → 05:02 |
| Monday | 08:55:58 → 17:01:34 | 01:00:01 → 12:59:58 |
| Tuesday | 08:53 → 17:00 | 01:00 → 12:59 |
| Wednesday | 08:42 → 17:10 | 01:00 → 12:59 |

Monday, Tuesday and Wednesday each hold hours `{1–5, 8–12}` — ten hours with a
hole at 6 and 7. Shifting `{1–5}` by twelve gives `{13–17}`, which abuts `{8–12}`
exactly. A three-hour hole from 05:00 to 08:4x in a working-hours capture is not a
property real captures have; three days closing to contiguous 08:4x–17:0x is not a
coincidence another reading survives. Neither argument depends on the `pm_hours`
assumption.

### 3.2 The fix, and the limits of its assumption

Per-day rule, `cfg.data.fix_12h_clock`, `cfg.data.pm_hours = [1, 7]`, cache suffix
`_pm1-7`. **Hours 6 and 7 never occur in any file**, so `[1, 5]` would produce an
identical result and the window's two widest entries are never exercised. The
business-hours assumption is therefore not load-bearing on this dataset.

The MIXED check runs **per file** while the pipeline parses the **pooled** column.
The two coincide here because the global count of hours ≥ 13 is zero. They would
not coincide in general.

Monday's first and last stamps carry seconds (`01:00:01`, `12:59:58`); the
other seven files' first and last stamps are on the minute. That is what the
audit measured — two stamps per file, not every row; a per-file count of
distinct second values is queued for the next pass. It matters in §5.3, whose
argument depends on the Friday files being minute-only; Monday is the contrast
showing the format is not uniform.

*Source: `ML/timestamp_audit.json`; the verdict, with its recorded basis (parse
digest, all eight CSV names and sizes, bundle commit), in `ML/PROVENANCE.json`
under `stages.audit_gate.verdict`, recorded unchanged from the verdict file by
the gate; `TIMESTAMP_FIX.md`. Cell B re-checks the basis on every run.*

---

## 4. Measured performance

All figures on the episode-split test set unless stated. **226,342 test edges**
(the epoch-31 model's test split had 227,325).

### 4.1 Flow (edge) classification

| | pre-fix model | **installed model** |
|---|---:|---:|
| macro F1, all 5 classes | 0.7042 | **0.4441** |
| macro F1, classes present in test | 0.7042 (5) | 0.5551 (4) |
| **binary attack/benign F1** | 0.9974 | **0.9961** |

**Binary detection moved −0.0013** (0.9974 → 0.9961) through everything that
changed the class head. **0.4441 is the comparison figure** for the class head. 0.5551 is a mean over four classes, because
the test graphs contain zero Botnet edges; it is not comparable to a five-class
mean and must not be set beside it.

| class | pre-fix | installed | test edges |
|---|---:|---:|---:|
| BENIGN | 0.9992 | 0.9988 | 174,421 |
| Volumetric_Flood | 0.9910 | 0.9617 | 27,191 |
| PortScan | 0.9800 | **0.2598** | 23,812 |
| BruteForce | 0.5508 | **0.0000** | 918 |
| Botnet | 0.0000 | *no test edges* | 0 |

**The two Botnet zeros mean different things.** Pre-fix, 0.0000 was a measurement
over 266 edges. Post-fix there are no Botnet test edges at all, so the class is
unevaluable on this split — recorded as "no test edges", never as 0.0. The sample
in §7 does evaluate it: **0 of 168 correct.**

### 4.2 Host (node) classification

Binary F1 **0.4475**, against 0.1407 pre-fix. The node head is five-way; its
binary F1 is computed as for the edge head (`evaluate.multiclass_metrics`):
a host counts as predicted attack when its **argmax class is not BENIGN**, and as
truly attack when its label is not BENIGN. Five-class node macro F1 is 0.3045. Measured on a test split whose
composition changed (§5.1), so it carries the same non-comparability caveat as
every other cross-run figure. 0.4475 is not a number to lead with in either
direction.

### 4.3 Window-level alerting

Installed model only:

| ≥ 5 flows / 60 s | installed |
|---|---:|
| test precision | 0.9688 |
| test recall | 0.8857 |
| test F1 | 0.9254 |
| Monday false-alert windows | 2 of 486 |
| Monday flow-level false positives | 60 |
| Monday flow FPR | 0.000120 |

**These are not comparable with the epoch-31 model's**, which recorded test
precision 1.0000, recall 0.3125, F1 0.4762, and on Monday 0 false-alert windows,
1 flow-level false positive, FPR 0.0000020. Pre-fix, 54 of the 80 test attack
windows contained only Botnet flows and the model's Botnet F1 was 0.0000, so those
windows were unalertable by construction: the gate missed exactly 266 attack flows
and there were exactly 266 Botnet test edges. Excluding them gives 25/26 = 0.96
before against 31/35 = 0.89 after — but the remaining populations (26 of 265
windows, against 35 of 207) are not comparable either. **Window-level alerting
supports no claim in either direction**, and the only direction it points is down.

### 4.4 Training behaviour

Training loss reaches 0.0004 by epoch 30 while validation edge-F1 stalls near
0.53; best validation is **epoch 18** at 0.5565, against a pre-fix best of 0.7568
at epoch 31. Early stop fired at 30 of 40 configured. *Interpretation:* the model memorises
the training windows — the evidence is training loss 0.0004 while validation
stalls near 0.53, with the best validation at epoch 18. The run is valid; the write-up cannot present 40 configured
epochs without saying the model stopped learning generalisable structure at ~18.

*Source: installed model — `ML/test_report.json`,
`ML/retrain_logs/training_log.csv`, `ML/threshold_window_level.csv`,
`ML/threshold_flow_level.csv`. Epoch-31 figures — the same files under
`ML/prefix_epoch31/`.*

---

## 5. Where the model fails, and why

### 5.1 The test task changed, and it is now the harder, correct one

Pre-registered prediction, printed before the measurement and stored in
`split_composition.json`:

> If the mechanism holds, the pre-fix share of test attack flows sharing a window
> with benign traffic is LOW and the post-fix share is SUBSTANTIALLY HIGHER. If
> both shares are similar, the mechanism is wrong.

Measured, weighted by rows:

| test attack flows sharing a 60 s window with benign traffic | old parse | fixed parse |
|---|---:|---:|
| | **266 of 52,062 — 0.51%** | **51,003 of 52,187 — 97.73%** |

And validation is the mirror image: **98.45% → 0.52%.**

*The hypothesis this measurement tests:* a 60-second window containing only
attack flows may be classifiable from structure alone — fan-out, degree, density —
without reading a flow feature, while a mixed window forces per-edge
discrimination. The measurement establishes that the composition changed; that the
pre-fix test task was therefore easier is the inference it supports, not a
separate measurement. **This is not a duplication leak**, and must not be
described as one; it is a change in window composition, and the evidence for it is
the pre-registered measurement above.

Three independent confirmations:

- the pooled BENIGN test tail moved from Friday-Morning (175,271 rows,
  08:59→12:59) to Friday-Afternoon (174,421 rows, 13:53→17:02), exactly as the
  mechanism requires;
- Botnet's 266 test rows are **identical under both parses** — Friday-Morning
  moves 0 rows — yet went from `graphable 100%` to `graphable 0%`, because the
  morning benign traffic that lifted their windows over the 8-flow floor left the
  split. That is why Botnet became unevaluable;
- `split_composition` reproduces the retrain's test edge counts exactly on all
  five classes: 174,421 / 27,191 / 23,812 / 918 / 0.

### 5.2 A second mechanism: the fix reorders three of the eight files

A 12-hour shift preserves within-file order **only for the three afternoon-only
files**. Monday, Tuesday and Wednesday contain both the shifted block `{1–5}` and
the unshifted block `{8–12}`, so sorted by timestamp the two blocks swap places.

The per-class split totals show it. A timestamp shift cannot create or destroy
rows, so the invariant classes are the control:

| class | old total | fixed total | delta | where its cuts fall |
|---|---:|---:|---:|---|
| PortScan | 158,746 | 158,746 | 0 | inside Friday-PM-PortScan, a file the fix does not reorder (afternoon-only: every row shifts equally) |
| Volumetric_Flood | 222,350 | 222,350 | 0 | train→val between days (Wednesday → Friday); val→test inside Friday-PM-DDos, afternoon-only, not reordered |
| Botnet | 1,526 | 1,526 | 0 | inside Friday-Morning, which the fix leaves untouched (0 rows moved) |
| BENIGN | 1,167,410 | 1,161,608 | −5,802 | cut over the pooled timeline, where the fix swaps Friday's morning and afternoon blocks; under the old parse the train→val cut fell inside Friday-PM-PortScan's benign rows |
| BruteForce | 6,508 | 6,868 | +360 | inside Tuesday, a file the fix reorders |

The net −5,442 is accounted for exactly by the split's dead zone, which removes
56,253 rows under the old parse and 61,695 under the fixed one.

**Under the old parse those two splits were not temporally ordered.** BruteForce
trained on rows stamped 02:09 — real 14:09 — while being tested on real
10:10–10:30: the model trained on the future and was tested on the past, inside
one campaign. BENIGN had the same violation (train's last row real 13:39, test
08:59–12:59). BruteForce fell 0.5508 → 0.0000; BENIGN, being easy either way, went
0.9992 → 0.9988.

So the fix acted through **more than one mechanism**. Measured: the test
windows' composition changed (§5.1), BruteForce's old split was out of time order,
and Botnet's test windows fell below the 8-flow floor. Which mechanism drives
PortScan's collapse is **open**: composition (§5.1) and contamination of its
validation split (§5.3) are both candidates. The next Colab pass settles it by
scoring test PortScan at the minute it shares with validation against the minutes
after it. BENIGN's F1 barely moved under either parse.

### 5.3 PortScan's validation score is not independent of training

A 300-second dead zone sits either side of each class cut, retrying at 150 s and
then at 0 s when it cannot fit. Measured separation between splits:

| class | train → val | val → test |
|---|---:|---:|
| BENIGN | 720 s | 720 s |
| Botnet | 720 s | 780 s |
| BruteForce | 720 s | 720 s |
| Volumetric_Flood | 178,560 s | **360 s** (150 s retry) |
| **PortScan** | **0 s** | **0 s** (0 s retry) |

**PortScan: train ends 14:55, validation is entirely 14:55, test begins 14:55.**
The minute 14:55 is a graph window in all three splits.

The cause is not a bug in the dead zone. The Friday files carry minute-resolution
timestamps and a port scan puts 23,812 rows on a single timestamp value, so a
rank-based cut lands inside one timestamp and a time-based dead zone can only
remove that whole block or none of it. **The defect is identical under the old
parse**, so it is a standing splitter property and does not disturb the pre/post
comparison — but it means PortScan's validation figures have never been
independent of training, in either run. Validation is where the checkpoint was
chosen and every operating point was fitted.

Correct design: cut on window boundaries, not row ranks. Recorded as future work;
changing it invalidates every number in this file.

### 5.4 PortScan and BruteForce are mutually confused

| | |
|---|---|
| true PortScan → BruteForce | 17,909 of 23,812 (75%) |
| true BruteForce → PortScan | 904 of 918 (98%) on test; 581 of 582 on validation |
| Botnet, on the §7 sample | 0 of 168 correct |

Validation PortScan is 99.6% above its floor; test PortScan is 0.0%. Same class,
same model, windows minutes apart.

**This is one finding, not two.** Neither 0.2598 nor 0.0000 is a property of the
model: the model cannot separate these two classes, and which one appears to
collapse depends on the window population of the split. Binary detection is
unaffected — F1 0.9961.

### 5.5 Episode splitting never engages

Under the fixed parse, episode detection finds BruteForce 3, Volumetric_Flood 11,
PortScan 8 — all rejected as *"sizes too uneven"* — and Botnet 2, taken as a
chronological cut. All four classes fall back to rank cuts. **These counts are
console output from the 2026-10-03 training run, not a committed artefact**; from
the next pass `split_composition` records the split's own episode lines under both
parses. No claim is made about the pre-fix counts.

*Source: §5.1–§5.4: `ML/split_composition.json`,
`ML/retrain_logs/split_composition_output.txt`. §5.5: the 2026-10-03 Colab console
(not committed).*

---

## 6. Operating points, and what the policy would enforce

These are the backend policy's floors, which the translator applies (§1), in
dry-run. The figures below are offline, on the test split.

| class | fitted floor | policy floor | test precision | test recall |
|---|---:|---:|---:|---:|
| Volumetric_Flood | 0.4571 | 0.90 | 0.9804 | 1.0000 |
| PortScan | 0.8706 | 0.85 | 0.0000 | 0.0000 |
| BruteForce | **cannot be fitted** — 0 predicted, 582 true in validation | 0.85 | — | — |
| Botnet | — | **1.01** | — | — |

A floor of **1.01 is a disabled rule**, not a threshold. Confidence cannot exceed
1.0. Say so in words wherever it appears.

**§6's standing finding is resolved for the model.** "Volumetric_Flood → meter can
never fire" is false: **22,268 of 27,191** correct VF predictions (81.9%) clear
0.90, p50 0.938.

Rules the per-class floors would admit on the test set. These are **upper bounds**:
the translator also requires node corroboration, which can only remove rules, and
Part B counts the edge head alone.

| | at most |
|---|---:|
| correct class, correct action | 22,268 — all Volumetric_Flood |
| wrong class, on a real attack | 118 — PortScan rule on true BruteForce |
| wrong class, on benign traffic | **2** of 174,421 benign flows — **1.15 × 10⁻⁵** |
| correct PortScan rules | **0** — 0 of 3,735 correct predictions clear 0.85 |
| correct BruteForce rules | **0** — true BruteForce is never predicted BruteForce |

The 17,909 PortScan edges mislabelled BruteForce have p95 **0.623**; **none**
reaches 0.85. The class head is unreliable and the confidence floors absorb almost
all of that unreliability. **On the test split, Volumetric_Flood is the only class
with a correct end-to-end path.** On the §7 sample, through the live service, 8
BruteForce `drop_port` rules were admitted on true BruteForce flows as well (with 4
Volumetric_Flood rules; §1) — 8 rules on one small slice, stated with its n, not
generalised. Binary detection still alerts on everything; what the floors
suppress is class-specific enforcement, not detection.

No floor, action or behaviour was changed to produce any figure in this section.

*Source: `ML/threshold_study.json`, `ML/split_composition.json` Part B,
`mitigation_policy.py`.*

---

## 7. Live-path cost

Measured on a committed sample: **18,264 rows, 58 windows, 52 of them mixed**,
drawn from four files in window space after cleaning. The sample is **90.8%
BENIGN** (16,590 rows); PortScan is 196 rows and Botnet 168.

**Not comparable to §4** — a small contiguous slice, a different population. The
deltas are the output. Common-flows table, macro over five classes:

| variant | macro F1 | vs baseline | what it models |
|---|---:|---:|---|
| baseline | 0.6811 | — | offline features, one submission per flow |
| degraded | 0.6578 | −0.0232 | features the live path cannot supply |
| recounted | 0.6772 | −0.0038 | the 5 s poll resubmitting each flow |
| **live** | **0.6567** | **−0.0243** | both — what would actually ship |

**The macro delta is almost entirely PortScan**: baseline → live, BENIGN
0.9940→0.9941, VF 0.9670→0.9568, BruteForce 0.9234→0.9344 (*up*), **PortScan
0.5208→0.3984 (−0.1224)**. "Small cost" is true at macro level and conceals −0.12
on the one class that already fails its gate.

Three caveats, all of which make these numbers optimistic:

- `IDLE_TIMEOUT` is 0, so every re-counting figure is the **best case**. Real
  flow-table entries linger past the flow with frozen counters and a growing
  duration.
- A sub-poll flow is submitted once here, so short-lived classes — PortScan above
  all — are **not re-counted at all**. Their small delta is not resilience.
- Zeroing all 20 edge features changes the argmax on 41 of 18,264 edges (0.22%),
  but on a 91%-benign slice that is not a measure of feature dependence. The
  probes in §8 are the instrument for that.

*Source: `ML/phase2b_results.json`, `ML/phase2b_sensitivity.json`,
`ML/testdata/cicids2017_sample.csv`; "52 of 58 mixed" from
`ML/retrain_logs/sample_output.txt`.*

---

## 8. Probes

| probe | pre-fix | installed |
|---|---:|---:|
| zero all 20 edge features | **+0.0956** | **−0.0265** |
| host memory off | +0.1270 | +0.0188 |
| largest leave-one-out removal gain | +0.0723 (`log_total_bytes`) | +0.0192 |

**The edge-feature probe changed sign.** The pre-fix model scored *better* with its
flow features zeroed; the installed model scores worse. Quote the split-agreement
verdict with it: `no_edge_feat` is val **+0.0397** / test **−0.0265**, i.e.
**split-specific**. The honest statement is that the pre-fix direction does not
survive the fix, not that the effect cleanly reversed.

**The host memory does not help; the probe does not show that it harms.**
+0.1270 → +0.0188: most of that headline was the clock, and the residual is
consistent with memory being untrained. Like leave-one-out below, this probe has
no variance estimate (§2 has the sentence to quote).

**On leave-one-out, be careful.** "Two misleading features became zero" is a
**reporting-threshold artefact** — the probe only flags gains above +0.02, and
post-fix the largest is +0.0192 with nine features weakly positive. The defensible
claim is twofold:

> The two features the earlier finding named now **degrade** macro-F1 when
> removed (−0.0158 and −0.0024), where before they improved it. The largest
> removal-gain of any feature fell from +0.0723 to +0.0192. The probe has no
> variance estimate, so effects of this size cannot be distinguished from
> run-to-run noise; the claim rests on the direction and on the disappearance of
> the large effect, not on the individual values.

The `config.py` comment recommending those two features be dropped is marked
superseded.

*Source: `ML/probes.json` (installed figures, and the epoch-31 references for the
first two rows), `ML/retrain_logs/probes_information_output.txt`,
`ML/retrain_logs/probes_confirm_output.txt`. The pre-fix +0.0723 is in the saved
output of `ML/GraphSentinel_Training.ipynb`.*

---

## 9. Limitations, enumerated

1. **The dry-run guarantee is v2's only; the path that blocks hosts is unmeasured**
   (§1.1). v1 — a two-class GraphSAGE over 7 features — creates the incidents,
   blocks the hosts and writes the chain records, and with `ENFORCEMENT_MODE=ovs`
   installs real drop rules. The only figures in this file that describe it are
   §1.2's, and they are unfavourable: on OVS-shaped input it puts 31 sources that
   sent no attack flow over its threshold, against 11 with full features.
2. **Both models are scored on graph sizes they were not trained on.** v1 trained
   on 500-flow windows and at inference scores whatever one poll returns, down to
   a single flow with no edges (`backend/app/services/inference_service.py`). v2
   needs `min_edges_per_graph = 8`, and that floor is what removed Botnet's test
   set (§5.1). One defect class, two models; its effect on v1 is not measured.
3. **v2 mitigation is dry-run only** (§1). Rules are generated under the validated
   policy and none is installed; the allowlist does not cover gateways, DNS or the
   controller, and no rule has been validated against a controller.
4. **PortScan's floor is unreachable** on the live sample (0 of 68 correct
   predictions reach 0.85) and on the test split (0 of 3,735): its `drop` action
   never fires.
5. **The host memory is untrained** (§2). Not learned state.
6. **PortScan's validation is contaminated** — one graph window appears in train,
   validation and test (§5.3). Validation chose the checkpoint and fitted every
   operating point.
7. **Validation and test have opposite window composition** — 98.45%/0.52% against
   0.51%/97.73% (§5.1). Fitted operating points do not transfer, and this is why.
8. **PortScan and BruteForce are not separable** by this model (§5.4). Their
   per-class F1s are properties of the split, not the model.
9. **Botnet is unevaluable on the test split** and scores 0 of 168 on the sample.
10. **Episode splitting never engages** under the fixed parse (§5.5); all four
   classes use rank cuts. The counts behind this are not yet a committed artefact.
11. **Cross-run comparisons are not controlled.** The fix changed which rows each
   split holds (§5.2), so every pre/post figure describes two different test tasks.
   Only §5.1's pre-registered measurement is a clean comparison.
12. **Window-level alerting supports no claim in either direction** (§4.3).
13. **The model memorises** — best epoch 18, training loss 0.0004 (§4.4).
14. **Live-path figures are optimistic** on three counts (§7).
15. **Calibration and latency have not been re-measured** for the installed model.
16. **The two morning-only CSVs are format-indeterminate** (§3.1); the fix's
    correctness on them is inferred from its behaviour, which is to leave them alone.
17. **`pm_hours = [1, 7]` is unexercised at its edges** (§3.2).
18. **The MIXED check is per file, the pipeline is pooled** (§3.2); they coincide
    only because no hour ≥ 13 exists anywhere.
19. **The host memory has never run in the condition it was designed for.** Its
    purpose is continuity across windows for the same hosts, which needs a
    sustained stream of flows from a stable host population. Every measurement
    here was made on offline CICIDS2017 windows or on the 58-window committed
    sample, and in the live path the provenance gate has never admitted a flow
    (§1.1). So the §8 ablation is not the last word on the memory: it measures an
    untrained memory on input that gives it nothing to remember.
20. **Neither model detects Botnet traffic.** On the one sample both have been
    run against (§7), v2 classifies 0 of 168 Botnet edges correctly and has no
    Botnet edges in its test split to say otherwise (item 9); v1, with every
    feature present, puts 0 of 50 Bot rows over its threshold, and those are
    most of the 63 positive rows of its source-level evaluation (§1.2).
    Two models, two architectures, one blind spot. The sample has five Bot hosts,
    so this is an observation about them, not a rate; but it is a measured gap,
    which makes it the best-evidenced item of future work the project has.

---

## 10. What may and may not be claimed

**May be claimed, with the cited figure:**

- Reliable binary attack/benign discrimination at the flow level — **edge binary
  F1 0.9961**, which moved only **−0.0013** (from 0.9974) through the correction
  that took the five-class macro F1 from 0.7042 to 0.4441. This is the strongest
  claim the project has.
- A reproducible, measured defect in CICIDS2017's `TrafficLabelling_` timestamps
  affecting **52.0% of 2,830,743 rows**, with an independently-confirmed capture-day
  reconstruction.
- That the defect materially changed what the test set measured, demonstrated by a
  **pre-registered** measurement: test attack flows sharing a window with benign
  traffic, **0.51% → 97.73%**.
- That the installed model depends on its flow features where the pre-fix model did
  not — with §8's split-specificity and variance caveats attached.
- Rule generation under a validated policy, in **dry-run**, verified at the
  inference-service boundary and not through the backend's monitor (§1): on the
  live sample, 12 rules, all on correctly classified flows (8 BruteForce, 4
  Volumetric_Flood). On the test split, offline, Volumetric_Flood is the one class
  with a correct path, at a false-action ceiling of **2 in 174,421 benign flows**.

**Must not be claimed:**

- That the loop has been demonstrated end to end. It is verified from the inference
  service outward; the backend's ingestion path from a real OVS flow to an accepted
  rule is a **named unverified link** (§1) until a Mininet run exercises it.
- Zero-day detection. Nothing in this project measures unseen attack families.
- Real-time performance. Latency has not been measured for the installed model.
- Production readiness.
- Self-healing or mitigation of live traffic by the model measured here. v2's
  rules are dry-run; none has been installed or validated against a controller
  (§1). The blocking the system performs is v1's, which this file does not
  measure (§1.1).
- "Dry-run throughout", or "no rule has ever been installed", as a statement about
  the system. It is true of v2 only.
- Any improvement over the pre-fix model. The honest summary is that the numbers
  **fell** — macro F1 0.7042 → 0.4441 — and that the fall is the correction of a
  measurement, not a regression in the system.
- Host-level classification as a working capability. Node binary F1 is 0.4475.
- Flow classification as host classification. They are different heads with
  different numbers.
- Any per-class F1 for PortScan or BruteForce as a model property (§5.4).
- Detection of Botnet traffic, by either model, or "a five-class detector"
  without qualification. The taxonomy includes a class that nothing in this
  project has detected (§9 item 20).

The contribution this codebase supports is **the audit and the honest
re-measurement**: a defect found at full scale, a pre-registered test of its
mechanism, and a corrected set of numbers that are lower than the ones they
replace.

---

## 11. Reproduction

1. Cell A — the timestamp audit. Must run first whenever `preprocess.py` changes;
   the verdict's recorded basis is the parse digest plus CSV names and sizes, and
   Cell B checks it every run.
2. Cell B — graphs, training, threshold study, probes, `split_composition`, sample,
   Phase 2b, package. Completed stages are skipped by name, not position.
3. Container load before installing any weights: sha256 against the manifest,
   parameter count, class order, `dry_run`, and a fixed window scored against a
   local run.
4. Unzip the result at the repository root; every file lands at its own path.
   `.gitattributes` pins `-text` on every digest-bearing artefact, including the
   moved pre-fix files, the sample and the retrain logs.

Suites at time of writing, on branch `fix/audit-p0-p1`: **ML 167 passed; backend
244 passed, 3 skipped; Hardhat 25 passing.** The backend figure was 233 passed
before the audit fixes and was first produced with `web3` 7.16.0 installed against
a pin of 7.4.0; the pin is now what is installed, and the count is the same under
both (`AUDIT_2026-10-04.md` §1.7). How to
start the system and verify it in one command: `RUN_GUIDE.md` (§6,
`python ML/verify_stack.py`).

---

## 12. Provenance

Every installed file matches its digest in `PROVENANCE.json`. The superseded
epoch-31 model lives in `ML/prefix_epoch31/` and Phase 2b run 1 in
`ML/phase2b_runs/`; both are **evidence for §4 and §5 and must not be deleted.**

`report/main.tex` compiles to 74 pages under Tectonic 0.15 with biber 2.17.
`reference.bib` is not in the repository, so 20 citations resolve as undefined
until it is added.

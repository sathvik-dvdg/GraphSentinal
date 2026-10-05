# GraphSentinel — Implementation Verification and Presentation Readiness Audit

Audit only. No source, model, configuration or script was changed to produce this
report. Branch `fix/audit-p0-p1` at commit `ae34631`, audited 2026-10-05.

**How to read the evidence.** Every conclusion rests on one of three things, and
each is labelled:

- **CODE** — read from the source at the cited file and line.
- **RUN** — measured by executing the code: the test suites run for this audit,
  and the three live Mininet/OVS runs of 2026-10-04/05, whose raw outputs are in
  `ML/retrain_logs/live_loop*/` and `ML/live_loop_run*.json`. Two SQLite
  databases from those runs (`C:\dev\gs_live\live_loop2.db`, `live_loop3.db`,
  not tracked) were read for this audit to see what v1 did.
- **UNVERIFIED** — could not be established from code or execution.

Documentation was not used as evidence. Where documentation and code disagree,
it is flagged.

---

## 1. Executive Summary

**Can I safely use the existing two trained models with the Mininet simulation
for my presentation?**

```text
YES — WITH SPECIFIC CHANGES
```

and only as a demonstration of the **mechanism**, not of detection quality.

What works, verified by execution: real Mininet traffic through a real OVS
switch reaches the backend, both models score it, v1 creates incidents and
blocks (simulated), v2 proposes rules in dry-run, and the dashboard is fed.

What does not hold, verified by execution:

1. **v1 blocks benign hosts on live traffic.** In two live runs it blocked 7 of
   10 and 9 of 10 hosts. Five of them were blocked during a phase that contained
   only benign pings and web fetches, within about 45 seconds.
2. **v2 labels half of benign traffic as attacks on live traffic**, and the rules
   it proposes land mostly on benign web fetches.
3. **The architecture in the brief is not what the code implements.** There is
   no model routing, no decision layer that combines the models, no DoS Hulk
   attack script, and no demo controller.
4. **A scripted five-attack sequence cannot work as written**: three of the four
   scripts attack from the same host, and a host that is already blocked
   produces no further incident.

The minimum changes are in section 15. The claims that are and are not safe are
in section 18, and that section matters more than any other.

---

## 2. Current Architecture (as implemented)

```text
Mininet hosts ── traffic ──► OVS switch s1  (ovs-testcontroller installs one
                                             exact-match entry per conversation)
                                   │
        enforcement_daemon.py: `sudo ovs-ofctl dump-flows s1`   (TCP 127.0.0.1:50051)
                                   │
        flow_parser._parse_output  → list of flows, each tagged data_source="ovs"
                                   │
        MininetMonitor._run, every 5 s — the WHOLE table, every poll
                 │                                   │
                 ▼                                   ▼
   v1 path (always)                         v2 path (if GS2_ENABLED and all flows "ovs")
   graph_builder: 1 node per FLOW,          flow_mapping.map_flow → inference service
     7 features, chain edges                  (separate process): 60 s windows,
   GraphSAGE → P(malicious) per flow          IP-as-node graph, GATv2 edge head, 5 classes
   max per source IP                        SDNTranslator + backend policy → rules
                 │                                   │
   score ≥ THREAT_THRESHOLD (0.75)          DRY RUN: logged, counted, discarded
                 │                          (no incident, no block, no chain write,
   infer_attack_type(): a port/volume        nothing shown on the dashboard)
     HEURISTIC, not a model output
                 │
   Incident row → SelfHealingEngine.block_ip → EnforcementAgent
                 │        (simulated: log only | ovs: `ovs-ofctl add-flow ... drop`)
   BlockchainAdapter.store_incident → Ganache contract (if reachable)
                 │
   Socket.IO: graph_update / alert / healing_triggered  +  REST polling
                 │
   React dashboard (shows v1's incidents, blocks and chain records only)
```

The two models do not feed a shared decision. They run side by side on the same
poll; v1's result drives everything the user sees, v2's result is logged.

---

## 3. Intended vs Actual Architecture

| Component | Intended | Actual | Status |
|---|---|---|---|
| Mininet simulation | Attack scripts generate traffic | 4 scripts exist; each builds and tears down its own topology | 🟠 see 6, 13 |
| OVS flows | Collected | Yes, via the daemon (CODE, RUN) | 🟢 |
| Flow collection | Polled | Every 5 s, whole table each time (CODE `monitor.py:323`) | 🟢 with a cost |
| Feature extraction | Model features | v1: 7 per flow, 3 degenerate on OVS; v2: 10 of 20 filled | 🟠 |
| Graph builder | One | Two different ones, one per model | 🟡 |
| GraphSAGE v1 | Binary detection | Binary; runs always; **it is the model that acts** | 🟢 runs / 🔴 quality |
| GATv2 v2 | Multi-class detection | Runs, dry-run only, output shown nowhere in the UI | 🟠 |
| Model selection | Per attack | **Not implemented** | 🔴 MODEL ROUTING REQUIRED |
| Decision layer | Combines both models | **Does not exist.** v1 threshold only | 🔴 |
| Alert | Yes | v1 only (`alert` socket event) | 🟢 |
| Mitigation | Block / isolate | v1 only; simulated by default, real OVS drop rule in `ovs` mode | 🟢 |
| Audit / blockchain | Every incident | v1 incidents, if Ganache is reachable; else `retry` | 🟡 |
| Dashboard | Shows detections | Shows v1 only; attack type is a heuristic label | 🟠 |
| DoS Hulk attack | Script | **No script exists** | 🔴 NOT IMPLEMENTED |
| Demo controller | Runs the sequence | **Does not exist** | 🔴 NOT IMPLEMENTED |

---

## 4. Model Inventory

### v1 — GraphSAGE

| | |
|---|---|
| Checkpoint | `ML/GraphSage-model/graphsage_weights.pt` (CODE `inference_service.py:93`) |
| Architecture | 3 SAGE layers, 256 hidden, mean aggregation, 2 outputs (CODE `inference_service.py:87-91`; `ML/GraphSage-model/config.json`) |
| Size | 138,244 values in the state dict, batch-norm buffers included (RUN) |
| Input | 7 features per **flow**; one graph node per flow; edges chain consecutive flows and flows sharing a destination port (CODE `graph_builder.py:44-78`, `:81-96`) |
| Scaling | fixed mean/std from `ML/GraphSage-model/inference_stats.pt` (CODE `graph_builder.py:107-151`) |
| Output | P(malicious) per flow; the maximum per source IP is the source's score |
| Classes | 2: benign, malicious. **No attack type.** |
| Inference path | in the backend process, every poll and every `POST /analyze` |
| Evaluation evidence | `ML/GraphSage-model/test_results.json`: accuracy 0.9957, weighted F1 0.9957, AUC 0.9975. **The code that produced it is not in the repository** (see below), so the split and the method cannot be checked. |

**🟠 v1's training code is not in the repository.** Both notebooks in `ML/` are
v2 training notebooks. v1's training feature schema, preprocessing and graph
construction therefore **cannot be compared with its inference code**. Training
and inference parity for v1 is **UNVERIFIED**.

### v2 — GATv2

| | |
|---|---|
| Checkpoint | `ML/weights.pt`, `ML/model.ts`; digest pinned in `ML/MANIFEST.json` |
| Architecture | GATv2 with edge features, edge head and node head (CODE `ML/graphsentinel_v2/graphsentinel/models/net.py`) |
| Size | 654,851 parameters (`ML/model_card.json`; checked on load by `ML/verify_stack.py`) |
| Input | IP-as-node graph per 60 s window; 20 edge features, 16 node features (`ML/model_card.json` → `inputs`) |
| Scaling | none shipped; trained on raw builder output (`ML/model_card.json` → `scaling`) |
| Output | 5-way class and confidence per flow, plus a host head |
| Classes, in order | BENIGN, Volumetric_Flood, PortScan, BruteForce, Botnet |
| Inference path | separate service (`graphsentinel.inference.service`), called by the backend |
| Evaluation evidence | `ML/test_report.json`, offline, CICIDS2017: edge binary F1 0.9961; per-class F1 Volumetric_Flood 0.9617, PortScan 0.2598, BruteForce 0.0000, Botnet no test edges |

For v2 the training package and the inference service share one graph builder
and one class list, and the backend refuses to start on a contract mismatch
(CODE `backend/app/services/inference_v2.py`, `model_contract.py`). Class order
parity is 🟢 verified by `ML/verify_stack.py` check 6 and by the test suite.

Test suites run for this audit: ML package **181 passed**; backend **252 passed,
3 skipped** (same code, run earlier the same day); frontend build succeeds, 16
unit tests pass.

---

## 5. Model Capability Matrix

| Attack | v1 GraphSAGE | v2 GATv2 | Best choice for the demo | Confidence |
|---|---|---|---|---|
| DDoS | UNSAFE TO CLAIM as detection. Binary only; blocks attackers and benign hosts alike on live traffic (RUN) | WEAK on live: a one-conversation flood got no rule; a many-conversation flood got one, at the same confidence as benign fetches (RUN). STRONG offline only | v1, shown as the mechanism | High |
| DoS Hulk | NOT IMPLEMENTED: no script. The label is a heuristic on HTTP bytes | Same class as DDoS (Volumetric_Flood); no separate class | Not demonstrated | High |
| PortScan | UNSAFE TO CLAIM. Label is a heuristic (5 or more destination ports) | Alert-only by policy; offline F1 0.2598; confused with BruteForce | v1, shown as the mechanism | High |
| SSH Brute Force | UNSAFE TO CLAIM. Label heuristic needs port 22 **and** more than 250 packets; the brute-force-shaped host in the live runs was labelled "Botnet" (RUN) | Offline F1 0.0000; on live traffic labelled Volumetric_Flood (RUN) | v1, mechanism only; expect the wrong label | Medium |
| Botnet | NOT SUPPORTED. "Botnet" is the heuristic's fall-through label for anything it does not match | NOT SUPPORTED: 0 of 168 correct on the committed sample; alert-only | Not demonstrated | High |

"Best choice" means the model whose path produces something visible. It does
not mean the model detects the attack.

---

## 6. Mininet Attack Verification

All from CODE (`mininet/topologies/attack_scripts/`). **None of the four scripts
was executed for this audit**; the live runs used a separate traffic script. So
"OVS visible" below is inferred from the controller's behaviour, which the live
runs did verify.

| Attack | Script | Traffic generated | OVS visible | Features the model needs | Model compatible | Status |
|---|---|---|---|---|---|---|
| DDoS | `ddos_attack.py` | `ping -f` h2→h1 for 15 s: an **ICMP** flood | One table entry each way | v2: one conversation is one edge, whatever its packet count | v2: no (RUN, different flood, same shape). v1: UNVERIFIED | 🟠 |
| DoS Hulk | **none** | — | — | — | — | 🔴 NOT IMPLEMENTED |
| Port Scan | `portscan_attack.py` | h2 opens TCP to 9 fixed ports on h1, looped for 15 s | One entry per attempt (new source port each time) | destination port reaches both models | v1 heuristic will say PortScan (9 ports ≥ 5) if v1 scores it over 0.75: UNVERIFIED | 🟡 |
| SSH Brute Force | `ssh_bruteforce_attack.py` | h2 opens TCP to h1:22 in a loop for 15 s; **nothing listens on 22**, so every attempt is refused | One entry per attempt | no TCP flags reach either model from OVS, so SYN behaviour is invisible | v1 label needs >250 packets on port 22: unlikely from refused connections | 🟠 |
| Botnet | `botnet_burst.py` | h4, h6, h8 open TCP to h3 on 6667 and 8080 every 2 s for 20 s; nothing listens | Yes | periodicity is not a v1 feature; v2's host memory is untrained | Neither | 🔴 |

**🔴 Every script builds and tears down its own Mininet network**
(`GraphSentinelTopology()` then `topology.start()` … `topology.stop()`). So:

- a script cannot be run against an already running topology (the switch name
  `s1` collides);
- when the script ends the switch is deleted, so the backend's polls fail from
  then on;
- an attack lasts 15 to 20 s, which is 3 or 4 polls. v2 closes a window only
  when a later poll crosses a 60 s boundary; after the switch is gone there is
  no later poll with flows. **Whether a v2 window ever closes for a scripted
  attack is UNVERIFIED and unlikely.**

---

## 7. Feature Parity Audit

### v1 (7 features per flow) — CODE `backend/app/services/graph_builder.py:44-78`

| Feature | v1 training | v1 live | Available from OVS? |
|---|---|---|---|
| `fwd_ratio` | UNVERIFIED | fwd / (fwd+bwd) packets | **No direction split.** Takes only 0 or 1 (RUN) |
| `avg_packet_size` | UNVERIFIED | bytes / packets | Yes |
| `connection_rate` | UNVERIFIED | log1p(packets / duration) | Yes, but duration is the table entry's age |
| `port_norm` | UNVERIFIED | dst_port / 65535 | Yes |
| `byte_asymmetry` | UNVERIFIED | (fwd − bwd) / total bytes | **No.** Takes only 0 or 1 (RUN) |
| `syn_ratio` | UNVERIFIED | SYN count / packets | **No.** Constant 0: no dump carries `tcp_flags` (RUN) |
| `bytes_rate_norm` | UNVERIFIED | log-scaled bytes/s | Yes, same caveat on duration |

Measured on the 23,526 flows of live run 3 against the training statistics the
backend scales by: `connection_rate` mean 0.0609 against a training mean of
3.5594; `bytes_rate_norm` 0.0431 against 0.3756; 52% of submitted flows had zero
packets.

### v2 (20 edge features) — CODE `backend/app/services/flow_mapping.py:25-37`, `:120-178`

| Group | Features | v2 training | v2 live from OVS |
|---|---|---|---|
| Filled (10) | `log_duration_s`, `log_total_packets`, `log_total_bytes`, `avg_packet_size`, `log_dt_since_pair`, `log_dt_since_src`, `window_position`, `direction_flag`, `log_bytes_per_s`, `log_packets_per_s` | CICFlowMeter columns | Derived; the three timing features take poll-shaped values because every flow in a poll shares one timestamp |
| Pinned (2) | `fwd_packet_ratio`, `byte_asymmetry` | real | **constant 1.0 and +1.0** |
| Zero (8) | `log_max_fwd_len`, `log_max_bwd_len`, `log_iat_mean`, `iat_burstiness`, `syn_ratio`, `rst_ratio`, `ack_ratio`, `psh_ratio` | real | **0.0** |

### Mismatches common to both

- **Aggregation unit.** Training data is one record per completed flow. Live
  input is one record per table entry **per poll**, with cumulative counters: a
  conversation was submitted between 1.16 and 9.17 times per window in run 3.
- **Graph size.** v1's config trains on 500-flow windows; live, it scores
  whatever one poll returns.
- **v2's effect of the missing features is not measured.** That is the single
  most likely cause of benign traffic being labelled an attack, and it is open.

---

## 8. Model Routing Audit

**Is model selection between v1 and v2 implemented? No.**

```text
CURRENT:
  monitor.py:327   result = analyze_flows(flows)          # v1, every poll, always
  monitor.py:337   self._score_v2(flows, observed_at)     # v2, additionally, if enabled
  No code chooses a model per attack, per class, or per confidence.
  v2's rules and verdicts are returned by score_flows and discarded by the monitor.

REQUIRED for the intended architecture (not present):
  - a decision component that receives both results for the same flows;
  - a place where v2's verdicts are stored and served to the frontend;
  - a rule for which model's output creates the incident.
```

**MODEL ROUTING REQUIRED.** Having two checkpoint files loaded does not make the
hybrid in the brief exist.

### Is a hybrid safe on the current code?

No. The backend's incident path assumes a single binary score per source:

- `threat_analyzer.py:94` compares one float to one threshold;
- the incident's `attack_type` is filled by `infer_attack_type()`, a heuristic;
- the frontend's attack taxonomy is v1's heuristic names (DDoS, SSHBrute,
  PortScan, Botnet, DoSHulk), not v2's five classes
  (CODE `backend/app/models/schemas.py:12`);
- v2's taxonomy has no DoS Hulk and no separate DDoS: both are Volumetric_Flood.

Routing "DDoS → v2" would need all four changed.

---

## 9. Inference Pipeline Audit

| Step | File and function | Input → output | Failure mode |
|---|---|---|---|
| OVS → text | `backend/scripts/enforcement_daemon.py` `handle_request` | `sudo ovs-ofctl dump-flows s1` → raw text | daemon down or wrong token → poll `failed` |
| text → flows | `backend/app/mininet_monitor/flow_parser.py` `_parse_output` | lines with `nw_src`/`nw_dst` or ARP → dicts tagged `"ovs"` | IPv6 lines dropped silently |
| poll | `monitor.py:323` | whole table every 5 s | re-submission (section 7) |
| v1 features + graph | `graph_builder.py:136` `build_pyg_graph` | flows → 7×N tensor, chain edges | — |
| v1 inference | `inference_service.py:133` `predict` | → per-flow and per-source scores | falls back to a **heuristic scorer** if the model fails to load or throws (`:135`, `:156`) |
| v2 gate | `monitor.py` `_score_v2` | refuses any batch not entirely `"ovs"` | demo or manual flows are never scored by v2 |
| v2 mapping | `flow_mapping.py` `map_flow` | flow → CICFlowMeter-shaped record | section 7 |
| v2 inference | inference service, 60 s windows, minimum 8 edges | → class + confidence per flow | a window under 8 flows is unscored |

Verified end to end by RUN: in run 3 the flows parsed from the daemon's own
responses equal, window by window, the flow counts the backend logged.

---

## 10. Decision / Mitigation Audit

### Thresholds

| Threshold | Defined | Applied | Model | Consequence |
|---|---|---|---|---|
| `THREAT_THRESHOLD` = 0.75 | `backend/app/config.py:14`; `.env` | `threat_analyzer.py:94` | v1 | incident + block + chain write |
| severity bands | hard-coded in `threat_analyzer.py` / `graph_state.py:28` | node colour, severity | v1 | display |
| DDoS label if score ≥ 0.90 or packets > 5000 | `threat_analyzer.py` `infer_attack_type` | label only | heuristic | display |
| SSHBrute label: port 22 and packets > 250 | same | label only | heuristic | display |
| PortScan label: 5 or more ports | same | label only | heuristic | display |
| v2 floors: Volumetric_Flood 0.90, BruteForce 0.85, PortScan 0.85 (alert-only), Botnet 1.01 (disabled) | `backend/app/services/mitigation_policy.py` | `sdn.py` translator | v2 | dry-run rule or withholding |
| v2 window 60 s, minimum 8 edges | v2 config | graph builder | v2 | unscored window |
| idempotency bucket: one incident per source per minute | `threat_analyzer.py` `_create_incident` | v1 | dedup |
| already-blocked skip | `threat_analyzer.py:109` | v1 | **no new incident for a blocked host** |

No confirmation count, cooldown or temporal aggregation exists on the v1 path:
one flow over 0.75 in one poll blocks the source.

**Is 0.75 appropriate for v1's output?** Not on live traffic. In the live runs
benign hosts scored 0.77 (just over it) within seconds. No new value is
recommended here: the evidence is two runs.

### Mitigation, traced

```text
v1 score ≥ 0.75                        threat_analyzer.py:94
  → validate_mininet_ip (10.0.0.0/24)  threat_analyzer.py:101
  → _already_blocked? skip             threat_analyzer.py:109
  → Incident row                       threat_analyzer.py:114
  → SelfHealingEngine.block_ip         threat_analyzer.py:129
      → EnforcementAgent.block_ip      enforcement_agent.py:96
          mode != 'ovs' → log, return 'simulated'      (the default everywhere)
          mode == 'ovs' → daemon: ovs-ofctl add-flow s1
                          priority=1000,ip,nw_src=<ip>,actions=drop
  → BlockedIP row; healing event; socket `healing_triggered`
```

- In `simulated` mode **nothing is blocked**: the backend records a block and the
  dashboard shows one. Traffic continues.
- In `ovs` mode a real drop rule is installed. This path was **not executed** in
  this audit or in the live runs: UNVERIFIED by execution.
- v2 installs nothing in any mode (`SDNTranslator.install` refuses outside
  dry-run).

---

## 11. Blockchain Audit

```text
threat_analyzer.py:142  self.blockchain.store_incident(...)      after the block call
  → blockchain_adapter.py store_incident → web3_client.log_incident
  → contract logIncident on Ganache → tx hash → Incident.blockchain_tx
  → /api/v1/forensics → dashboard
```

- Triggered: yes, for every **v1** incident, after mitigation, synchronously with
  a 5 s adapter timeout.
- Not simulated: it is a real transaction when Ganache and the contract are up.
- **When Ganache is not reachable it does not fail loudly**: the incident is
  stored with `blockchain_status = retry` and a reconciler retries. In the live
  runs Ganache was not running and all 16 incidents ended in `retry` (RUN).
- v2 never writes to the chain.
- A full chain write through Ganache was **not executed** for this audit:
  UNVERIFIED by execution here.

---

## 12. Frontend Audit

| Shown | Source | Status |
|---|---|---|
| Attacker IP | incident `source_ip` (v1) | 🟢 |
| Target | graph links from observed flows | 🟢 |
| Attack type | `infer_attack_type()` heuristic | 🟠 looks like a model output and is not |
| Confidence | v1 threat score | 🟢 (binary score, not class confidence) |
| Severity, timestamp | incident | 🟢 |
| Mitigation status | `enforcement_status` (`simulated` / `enforced`) | 🟢 |
| Blockchain transaction | `blockchain_tx`, status badge | 🟢 if Ganache is up |
| Host state | graph node status | 🟢 |
| **v2 class, v2 confidence, v2 rules** | **nothing** | 🔴 not displayed anywhere; only a header badge says whether v2 is running |

Path: `websocket/events.py:73/79/85` emits `graph_update`, `alert`,
`healing_triggered`; `frontend/src/hooks/useGraphData.js` polls nine REST
resources every 10 s. The frontend changes of 2026-10-05 build and pass unit
tests but **have not been seen in a browser**.

---

## 13. Demo Controller Audit

**There is no demo controller in the repository.** The sequence
DDoS → PortScan → SSH → Botnet → DoS Hulk is not implemented by any file.

If the four existing scripts are run one after another by hand:

| Risk | Evidence | Effect |
|---|---|---|
| Same attacker | `ddos_attack.py`, `portscan_attack.py` and `ssh_bruteforce_attack.py` all attack from 10.0.0.2 | After the first block, `_already_blocked` (`threat_analyzer.py:109`) skips h2: **attacks 2 and 3 produce no incident** |
| Victim blocked too | run 3: the flood's victim 10.0.0.3 was blocked as "PortScan" | reply traffic scores as malicious |
| State not reset | blocked IPs persist in SQLite across script runs | later attacks are invisible until hosts are unblocked |
| Topology rebuilt per script | each script creates and destroys `s1` | polls fail between scripts |
| v2 window | 15 s attack, 60 s window | v2 probably logs nothing |
| No DoS Hulk | no script | fifth step does not exist |
| Memory | this machine had 123–643 MB free; the inference service segfaulted once at start | start-up can fail |
| Chain | needs Ganache and a deployed contract | otherwise every incident shows `retry` |

---

## 14. Bugs / Required Changes

```text
ID: A1
Severity: 🔴 CRITICAL
File: backend/app/services/inference_service.py, graph_builder.py (v1 path)
Function: InferenceService.predict / ThreatAnalyzer.evaluate
Problem: On live OVS traffic v1 scores benign hosts over the 0.75 threshold.
Evidence: RUN. live_loop2.db: 7 incidents, 5 of them on hosts that had sent only
  benign pings/fetches, the first 11 s after benign traffic began. live_loop3.db:
  9 of 10 hosts blocked, including the flood's victim.
Impact: With background traffic the dashboard fills with false blocks; in `ovs`
  mode those hosts would be cut off.
Required Change: None to the model before the presentation. Run the demo with NO
  benign background traffic and keep ENFORCEMENT_MODE=simulated.
Can Demo Work Without Fix: Yes, with that constraint.
```

```text
ID: A2
Severity: 🔴 CRITICAL
File: mininet/topologies/attack_scripts/*.py; backend/app/services/threat_analyzer.py:109
Function: main() in each script; ThreatAnalyzer._already_blocked
Problem: Three scripts attack from 10.0.0.2; a blocked host creates no new incident.
Evidence: CODE.
Impact: Only the first attack of a sequence is shown.
Required Change: Unblock the attacker between attacks (the dashboard's Unblock,
  as an admin), or give each script a different attacking host.
Can Demo Work Without Fix: Only for a single attack.
```

```text
ID: A3
Severity: 🔴 CRITICAL
File: (absent)
Problem: No DoS Hulk script and no demo controller exist.
Evidence: CODE. `git ls-files mininet` lists four attack scripts and two topologies.
Impact: The five-step sequence in the brief cannot be run.
Required Change: Drop DoS Hulk and the automated sequence from the presentation,
  or write them.
Can Demo Work Without Fix: Yes, with four manual attacks at most.
```

```text
ID: A4
Severity: 🔴 CRITICAL (for the claimed architecture)
File: backend/app/mininet_monitor/monitor.py:327, :337
Problem: No model routing and no decision layer; v2's output is discarded.
Evidence: CODE.
Impact: The architecture diagram in the brief is not the system.
Required Change: Present the actual architecture (section 2).
Can Demo Work Without Fix: Yes, if the slide is changed.
```

```text
ID: A5
Severity: 🟠 HIGH
File: backend/app/services/threat_analyzer.py (infer_attack_type)
Problem: The attack type on screen is a port/volume heuristic that falls through
  to "Botnet".
Evidence: CODE; RUN: benign hosts and the brute-force-shaped host were labelled
  "Botnet".
Impact: An examiner will read the label as a model's classification.
Required Change: Say so when presenting. No code change needed.
Can Demo Work Without Fix: Yes.
```

```text
ID: A6
Severity: 🟠 HIGH
File: backend/app/services/flow_mapping.py; ML/graphsentinel_v2 (v2 path)
Problem: On live traffic v2 predicts about half of benign flows as attacks and
  its rules land on benign fetches.
Evidence: RUN. ML/live_loop_run.json, ML/live_loop_run3.json.
Impact: v2 cannot be shown as detecting attacks live.
Required Change: None before the presentation. Show v2's offline results only.
Can Demo Work Without Fix: Yes.
```

```text
ID: A7
Severity: 🟠 HIGH
File: mininet/topologies/attack_scripts/*.py
Problem: Each script creates and destroys its own topology; attacks last 15-20 s.
Evidence: CODE.
Impact: Cannot attack a running topology; v2's 60 s window probably never closes.
Required Change: Run attacks inside one long-lived topology
  (base_topology_headless.py) with `mnexec`, as the live runs did.
Can Demo Work Without Fix: For v1 only, one script at a time.
```

```text
ID: A8
Severity: 🟡 MEDIUM
File: ML/GraphSage-model/ (v1 training code absent)
Problem: v1's training/inference parity cannot be verified.
Evidence: CODE. No file in the repository builds v1's training features.
Impact: v1's reported accuracy cannot be reproduced or scoped.
Required Change: Do not quote v1's accuracy as a system result.
Can Demo Work Without Fix: Yes.
```

```text
ID: A9
Severity: 🟡 MEDIUM
File: mininet/topologies/attack_scripts/ddos_attack.py
Problem: The "DDoS" is an ICMP ping flood from one host: one conversation.
Evidence: CODE; RUN shows a one-conversation flood gets no v2 rule.
Impact: v2 will not flag it; v1's behaviour on it is unverified.
Required Change: None required; do not describe it as distributed.
Can Demo Work Without Fix: Yes.
```

```text
ID: A10
Severity: 🟡 MEDIUM
File: backend/app/services/blockchain_adapter.py
Problem: With Ganache down incidents silently become `retry`.
Evidence: RUN: 16 of 16 incidents in the live runs.
Impact: No transaction hash to show.
Required Change: Start Ganache and deploy the contract before the demo; check
  /health → blockchain.connected.
Can Demo Work Without Fix: Yes, without the ledger part.
```

```text
ID: A11
Severity: 🔵 LOW
File: frontend/src/pages/LandingPage.jsx
Problem: States a detection accuracy and a sub-500 ms isolation time.
Evidence: CODE. No latency measurement exists in the repository.
Impact: A claim on screen that nothing supports.
Required Change: Do not show the landing page figures as results.
Can Demo Work Without Fix: Yes.
```

---

## 15. Minimum Changes Required Before Presentation

### MUST FIX (none of these needs a model change)

1. **Change the architecture slide** to section 2: two models side by side, v1
   acts, v2 advises in dry-run. Remove "model selection" and "decision layer".
2. **Remove DoS Hulk and the automated five-attack sequence**, or write the
   missing script and controller.
3. **Plan the attack order around the already-blocked rule**: unblock 10.0.0.2
   between attacks, or use a different attacker per attack.
4. **No benign background traffic during the live demo**, and keep
   `ENFORCEMENT_MODE=simulated`.
5. **Rehearse on the presentation machine with the real scripts.** They were not
   executed for this audit.

### SHOULD FIX

6. Run the attacks inside one long-lived topology rather than one topology per
   script.
7. Start Ganache and confirm `blockchain.connected` before starting.
8. Look at the dashboard in a browser once; recent frontend changes are unseen.
9. Free memory first (drop the WSL page cache); the inference service failed to
   start once without it.

### OPTIONAL

10. Show v2 from its log lines (`rule … on … -> …`, `withheld … : reason`) in a
    terminal beside the dashboard, as an honest view of the advisory path.

---

## 16. Recommended Presentation Configuration

```text
DDoS       → v1. Present as: the mechanism (a host crosses the threshold, is
             blocked in simulated mode, recorded, displayed). Not as "detected
             by GraphSAGE" in the sense of a validated detector.
DoS Hulk   → NOT DEMONSTRATED. No script; no separate class in v2.
PortScan   → v1, mechanism. The "PortScan" label is the heuristic's.
             v2: alert-only by policy; mention its offline confusion with BruteForce.
SSH Brute  → v1, mechanism. Expect the label to be wrong ("Botnet").
             v2: not usable (offline F1 0.0000; live, labelled Volumetric_Flood).
Botnet     → NOT DEMONSTRATED. Neither model detects it. Present it as the
             project's measured blind spot.
```

v2 is best presented **offline**: its test-set results, the timestamp defect it
exposed, and the live run that showed its result does not transfer.

---

## 17. Exact Demo Flow

```text
 1. Free memory. In WSL as root: sync; echo 3 > /proc/sys/vm/drop_caches
 2. Start Ganache and deploy the contract; note the address.           (optional: ledger)
 3. WSL: start Open vSwitch; python3 mininet/topologies/base_topology_headless.py
 4. WSL: start backend/scripts/enforcement_daemon.py with the backend's DAEMON_TOKEN
 5. Verify OVS: ovs-ofctl dump-flows s1 shows per-flow entries after one ping
 6. Start the inference service, then the backend (ENFORCEMENT_MODE=simulated)
 7. python ML/verify_stack.py  → expect ten checks to pass
 8. Start the frontend; sign in as the admin; confirm the header says LIVE
 9. Run ONE attack inside the running topology
      mnexec -a $(pgrep -f 'mininet:h2$') <attack command>
10. Wait two polls (10 s). Show: node turns red, incident appears, host shows
    as blocked (simulated)
11. Show the incident in Forensics, and its ledger entry if Ganache is up
12. Say what the attack-type label is (a heuristic) before anyone asks
13. Unblock the attacker; run the next attack from a different host
14. Finish on the measured limits: section 18's second list
```

Do not run benign traffic generators alongside. Do not run the stock attack
scripts while the headless topology is up: they will try to create `s1` again.

---

## 18. Presentation Claims

### Claims I CAN safely make

- Real traffic in a Mininet network, through an Open vSwitch switch, is read by
  the backend, scored by two graph neural network models, and shown on the
  dashboard. This has been run end to end.
- When a source crosses the threshold the system creates an incident, records a
  block and, if the ledger is running, writes a transaction: the self-healing
  **mechanism** works.
- Blocking in the demo is simulated; the code can install a real OVS drop rule
  in `ovs` mode.
- v2 (GATv2) reaches edge binary F1 0.9961 **offline, on the CICIDS2017 test
  set**, with per-class F1 0.9617 for volumetric floods.
- The project found a timestamp defect in CICIDS2017 and re-measured after
  fixing it, reporting the lower numbers.
- The project tested its model on live traffic, found that the offline result
  does not transfer, and reports that.
- v2's proposed rules are dry-run and nothing it proposes reaches a switch.
- The provenance gate refuses any traffic not read from the switch.

### Claims I MUST NOT make

- That either model **detects** DDoS, port scans, brute force or botnets on the
  live network. v1 blocks benign hosts; v2 labels half of benign traffic an attack.
- That the attack type on the dashboard comes from a model. It is a heuristic.
- That the system routes each attack to the best model, or has a decision layer
  combining them. Neither exists.
- That v2 is used for mitigation. It is advisory and dry-run.
- "97.7% accuracy", "99.6% accuracy" or any accuracy figure as a property of the
  running system. They are offline figures on a 2017 dataset; v1's cannot be
  reproduced from the repository.
- "Under 500 ms" or any latency or real-time claim. Nothing measures it.
- That Botnet or DoS Hulk is detected or demonstrated.
- That the DDoS is distributed. It is one host pinging another.
- That the system could protect real devices or a real network.
- "Five-class detection" without saying that one class is never detected and
  two are confused with each other.

---

## 19. Final Verdict

```text
🟡 PRESENTATION READY AFTER SPECIFIC FIXES
```

The pipeline from switch to dashboard is real and has been executed. What is not
ready is the story the brief wants to tell with it. The required fixes are to the
**presentation** — the architecture slide, the attack sequence, the claims — and
to how the demo is run (no background traffic, simulated enforcement, unblock
between attacks). None requires changing a model or a threshold.

Presented as "a working detect–block–record–display mechanism, with two models
whose detection quality we measured honestly and found wanting on live traffic",
it is defensible. Presented as "a system that detects five attack types with a
hybrid of two models", it is false in ways an examiner can find by reading one
file.

One caution on the verdict itself: the four stock attack scripts were **not
executed** for this audit. Step 5 of section 15 is not optional.

---

## 20. Evidence Index

| Conclusion | File | Function / lines | Why it proves it |
|---|---|---|---|
| Both models run on every poll; no routing | `backend/app/mininet_monitor/monitor.py` | `_run`, 323, 327, 337 | one call to v1, then one to v2, unconditionally |
| v2 output is discarded | `backend/app/mininet_monitor/monitor.py` | `_score_v2`, 292 | only counters are kept from `score_flows` |
| v1 is binary, per flow | `backend/app/services/inference_service.py` | `predict`, 133-181 | softmax over 2, max per source |
| v1 graph is flows, not hosts | `backend/app/services/graph_builder.py` | `_edge_index`, 81-96 | edges chain consecutive flows |
| v1's 7 features | `backend/app/services/graph_builder.py` | `_feature_row`, 44-78 | the feature vector itself |
| Attack type is a heuristic | `backend/app/services/threat_analyzer.py` | `infer_attack_type` (ends at 74 `return "Botnet"`) | port and packet rules, no model call |
| One threshold decides | `backend/app/services/threat_analyzer.py` | `evaluate`, 94 | `if score < self.threshold: continue` |
| Blocked host creates no incident | `backend/app/services/threat_analyzer.py` | 109 | `_already_blocked` → `continue` |
| Simulated mode blocks nothing | `backend/app/services/enforcement_agent.py` | `block_ip`, 96-100 | returns `'simulated'` before any daemon call |
| Real drop rule in `ovs` mode | `backend/scripts/enforcement_daemon.py` | `handle_request` | `ovs-ofctl add-flow … actions=drop` |
| Whole table every poll | `backend/app/mininet_monitor/flow_parser.py` | `result_from_output`, `_parse_output` | parses the full dump; no diff |
| v2 fills 10 of 20 features | `backend/app/services/flow_mapping.py` | module docstring 25-37; `map_flow` 120-178 | the mapping itself |
| v2 rule dedup key | `ML/graphsentinel_v2/graphsentinel/inference/sdn.py` | 294 | `(src, dst, proto, port-or--1)` |
| PortScan and Botnet alert-only | `backend/app/services/mitigation_policy.py` | `_POLICY_BY_CLASS` | `action=ACTION_ALERT_ONLY` |
| No DoS Hulk, no controller | repository listing | `git ls-files mininet` | four attack scripts, two topologies |
| Scripts build their own topology | `mininet/topologies/attack_scripts/*.py` | `main` | `GraphSentinelTopology()`, `start()`, `stop()` |
| Three scripts share an attacker | same | `attacker = topology.hosts["10.0.0.2"]` | identical in ddos, portscan, ssh |
| v1 blocks benign hosts live | `C:\dev\gs_live\live_loop2.db`, `live_loop3.db` (untracked) | `incidents` table | 7 and 9 incidents, with timestamps inside the benign-only phase |
| v2 wrong on live traffic | `ML/live_loop_run.json`, `ML/live_loop_run3.json` | `windows`, `rules_by_what_the_flow_was` | counted from the backend's own log |
| Parser input equals what was scored | `ML/retrain_logs/live_loop/daemon_responses_run3.txt` | re-parsed per window | counts equal the backend's log lines |
| v1 training code absent | repository | search for `fwd_ratio` | only inference and check scripts match |
| Suites pass | executed | ML 181 passed; backend 252 passed, 3 skipped | run on this code |

### What this audit did not verify

- The four stock attack scripts, by execution.
- `ENFORCEMENT_MODE=ovs` installing a real drop rule.
- A blockchain write through Ganache.
- Anything in a browser.
- v1's training pipeline (not in the repository).
- v1's score on each scripted attack in isolation, without background traffic.

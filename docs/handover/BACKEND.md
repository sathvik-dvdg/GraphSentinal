# Backend and Mininet handover

For Sairaj. Written from the code on branch `fix/audit-p0-p1` at `5fd69a6`. No
source file was changed to write this. Every file and line cited was read.
Measured numbers are quoted from `MODEL_BEHAVIOUR.md`, `OPEN_ITEMS.md`, the
audit report and `mininet/demo/tested_run.txt`, and say which.

Four names in older notes do not match the tree, so you are not sent looking for
files that do not exist:

- The routers are in `backend/app/api/v1/`, not `backend/app/routers/`.
- `SelfHealingEngine` is in `backend/app/services/self_healing.py`.
- The chain client is `blockchain/web3_bridge/web3_client.py`; the backend
  loads it through `blockchain_adapter.py`.
- `SDNTranslator` is not in the backend. It runs inside the v2 inference
  service (`ML/graphsentinel_v2/graphsentinel/inference/sdn.py`).

---

## 1. What the backend is

A FastAPI application with a Socket.IO server mounted over it, SQLite through
SQLAlchemy 2 (Alembic migrations in `backend/migrations/`), PyTorch and PyTorch
Geometric for the v1 model, `httpx` to reach the v2 inference service, and
`web3` 7.4.0 for the chain. Two background threads start with it: the monitor,
which polls the switch, and the reconciliation worker.

Start it from `backend/` (`RUN_GUIDE.md` §5):

```powershell
$env:GS2_ENABLED     = "true"
$env:GS2_SERVICE_URL = "http://127.0.0.1:8081"
$env:GS2_MODEL_DIR   = "../ML"
python -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8001
```

The target must be `app.main:socket_app`. `app.main:app` serves REST without the
socket.

Settings are read from `backend/.env` by `backend/app/config.py`; an environment
variable overrides the file. The ones that matter:

| Variable | Default (`config.py`) | What it does |
|---|---|---|
| `THREAT_THRESHOLD` | `0.75` | v1's single gate. A source at or over it gets an incident, a block and a chain write. Can be changed at runtime from Settings; that change is in memory only. |
| `ENFORCEMENT_MODE` | `simulated` | `simulated`: a block is logged and recorded, nothing touches the switch. `ovs`: a real drop rule is installed. Keep `simulated` for the demo. |
| `POLL_INTERVAL_SECONDS` | `5` | Monitor poll period. |
| `GS2_ENABLED` | `false` | Turns the v2 path on. Compose sets it to `true`; the manual path must set it. |
| `GS2_SERVICE_URL` | `http://127.0.0.1:8080` | Where the v2 inference service is. Use 8081 on this machine (`RUN_GUIDE.md` §5 says why). |
| `GS2_MODEL_DIR` | `../ML` | Folder holding `model_card.json`. The backend reads the card, never the weights. |
| `GS2_REQUIRE_CONTRACT` | `true` | With v2 on, refuse to boot if the card is missing or the wrong version. |
| `DAEMON_HOST` / `DAEMON_PORT` / `DAEMON_TOKEN` | `127.0.0.1` / `50051` / `test-token` | How to reach the enforcement daemon. The token must equal the daemon's own `DAEMON_TOKEN` or every poll fails with "Unauthorized". |
| `DEMO_FALLBACK_FLOWS` | `false` | When a poll **fails**, substitute random synthetic flows. `.env.docker` sets it `true`. Must be `false` for the Mininet demo. |
| `GANACHE_URL` / `CONTRACT_ADDRESS` | `http://127.0.0.1:8545` / empty | The chain. `blockchain/scripts/deploy.js` rewrites both in `backend/.env`. Read once, at startup. |
| `BLOCKCHAIN_TX_TIMEOUT_SECONDS` | `5` | How long the adapter waits for one chain write. |
| `BLOCKCHAIN_RETRY_INTERVAL_SECONDS` | `10` | Reconciliation worker period. |
| `OPERATOR_USERNAME` / `OPERATOR_PASSWORD` | `admin` / `change-me-for-demo` | The admin login. |
| `READONLY_USERNAME` / `READONLY_PASSWORD` | `readonly` / `readonly-for-demo` | The read-only login. |
| `BACKEND_API_TOKEN` / `ADMIN_API_TOKEN` | `change-me-for-demo` / `admin-secret-key-for-demo` | `X-API-Key` values. The first has the operator role, the second admin. `run_demo.py --api-key` needs the admin one. |
| `MAX_ANALYZE_FLOWS` | `5000` | Upper limit on flows in one analysis, **including one monitor poll** (BE-10). |
| `SQLITE_PATH` | `./graphsentinel.db` | The database file. |
| `CORS_ORIGINS` | ports 5173, 5174, 3000 on localhost | Allowed browser origins, for REST and the socket. |

---

## 2. Service map

| Component | File | What it does | What it calls |
|---|---|---|---|
| `MininetMonitor` | `app/mininet_monitor/monitor.py` | A thread. Every 5 s: poll the switch, run v1, push socket events, then offer the same flows to v2. Keeps poll and v2-gate counters for `/health`. | `poll_ovs_flows`, `analyze_flows`, `emit_analysis_events`, `score_flows` |
| Flow parser (functions, no class) | `app/mininet_monitor/flow_parser.py` | Asks the daemon for `dump-flows`, turns the text into flow dicts tagged `data_source="ovs"`. Reports `ok`, `ok_empty` or `failed`. Also holds `demo_flows()`. | The enforcement daemon, over TCP |
| `analyze_flows` | `app/services/analysis_pipeline.py` | The v1 pipeline in one function: validate → score → evaluate → update graph. Used by the monitor and by `POST /analyze`. | `InferenceService`, `ThreatAnalyzer`, `graph_state` |
| Graph builder (functions) | `app/services/graph_builder.py` | Builds v1's input: one node **per flow**, 7 features, scaled; edges chain consecutive flows and flows sharing a destination port. | torch |
| `InferenceService` (v1) | `app/services/inference_service.py` | Loads the GraphSAGE weights once (singleton). `predict` returns a score per flow and the maximum per source IP. Falls back to a hand-written formula if the model is unavailable. | `build_pyg_graph`, `GraphSAGEClassifier` (`graphsage_model.py`) |
| `ThreatAnalyzer` | `app/services/threat_analyzer.py` | Applies the threshold per source. Creates the incident, calls the block, calls the chain write, records the enforcement action. Holds `infer_attack_type`. | `SelfHealingEngine`, `BlockchainAdapter`, `enforcement_log` |
| `SelfHealingEngine` | `app/services/self_healing.py` | Blocks or unblocks one IP: calls the agent, upserts or deletes the `blocked_ips` row, returns the healing event. | `EnforcementAgent` |
| `EnforcementAgent` | `app/services/enforcement_agent.py` | In `simulated` mode logs and returns `'simulated'`. In `ovs` mode sends `block` / `unblock` to the daemon. Holds `validate_mininet_ip`. | The enforcement daemon |
| `GraphState` | `app/services/graph_state.py` | The in-memory current graph (singleton). Builds `/graph` and `/stats`, and writes every flow of every poll to `flow_snapshots`. | SQLite |
| `BlockchainAdapter` | `app/services/blockchain_adapter.py` | Singleton wrapper round the chain client. `store_incident` and `release_node` run the client in a worker thread with a 5 s timeout. | `BlockchainClient` (`blockchain/web3_bridge/web3_client.py`) |
| Reconciliation (`ReconciliationWorker`, `reconcile_once`, `reconcile_blockchain_outbox`) | `app/services/reconciliation.py` | A thread, every 10 s. In `ovs` mode makes the switch's drop rules match `blocked_ips`. Always: looks up pending chain transactions and retries unwritten incidents. Also prunes old flow snapshots. | The daemon, `BlockchainAdapter` |
| `InferenceV2State` | `app/services/inference_v2.py` | Built once at startup. Holds the validated model contract, the mitigation policy and the operating points. Decides whether v2 is ready. | `model_contract`, `mitigation_policy`, `operating_points` |
| `MitigationPolicy` | `app/services/mitigation_policy.py` | The only v2 policy: per class, an action and a confidence floor. Built from the model card's class list; startup fails if they disagree. | — |
| Flow mapping (functions) | `app/services/flow_mapping.py` | Turns a backend flow into the CICFlowMeter-shaped record v2's graph builder expects. | — |
| `InferenceClient` | `app/services/inference_client.py` | HTTP client for the v2 service (singleton). `submit` maps and posts flows, returns any windows that closed. No fallback. | `map_flows`, the inference service |
| `score_flows` | `app/services/analysis_pipeline_v2.py` | The v2 path: check the service's contract, submit, check the policy digest echoed back, log rules admitted and withheld. | `InferenceClient` |
| `SDNTranslator` | `ML/graphsentinel_v2/graphsentinel/inference/sdn.py` (inference service process) | Turns v2's scored flows into candidate rules under the policy the backend sent. `install` writes nothing in dry-run and raises outside it. | — |
| Enforcement daemon | `backend/scripts/enforcement_daemon.py` (separate process, root, WSL) | Runs `ovs-ofctl` for the backend. | `sudo ovs-ofctl` |

---

## 3. The poll loop, traced

Everything below happens in the monitor's thread, in this order, once every
5 s. `MininetMonitor._run` is `monitor.py:318-348`.

### v1: the path that acts

1. **Poll.** `_run` records `observed_at = time.time()` (`monitor.py:322`) and
   calls `self._poll()` (`:323`), which calls
   `poll_ovs_flows(settings.enforcement_switch)` (`monitor.py:149` →
   `flow_parser.py:43-78`). That opens a TCP socket to the daemon, sends
   `{"token", "action": "dump_flows", "switch": "s1"}`, and passes the returned
   text to `result_from_output` → `_parse_output` (`flow_parser.py:88-154`).
   **Carried forward:** `flows`, a list of dicts, each
   `{src_ip, dst_ip, src_port, dst_port, protocol, packet_count, byte_count, duration_sec, tcp_flags, data_source: "ovs"}`.
   If the poll failed and `DEMO_FALLBACK_FLOWS` is on, `_poll` replaces `flows`
   with `demo_flows()` tagged `"demo"` (`monitor.py:155-159`).

2. **Analyse.** `analyze_flows(flows)` (`monitor.py:327` →
   `analysis_pipeline.py:13-34`). It raises `ValueError` if there are more than
   `max_analyze_flows` flows (`:14-15`), then validates every dict into a
   `FlowRecord` (`:17`). **Carried forward:** `flow_records`.

3. **Build the graph.** `InferenceService.predict(flow_records)`
   (`inference_service.py:133`) calls `build_pyg_graph`
   (`graph_builder.py:136-159`). One row of 7 features per flow from
   `_feature_row` (`:44-78`), scaled with the fixed mean and standard deviation
   from `get_global_stats` (`:107-128`); edges from `_edge_index` (`:81-96`).
   **Carried forward:** a `GraphData` with `x` (N × 7), `edge_index`,
   `flow_sources`, `flow_destinations`. This is a dataclass shaped like a PyG
   `Data`, not a PyG object.

4. **Score.** `self.model.predict_proba(graph.x, graph.edge_index)`
   (`inference_service.py:143-144`) gives P(malicious) per flow.
   `_aggregate_source_scores` (`:224-229`) takes the **maximum per source IP**.
   **Carried forward:** `prediction`, a dict with `flow_scores`,
   `source_scores` (what the analyzer uses) and `ip_scores` (what the graph
   uses; a destination gets a quarter of the flow's score).

5. **Evaluate.** `ThreatAnalyzer().evaluate(prediction, flow_records)`
   (`analysis_pipeline.py:20-21` → `threat_analyzer.py:86-165`). For each
   source:
   - under the threshold: skip (`:94`);
   - outside `10.0.0.0/24`: skip, recorded in `skipped` (`:100-105`);
   - already in `blocked_ips`: skip, recorded in `skipped` (`:109-111`);
   - label it: `infer_attack_type(clean_ip, score, related_flows)` (`:113`);
   - create the `Incident` row with `blockchain_status="submitting"`
     (`_create_incident`, `:175-209`). The idempotency key (`:277-285`) is a
     hash of IP, label, score to two decimals, severity, the current minute and
     the set of targets.

6. **Block.** `self.healer.block_ip(...)` (`threat_analyzer.py:129` →
   `self_healing.py:17-64`) → `_enforce_block` → `EnforcementAgent.block_ip`
   (`enforcement_agent.py:96-112`). In `simulated` mode that logs and returns
   `'simulated'` (`:98-100`); in `ovs` mode it sends
   `{"action": "block", "ip", "switch"}` to the daemon. Then the `blocked_ips`
   row is upserted. **Carried forward:** `healing_event`.

7. **Write to the chain.** `self.blockchain.store_incident(...)`
   (`threat_analyzer.py:142-148` → `blockchain_adapter.py:86-156`). Synchronous,
   in this thread, with a 5 s timeout. **Carried forward:** `tx_result`, with
   `tx_hash` and `status`. `_update_incident_after_actions` (`:212-250`) writes
   the outcome to the incident: `confirmed`, `pending` (a hash but no receipt
   yet), or `retry` for anything else, including "chain offline".

8. **Record and return.** `log_enforcement_action` (`:150-161`) appends to
   `enforcement_actions`; an alert dict is built (`_alert_record`, `:254-274`).
   `evaluate` returns `(alerts, healing_events)`.

9. **Update the graph.** `graph_state.update(flow_records, prediction)`
   (`analysis_pipeline.py:22` → `graph_state.py:117-124`) replaces the in-memory
   flows and writes one `flow_snapshots` row per flow.

10. **Emit.** `self._emit(result)` (`monitor.py:328`, `:299-316`) schedules
    `emit_analysis_events` (`websocket/events.py:62-87`) on the server's event
    loop: one `graph_update` (capped at 50 nodes and 100 links), one `alert` per
    new alert, one `healing_triggered` per block.

### v2: the path that advises, on the same poll

Runs straight after step 10, isolated in its own `try` so it cannot stop v1
(`monitor.py:336-340`).

1. **Gate.** `_score_v2(flows, observed_at)` (`monitor.py:244-297`). Returns at
   once if v2 is not ready or there are no flows. Then the provenance gate: if
   **any** flow's `data_source` is not `"ovs"`, the whole batch is refused and
   counted (`:282-285`). Demo and simulated flows never reach v2.

2. **Map.** `score_flows(flows, state, observed_at=observed_at)`
   (`monitor.py:292` → `analysis_pipeline_v2.py:143-202`) →
   `InferenceClient.submit` (`inference_client.py:213-250`) →
   `map_flows` → `map_flow` (`flow_mapping.py:108-178`). **Carried forward:** a
   list of records with CICFlowMeter column names; every flow in the poll gets
   the same `t = observed_at`.

3. **Infer.** `POST /flows` with `{flows, policy}` to the inference service
   (`ML/graphsentinel_v2/graphsentinel/inference/service.py:105-114`) →
   `InferenceEngine.ingest` (`engine.py:199-225`), which buffers records and
   closes a window each time `t` crosses a 60 s boundary. `_close_window`
   (`:232-306`) builds one IP-as-node graph; fewer than 8 flows and the window
   comes back `unscored`. Otherwise the model predicts, and
   `SDNTranslator.translate` (`sdn.py:213-326`) turns attack-classified flows
   into rules under the policy, recording every one it withholds and why.

4. **Accept.** Back in the backend, `_rules_for`
   (`analysis_pipeline_v2.py:72-100`) discards the rules unless the service
   echoed this backend's policy digest and reported `dry_run`. It logs one line
   per window, one per rule (`:92-96`) and one per withheld class and reason.

5. **Discard.** `score_flows` returns the windows, verdicts and rules. The
   monitor keeps two things from that return value: an error string and a
   window count (`monitor.py:293-297`). Everything else is dropped. No incident,
   no block, no chain write, nothing sent to the frontend.

---

## 4. v1: GraphSAGE

**Architecture.** Three `SAGEConv` layers with mean aggregation, 256 hidden
channels, batch norm and ReLU after the first two, dropout 0.3, two outputs;
`softmax(...)[:, 1]` is the score (`graphsage_model.py`, constructed at
`inference_service.py:87-91`; `ML/GraphSage-model/config.json`). The config
records a training window of 500 flows. The code that trained it is not in the
repository, so training and inference cannot be compared (audit A8).

**The 7 features**, from `_feature_row` (`graph_builder.py:44-78`). An OVS flow
supplies `packet_count`, `byte_count`, `duration_sec`, `dst_port` and
`tcp_flags`; it has no forward/backward split, so the code puts everything on
the forward side (`:51-54`).

| # | Feature | Computed as | On live OVS traffic |
|---|---|---|---|
| 0 | `fwd_ratio` | fwd packets / (fwd + bwd packets) | **Degenerate.** bwd is always 0, so it is 1 for a flow with packets and 0 for a flow with none. Two values only. |
| 1 | `avg_packet_size` | bytes / packets | Real. |
| 2 | `connection_rate` | `log1p(packets / duration)` | Real, but `duration` is the age of the table entry, not of the conversation. |
| 3 | `port_norm` | `dst_port / 65535` | Real. |
| 4 | `byte_asymmetry` | (fwd − bwd bytes) / total bytes | **Degenerate.** 1 or 0, as feature 0. |
| 5 | `syn_ratio` | SYN count / packets | **Constant 0.** No dump in any live run carried `tcp_flags`, and the parser will not invent it. |
| 6 | `bytes_rate_norm` | `log1p(min(bytes/s, 3e8)) / log1p(3e8)` | Real, same caveat on duration. |

Measured on the 23,526 flows of live run 3 (audit report §7): 52% of submitted
flows had zero packets; mean `connection_rate` was 0.0609 against a training
mean of 3.5594; mean `bytes_rate_norm` 0.0431 against 0.3756.

**Scaling.** `(x − mean) / std` with fixed statistics loaded once from
`ML/GraphSage-model/inference_stats.pt` (`graph_builder.py:107-128`), falling
back to the constants at `:101-102` if the file cannot be read. That fallback
is silent (`except Exception: pass`).

**The attack-type heuristic**, `infer_attack_type`
(`threat_analyzer.py:35-74`), evaluated in this order over the source's flows in
this poll:

1. port 22 among the destination ports **and** more than 250 packets in total → `SSHBrute`
2. five or more distinct destination ports → `PortScan`
3. more than 1,000,000 bytes to ports 80, 443 or 8080 → `DoSHulk`
4. more than 5000 packets in total, **or** a score of 0.90 or more → `DDoS`
5. anything else → **`Botnet`**

It is not a model output. v1 says malicious or not, nothing more.

**Threshold.** 0.75. The source's score is its single highest-scoring flow, so
**one flow over 0.75 in one poll blocks the source immediately**
(`threat_analyzer.py:94`). There is no confirmation count, no cooldown and no
averaging over polls.

**Known behaviour on live traffic: it blocks benign hosts.** In two live runs
it blocked 7 of 10 and 9 of 10 hosts; five of them during a phase that held
only benign pings and web fetches (audit report §1, §14 A1). Offline, with the
three features forced to their OVS constants, the number of sources over the
threshold that sent no attack flow rose from 11 to 31
(`MODEL_BEHAVIOUR.md` §1.2). What it responds to is a completed TCP
conversation, whoever sends it (`mininet/demo/DEMO_SETUP.md`).

**The fallback.** If the weights fail to load, or a forward pass throws, v1
switches to `_heuristic_score` (`inference_service.py:134-135`, `:153-156`,
`:204-221`) and keeps going. Incidents from it carry the reason
`HEURISTIC_DEGRADED`, and they block hosts just the same.

---

## 5. v2: GATv2

**Architecture.** `GraphSentinelNet`
(`ML/graphsentinel_v2/graphsentinel/models/net.py`): hosts are nodes, flows are
edges. Two GATv2 layers with four heads and edge features, 128 hidden, residual
blocks, jumping-knowledge concatenation, port and protocol embeddings, a 64-d
per-host memory that is untrained, and two heads: an edge head (per flow) and a
node head (per host). 654,851 parameters. The backend reads **only** the edge
head; the node head's test binary F1 is 0.4475 and it is never read. Classes,
in contract order (`ML/model_card.json` → `outputs.classes`):
`BENIGN, Volumetric_Flood, PortScan, BruteForce, Botnet`.

**The 20 edge features** (`ML/model_card.json` → `inputs.edge_features.names`)
and what an OVS dump can supply (`flow_mapping.py:23-37`):

| Group | Features | Live value |
|---|---|---|
| Filled (10) | `log_duration_s`, `log_total_packets`, `log_total_bytes`, `avg_packet_size`, `log_dt_since_pair`, `log_dt_since_src`, `window_position`, `direction_flag`, `log_bytes_per_s`, `log_packets_per_s` | Derived from the flow. The three timing features take poll-shaped values, because every flow in a poll shares one timestamp. |
| Pinned (2) | `fwd_packet_ratio`, `byte_asymmetry` | Constant **1.0** and **+1.0**: everything is put on the forward side (`flow_mapping.py:144-147`). |
| Zero (8) | `log_max_fwd_len`, `log_max_bwd_len`, `log_iat_mean`, `iat_burstiness`, `syn_ratio`, `rst_ratio`, `ack_ratio`, `psh_ratio` | **0.0**. The columns are absent and the builder zero-fills; the flag ratios are 0 because `tcp_flags` is 0. |

All 16 node features survive, provided the byte and timestamp mappings stay
(`flow_mapping.py:5-21`).

**Windows.** 60 s, non-overlapping, closed when a later record crosses the
boundary. A window needs at least 8 edges to be scored
(`min_edges_per_graph`); below that it is returned `unscored`, which is
reported and is not "clean".

**Policy floors** (`mitigation_policy.py:83-137`). A rule also needs the
source host's node threat to reach 0.60 (`sdn.py:284-289`).

| Class | Floor | Action | Status |
|---|---:|---|---|
| `Volumetric_Flood` | 0.90 | `meter` (rate-limit to 1000 kbps) | Enforceable in policy; dry-run |
| `BruteForce` | 0.85 | `drop_port` | Enforceable in policy; dry-run |
| `PortScan` | 0.85 | `alert_only` | Never a rule, since 2026-10-05 |
| `Botnet` | 1.01 | `alert_only` | Disabled. A floor above 1.0 cannot be reached. |

`BENIGN` has no entry and must not have one.

**Dry-run.** Nothing from v2 reaches an incident, a block, the chain or the
frontend's incident list. `SDNTranslator.install` raises outside dry-run
(`sdn.py:189-199`), and the backend discards any window whose service reports
`dry_run=False` (`analysis_pipeline_v2.py:82-85`). The only trace on the
dashboard is the header badge `v2: DRY-RUN / OFF / NO ANSWER / UNKNOWN`.

**Known behaviour on live traffic: about half of benign flows are called
attacks.** In run 2's benign-only window 202 of 400 flows were predicted as an
attack class; in run 3's, 329 of 652. Of run 2's 13 admitted rules, 11 were on
benign web fetches or their replies and none was on the flood. The wrong
predictions were confident enough to clear the 0.90 floor
(`MODEL_BEHAVIOUR.md` §1.3). Three runs of one script on one topology: an
observation, not a rate.

---

## 6. Mininet and OVS integration

### The enforcement daemon

`backend/scripts/enforcement_daemon.py` runs as root in WSL and listens on TCP
`127.0.0.1:50051` (`DAEMON_HOST`, `DAEMON_PORT`). It exits at start if
`DAEMON_TOKEN` is not set (`:19-21`). Each connection sends one JSON object.
`handle_request` (`:83-148`):

- compares `payload["token"]` with its `DAEMON_TOKEN`; a mismatch returns
  `{"status": "error", "error": "Unauthorized"}`;
- accepts only switches `s1`, `s2`, `s3`;
- `dump_flows` → runs `sudo ovs-ofctl dump-flows s1` and returns
  `{"status": "success", "output": <the raw text>}`. With `DAEMON_DUMP_LOG` set
  it also appends that exact text to a file, under a timestamp;
- `block` → `ovs-ofctl add-flow s1 priority=1000,ip,nw_src=<ip>,actions=drop`;
- `unblock` → `ovs-ofctl del-flows s1 ip,nw_src=<ip>`.

For `block` and `unblock` it re-validates the IP against `MININET_CIDR` itself.

### The parser

`_parse_output` (`flow_parser.py:88-154`) reads the dump line by line.

- A line with `nw_src=` **and** `nw_dst=` is an IP flow. The protocol is
  `ICMP`, `TCP` or `UDP` by substring, otherwise `IP`. Ports come from
  `tp_src=` / `tp_dst=` and default to 0, which is right for ICMP.
- A line with `arp_spa=` and `arp_tpa=` is kept as protocol `ARP`. **ARP is
  not dropped**; older notes say it is. The headless topology sets
  `autoStaticArp=True`, so in the demo there are none.
- Anything else is skipped: the header line, a table-miss rule, **IPv6**
  (`ipv6_src=` is not handled), and the backend's own drop rules, which have
  `nw_src` but no `nw_dst`.
- `tcp_flags` is taken only if the dump prints one. It does not; the value is 0.

The output dict is the one in section 3, step 1. Note what one conversation
looks like in the table: **two entries, one per direction**, each with its own
counters. The reply direction is a separate flow whose source is the server.
That is how a victim ends up scored and blocked as a source.

### Re-submission

The monitor submits the **whole table on every poll**. The parser keeps no
state between polls: it does not diff against the previous dump, and it does
not read `idle_age`, which the dump does print. `ovs-testcontroller` installs
each entry with `idle_timeout=60`, so an entry stays in the table for up to a
minute after its last packet, with frozen counters and a growing `duration`.
Effects:

- A conversation is scored by v1 on every poll for as long as its entry lives.
  That is why unblocking a host straight after its attack does not stick
  (BE-08).
- v2 receives each conversation several times per 60 s window, with cumulative
  counters. Measured in run 3: between 1.16 and 9.17 times per window
  (`ML/live_loop_run3.json`, `resubmission_factor`).
- `flow_snapshots` receives one row per entry per poll.

### The topology

`mininet/topologies/base_topology_headless.py` starts one OVS switch `s1` in
`secure` fail mode, an `OVSController` (`ovs-testcontroller`), and ten hosts
`h1`–`h10` at `10.0.0.1`–`10.0.0.10`, pings h2 → h1 once, and then sleeps until
it is signalled. It has no CLI, so it can run detached.

The demo uses it instead of the scripts in
`mininet/topologies/attack_scripts/` because each of those builds and tears
down its **own** network: they cannot attach to a running one (the switch name
`s1` collides), and when one ends the switch is gone and the backend's polls
fail (audit A7).

### The demo attacks

`mininet/demo/attacks/` enters a host's namespace of the running topology with
`mnexec -a <pid>` (`_hosts.py`); on Windows the command is sent into WSL as
root. `mininet/demo/run_demo.py` runs the three in sequence after a preflight
that refuses to start if the backend's last poll failed.

| Attack | From → to | What it sends | Label in the tested run |
|---|---|---|---|
| `flood.py` | h2 → h1:80 | 2000 HTTP requests, a new TCP connection each | `DDoS` |
| `portscan.py` | h3 → h1, ports 20–30 | a TCP connect to each of 11 ports (nmap if installed) | `PortScan` |
| `bruteforce.py` | h4 → h1:22 | 300 short TCP connections | `SSHBrute` |

Each attack **opens the port it needs on h1** for its own duration
(`_hosts.py:102-114`). That is required, not cosmetic. Nothing listens on any
port in the stock topology, a refused connection leaves a table entry with
almost no packets, and v1 scores such a source far under 0.75. The measured
scores are in the attack modules' docstrings: closed-port scan 0.004, closed
port 22 0.007, ping flood 0.02, against 0.77–0.93 with the ports open.
`mininet/demo/tested_run.txt` confirms the outcome: with open ports, three
attacks gave three incidents; the same three against closed ports or as a ping
flood gave **no incident for any attacker** (`:39-40`).

---

## 7. Bugs and open items

BE-01 to BE-08 are items already recorded in `OPEN_ITEMS.md` or the audit
report. BE-09 to BE-16 are things I found while reading; none is recorded
elsewhere yet.

### BUG BE-01 (open item 4, step 1): Replay run 3 with each conversation submitted once
**File:** `ML/retrain_logs/live_loop/daemon_responses_run3.txt`; `backend/app/mininet_monitor/flow_parser.py:88` (`_parse_output`); `backend/app/services/flow_mapping.py:181` (`map_flows`)
**What is wrong:** On live traffic v2 labels about half of benign flows as attacks, and the cause has not been separated. One candidate is re-submission: the same conversation arriving up to nine times in a window. It has been counted, not removed. If benign fetches are still labelled attacks when each conversation is submitted once, re-submission is not the cause.
**How to reproduce:** No live run is needed. The file holds 59 daemon answers, each under a header line `=== <UTC timestamp> dump_flows s1 (returned to caller)`. For each block call `_parse_output(text)`; `ML/retrain_logs/live_loop/assemble_run_3.py` already imports it and shows how to set up the path. Key each flow by `(src_ip, dst_ip, src_port, dst_port, protocol)`; within each 60 s window keep one record per key, the last one seen, with the header's timestamp as `observed_at`. Send the result through `map_flows` and `POST /flows` to a freshly started inference service with `MitigationPolicy.wire()` as the policy, the way `ML/live_rule_check.py` does. Compare the benign-only window (the one starting at 1791145860 in `ML/live_loop_run3.json`) with the recorded 329 of 652.
**What done / what remains:** Counted. The replay is not written. **This is the first of the two next steps.**

### BUG BE-02 (open item 4, step 2): Score the committed sample with the features forced to their OVS values
**File:** `ML/b08_ovs_constants_check.py` (the v1 equivalent to copy); `backend/app/services/flow_mapping.py:120-178`; `ML/testdata/cicids2017_sample.csv`
**What is wrong:** An OVS dump fills 10 of v2's 20 edge features; 2 are pinned and 8 are zero (section 5). Nobody has measured what that does to v2's benign-versus-attack decision. `OPEN_ITEMS.md` calls it the most likely source of the benign-as-attack labelling.
**How to reproduce:** No live run is needed. Score the labelled sample twice through the inference service: once as it is, once with every row reduced to what `map_flow` can emit. That means `Total Backward Packets = 0` and `Total Length of Bwd Packets = 0` with the totals moved to the forward columns (which pins `fwd_packet_ratio` to 1.0 and `byte_asymmetry` to +1.0), and the columns for the eight zeroed features removed: both maximum packet lengths, the inter-arrival columns, and the SYN, RST, ACK and PSH flag counts. Report how many **benign** flows are predicted as an attack class in each run, and how many clear their floor. Before writing it, read `ML/phase2b_live_path_cost.py`: its "degraded" variant already forces "features the live path cannot supply" on this sample and reports a macro-F1 change (`MODEL_BEHAVIOUR.md` §7). What that script does not report is the number this item needs, the benign-as-attack count; it may be the quickest place to add it.
**What done / what remains:** Listed, not measured. **This is the second next step, after BE-01.** Do not move the 0.90 floor before both are done; `OPEN_ITEMS.md` is explicit about that.

### BUG BE-03 (open item 5): A chain write can be made twice when the timeout fires before broadcast
**File:** `backend/app/services/blockchain_adapter.py:121-136`; `backend/app/services/threat_analyzer.py:236-239`; `backend/app/services/reconciliation.py:286-296`
**What is wrong:** `store_incident` runs the chain client in a worker thread and waits 5 s. The thread cannot be stopped. If the 5 s runs out **before** the client has broadcast the transaction, the adapter has no hash to return and returns `status: 'pending'` with `tx_hash: None` (`:134-136`). The analyzer stores that as `retry`. Meanwhile the worker thread is still running, and may broadcast a moment later. Ten seconds on, the reconciler picks up the row, sees no hash, and submits the incident again (`reconciliation.py:290-296`). The contract accepts both. One incident, two on-chain records. The case where the timeout fires **after** broadcast is fixed (commit `b811d20`): the client reports the hash as soon as it has sent, and the adapter returns it.
**How to reproduce:** A test with a mock client whose `log_incident` sleeps longer than the adapter's timeout before it "broadcasts", then check how many times it was called after one reconciler pass. `backend/tests/test_b05_broadcast_hash.py` has the three tests for the fixed half to copy from.
**What done / what remains:** The intended fix is decided: **make the consumer idempotent and leave the send path alone.** Before the reconciler resubmits a row that has no hash, it looks on chain for an incident whose `forensicsURI` is `local://incident/<id>` and adopts it if one exists. The fix goes in `reconcile_blockchain_outbox`, between line 286 (`target = db.get(...)`) and line 290 (`result = adapter.store_incident(...)`). The lookup already exists: `adapter.client.get_all_incidents()` returns `forensics_uri` for every incident (`web3_client.py:299`). It is O(N) with two RPC calls per incident, which is acceptable in the 10 s worker and not on a request path; scan recent incidents only. **One hazard to design for:** the URI is built from the SQLite row id (`web3_client.py:150`). The chain persists across runs (Ganache's `--db`, the Compose volume) and SQLite ids restart at 1 whenever the database is new, so `local://incident/1` can already exist on chain from an earlier database. Match on `source_ip` and `attack_type` as well, and require the on-chain timestamp to be no earlier than the row's `created_at`. The same retry path is reached from manual blocks (`api/v1/blocked.py:179-182`), so one fix covers both. Skanda has the contract side of this in BLOCKCHAIN.md.

### BUG BE-04 (open item 6): A second `live_rule_check.py` run against the same service gives a different answer
**File:** `ML/live_rule_check.py`; `ML/live_rule_check.json`
**What is wrong:** Against a freshly started inference service the script scores the committed sample as the documented 58 windows and 12 rules. Run again against the **same running process**, it reported one window and one rule.
**How to reproduce:** Start the inference service, run the script twice without restarting the service, and compare.
**What done / what remains:** Observed on 2026-10-05 and not investigated. **The cause is unknown.** The engine does keep state between requests: a flow buffer, the current window boundary, a per-host history and the host memory (`engine.py:146-148`). That is a place to look, not a diagnosis. Workaround until it is understood: restart the inference service before `python ML/verify_stack.py` if checks 8 and 9 are to show the documented counts. `RUN_GUIDE.md` §6 should say so once the cause is known.

### BUG BE-05 (open item 13): The monitor keeps nothing of a scored v2 window
**File:** `backend/app/mininet_monitor/monitor.py:292-297`
**What is wrong:** `score_flows` returns every closed window with its per-flow verdicts, the rules admitted and the flows withheld. `_score_v2` reads two keys from that result, `reason` and `closed_windows`, and lets the rest go out of scope at line 297. What is lost: which flows were scored, the class and confidence of each, each rule's source, destination, port, action and confidence, and the withheld counts by reason. `/health` shows counters only. The first live run could not say which flows its rules were on.
**How to reproduce:** Run the stack with v2 on and traffic flowing; query `/health` after a window closes. `monitor.v2_windows_closed` goes up; nothing says what was in the window.
**What done / what remains:** Since 2026-10-05 `_rules_for` logs one INFO line per rule, with class, action, source, destination, port, protocol, confidence, floor and policy digest (`analysis_pipeline_v2.py:92-96`), and one per withheld class and reason (`:97-99`). **That log is the only record**, and it does not include the per-flow verdicts. If rules are ever to drive anything, or to be shown, they need to be kept somewhere a person or a test can read: a table, or a bounded in-memory list served by an endpoint.

### BUG BE-06 (open item 2): The backend's health window has not been checked under load
**File:** `docker-compose.yml:169-179`
**What is wrong:** Compose gives the backend a `start_period` of 180 s to become healthy. That number was chosen on an idle machine, as was the 75 it replaced. On a busy machine the backend may take longer than that and be marked unhealthy.
**How to reproduce:** Start the stack while the machine is busy (a build running, or the memory pressure this machine has anyway) and time from `docker compose up` to `healthy`.
**What done / what remains:** `RUN_GUIDE.md` §4 states that the value was chosen idle. The measurement is not done. For the presentation the manual path avoids the question.

### BUG BE-07 (audit A1): v1 blocks benign hosts on live traffic
**File:** `backend/app/services/inference_service.py:133-181`; `backend/app/services/graph_builder.py:44-78`; `backend/app/services/threat_analyzer.py:94`
**What is wrong:** On live OVS input v1 scores ordinary hosts over 0.75 and the analyzer blocks them at once. Evidence, from the audit report §14 A1: in one live run 7 incidents, 5 on hosts that had sent only benign pings and fetches, the first 11 s after benign traffic began; in the next, 9 of 10 hosts blocked, including the flood's victim. `mininet/demo/tested_run.txt` shows the other side of the same behaviour: with **no** background traffic, exactly the three attackers were blocked and nobody else.
**How to reproduce:** Start the demo stack, run a loop of `curl` between two hosts that are not attacking, and watch the blocked list.
**What done / what remains:** Not fixed, and no model or threshold change is recommended on two runs. **Demo workaround: run no benign background traffic, and keep `ENFORCEMENT_MODE=simulated`.** Say what v1 is if asked: it flags completed TCP conversations.

### BUG BE-08 (audit A2): A blocked host produces no new incident, and an unblock does not stick
**File:** `backend/app/services/threat_analyzer.py:109-111`, `:167-173`
**What is wrong:** `evaluate` skips any source already in `blocked_ips`. That is correct in itself: without it every new minute produced another incident for the same host. The consequence is that a second attack from an already-blocked host shows nothing. The stock scripts in `mininet/topologies/attack_scripts/` attack from `10.0.0.2` three times, so only the first would appear. The reverse also bites: unblock a host while its flows are still in the switch's table (up to 60 s) and v1 scores them again on the next poll and blocks it again. `tested_run.txt:33-35` shows it: `10.0.0.2` blocked at 04:49:47, unblocked at 04:50:10, blocked again at 04:50:14, this time with a score of 0.94.
**How to reproduce:** Run `flood.py` twice in a row without unblocking; the second run adds no incident. Or run `run_demo.py` with `--api-key` and read the incident table afterwards.
**What done / what remains:** The demo scripts work round both: **each attack uses a different host** (h2, h3, h4), so the sequence never depends on an unblock. If you need to reuse a host, unblock it and wait more than 60 s. A real fix would be a short grace period after a manual unblock.

### BUG BE-09: If Ganache is down when the backend starts, the chain never comes back
**File:** `backend/app/services/blockchain_adapter.py:22-26`, `:61-69`; `backend/app/services/reconciliation.py:162-164`
**What is wrong:** `BlockchainAdapter` connects once, in its constructor, and `_connect` is called from nowhere else. If Ganache is not reachable at that moment, or `CONTRACT_ADDRESS` is empty or stale, `_connected` stays false for the life of the process. `store_incident` then returns `offline` immediately for every incident, and the reconciler returns `{"status": "offline"}` on its first line and retries nothing. Starting Ganache afterwards changes nothing; the `retry` rows wait for a backend restart. In the live runs all 16 incidents ended in `retry` this way.
**How to reproduce:** Start the backend, then Ganache, then run an attack. `/health` → `blockchain.connected` stays `false` and the incident has no hash.
**What done / what remains:** Not recorded before. Open. Either retry `_connect` from the reconciliation worker when not connected, or keep the rule and make it loud: **start Ganache and deploy the contract before the backend, and restart the backend after every redeploy** (the deploy script rewrites `CONTRACT_ADDRESS` in `backend/.env`, which is read only at startup). `run_demo.py`'s preflight does not check `blockchain.connected`; it would be a two-line addition.

### BUG BE-10: A poll of more than 5000 table entries is thrown away whole
**File:** `backend/app/services/analysis_pipeline.py:14-15`; `backend/app/mininet_monitor/monitor.py:345-347`; `backend/app/config.py:61`
**What is wrong:** `analyze_flows` raises `ValueError` when given more than `max_analyze_flows` flows. That limit was written for the HTTP endpoint, but the monitor calls the same function. The exception is caught by the monitor's outer handler, which prints `[Monitor] Tick error` and sleeps. Nothing was scored by v1, the graph was not updated, no events were sent, and v2 was never offered the flows, because `_score_v2` comes after the line that raised. This repeats on every poll until the table shrinks. The demo flood opens 2000 connections; each is two table entries, so the flood alone is about 4000, inside the limit but not by much. The tested run did not hit it. I have not measured the peak table size, so whether a larger `--count` or two overlapping attacks would cross 5000 is unverified.
**How to reproduce:** `sudo python3 mininet/demo/attacks/flood.py --count 3000` and watch the backend's console for `Tick error: Too many flows`.
**What done / what remains:** Not recorded before. Open. For the demo, keep the flood at its default 2000 and do not overlap attacks. A fix is to exempt the monitor from the limit, or to score the first N and say so.

### BUG BE-11: One slow chain write stalls the whole poll loop
**File:** `backend/app/services/threat_analyzer.py:142-148`; `backend/app/services/blockchain_adapter.py:121-124`; `backend/app/mininet_monitor/monitor.py:327-328`
**What is wrong:** The chain write is synchronous, inside `evaluate`, inside the monitor thread, with a 5 s wait per incident. The socket events for that poll are emitted only after `analyze_flows` returns. So if Ganache is reachable but slow, each new incident holds the poll for up to 5 s, the dashboard's `alert` and `healing_triggered` pushes arrive late, and several incidents in one poll add up. When Ganache is simply down this does not happen: the adapter returns at once.
**How to reproduce:** A mock client that sleeps 4 s in `log_incident`, three sources over the threshold in one batch, and time `analyze_flows`.
**What done / what remains:** Not recorded as its own item (it is the other face of B05). Open. The outbox already exists: the incident could be left as `retry` and written by the reconciler, which would take the chain off the detection path entirely.

### BUG BE-12: If the v1 model fails to load, a hand-written formula blocks hosts instead
**File:** `backend/app/services/inference_service.py:102-107`, `:134-135`, `:153-156`, `:204-221`
**What is wrong:** With the defaults (`REQUIRE_ML_MODEL=false`, `DEMO_ALLOW_MOCK_ML=true`) a missing weights file, a missing PyTorch Geometric or a failed forward pass does not stop anything. `predict` returns scores from `_heuristic_score`, a formula over packets, bytes per second and port. Those scores go through the same threshold and block the same way; the only marks are `ml.mode: "degraded"` in `/health`, the reason `HEURISTIC_DEGRADED` on the enforcement action, and a `HEURISTIC SCORING` badge on the dashboard.
**How to reproduce:** Rename `ML/GraphSage-model/graphsage_weights.pt`, start the backend, and read `/health` → `ml`.
**What done / what remains:** By design, and visible in three places, but easy to miss on the day. **Before the demo, confirm `/health` → `ml.mode` is `"model"`.** `run_demo.py`'s preflight prints it (`run_demo.py:78`) and `verify_stack.py` checks it.

### BUG BE-13: `/forensics` drops the forensics URI, reports every record as confirmed, and blocks the event loop
**File:** `backend/app/api/v1/forensics.py:18-34`, `:61-65`; `backend/app/models/schemas.py:300-311`
**What is wrong:** Three things in one endpoint. `_normalize_chain_record` copies eleven fields from each on-chain record and leaves out `forensics_uri`, which the client does return, so the frontend's "Forensics URI" line is always blank. It also writes `"status": "confirmed"` for every record, overwriting the real receipt status the client worked out, so the frontend's `pending` and `failed` filters can never match. And the handler is `async def` but calls `get_all_incidents()` directly: a filter creation plus two RPC calls per on-chain incident, on the event loop, on every request (audit B10). The frontend polls this endpoint every 10 s from the shell, every 5 s from the Forensics page and every 3 s from the modal.
**How to reproduce:** With a few incidents on chain, `GET /api/v1/forensics` and look at `blockchain_records[0]`: no `forensics_uri`, `status` always `confirmed`.
**What done / what remains:** B10 is recorded in `AUDIT_2026-10-04.md` and held. The two field problems are not recorded. Add `forensics_uri` to `ChainRecord` and to the normaliser, pass `raw.get("status")` through, and move the chain read into `run_in_threadpool`. Susheep's FE-13 and Skanda's lookup for BE-03 both want the URI.

### BUG BE-14: Changing the threshold from Settings does not move the node colours or severities
**File:** `backend/app/services/graph_state.py:28-35`; `backend/app/services/threat_analyzer.py:23-28`; `backend/app/api/v1/settings_route.py:45-54`
**What is wrong:** `PATCH /settings` sets `settings.threat_threshold`, and the analyzer reads it for the block decision. But node status (`malicious` at 0.75, `suspicious` at 0.50) and the severity label (`critical` at 0.75) are hard-coded constants. The comment in the route says the change moves "graph_state severity banding"; it does not. Lower the threshold to 0.60 and a host scoring 0.65 is blocked while its node, before the block lands, is still drawn as merely suspicious and its alert is labelled `warning`.
**How to reproduce:** Set the threshold to 0.60 from Settings and send a flow that scores between 0.60 and 0.75.
**What done / what remains:** Not recorded before. Low priority. Do not change the threshold during the demo and it cannot show.

### BUG BE-15: In `ovs` mode an unblock deletes more than the drop rule
**File:** `backend/scripts/enforcement_daemon.py:129`
**What is wrong:** The block adds `priority=1000,ip,nw_src=<ip>,actions=drop`. The unblock runs `ovs-ofctl del-flows s1 ip,nw_src=<ip>`, which is a loose match: it removes **every** IP flow with that source, including the controller's per-conversation entries for that host. Those are re-learned on the next packet, so traffic recovers, but their counters restart and the host's history in the table is gone.
**How to reproduce:** Only in `ovs` mode, which no run has exercised (audit report §10). `dump-flows` before and after an unblock.
**What done / what remains:** Not recorded before. Low priority while the demo stays in `simulated`. A strict delete would name the priority: `--strict del-flows s1 priority=1000,ip,nw_src=<ip>`.

### BUG BE-16: Every poll writes the whole flow table to SQLite
**File:** `backend/app/services/graph_state.py:247-272`
**What is wrong:** `_persist_snapshots` inserts one `flow_snapshots` row for every flow of every poll, then runs the retention cleanup, all in the monitor thread. Because of re-submission the same conversation is written on every poll while its entry lives. Run 3 submitted 23,526 flows in about five minutes. Retention is 24 h (`flow_snapshot_retention_hours`). During a flood that is some thousands of inserts every 5 s, on the same thread that has to keep polling.
**How to reproduce:** Run the flood and `SELECT COUNT(*) FROM flow_snapshots` before and after.
**What done / what remains:** Not recorded before. Not a correctness problem; a growth and timing one. The only reader of these rows is the restart rehydration, which wants the last 15 s.

---

## 8. API surface

All application routes are under `/api/v1`, registered in
`backend/app/main.py:147-160`. "Any" means any signed-in session or either API
key; "write" means anything except the `readonly` role; "admin" means the admin
role or the admin API key (`backend/app/api/v1/deps.py`).

**F** = the frontend polls it every 10 s. **D** = `run_demo.py` calls it.

| File | Method and path | Auth | What it does | |
|---|---|---|---|---|
| `main.py` | `GET /health` | none | Status of v1, v1's settings, v2, the chain, the monitor and reconciliation. | F, D |
| `auth.py` | `POST /api/v1/auth/login` | none, rate-limited (10 per 5 min per IP) | Checks the operator or read-only credentials, returns a session token and role. | |
| `auth.py` | `POST /api/v1/auth/logout` | token | Ends the session. | |
| `auth.py` | `GET /api/v1/auth/me` | token | Username and role of the session. | |
| `analyze.py` | `POST /api/v1/analyze` | write, rate-limited (30 per min per IP) | Runs v1's whole pipeline on submitted flows: scores, incidents, blocks, chain writes, socket events. | |
| `analyze.py` | `POST /api/v1/ml/reload` | admin | Reloads the v1 weights. | |
| `graph.py` | `GET /api/v1/graph` | any | Current nodes and links. | F |
| `stats.py` | `GET /api/v1/stats` | any | Counts, health percentage, enforcement mode, demo flag. | F |
| `timeline.py` | `GET /api/v1/timeline?last=60min` | any | Incidents and blocks in five-minute buckets. `last` accepts `Nmin`, up to 1440. | F |
| `alerts.py` | `GET /api/v1/alerts?limit=50&severity=` | any | Incidents as alerts, newest first, with triage state. | F |
| `blocked.py` | `GET /api/v1/blocked` | any | The `blocked_ips` table. | F, D |
| `blocked.py` | `POST /api/v1/block` | admin | Body `{ip, action: "block" \| "unblock", reason}`. Blocks or unblocks, writes a `Manual` incident row, writes to the chain, audit-logs it. | D (unblock) |
| `healing.py` | `GET /api/v1/healing?limit=50` | any | Block actions joined to their incidents. | F |
| `incidents.py` | `PATCH /api/v1/incidents/{id}/status` | write | Sets triage to `open`, `acknowledged` or `resolved`. | |
| `forensics.py` | `GET /api/v1/forensics?limit=100&offset=0` | any | Incidents from SQLite with chain status, plus every on-chain record. See BE-13. | F |
| `blockchain.py` | `POST /api/v1/blockchain/store` | write | Writes one incident to the chain directly. Nothing in the app calls it. | |
| `settings_route.py` | `GET /api/v1/settings` | any | Threshold, enforcement mode, chain URL and address, v2's read-only gate. | |
| `settings_route.py` | `PATCH /api/v1/settings` | admin | Sets `threat_threshold`, in memory only. | |
| `enforcement_actions.py` | `GET /api/v1/enforcement-actions?limit=100&ip_address=` | any | The append-only block and unblock log. | F |
| `audit.py` | `GET /api/v1/audit-logs?limit=50&offset=0` | admin | Who did what. | |

Socket.IO: a client must present a session token in `auth.token` or an API key
header to connect (`main.py:204-214`). The server emits `connected` to the new
client and broadcasts `graph_update`, `alert` and `healing_triggered`
(`websocket/events.py`). It accepts no client events.

There is **no endpoint for v2's output.** Its windows, verdicts and rules are
not served anywhere (BE-05).

---

## 9. How the two models are used together, honestly

- **Both models run on every poll.** v1 always; v2 in addition, when
  `GS2_ENABLED` is true and every flow in the poll came from OVS.
- **v1 acts. v2 advises, in dry-run.** v1's score creates the incident, the
  block and the chain record. v2's rules are logged and discarded.
- **There is no routing and no decision layer.** No code chooses a model per
  attack, compares the two results, or lets one confirm the other. They read
  the same flows and never meet (`monitor.py:327`, `:337`).
- **v1 is binary.** The attack type on screen is `infer_attack_type`, not a
  model output.
- **Neither is a validated detector on live traffic.** v1 blocks benign hosts;
  v2 labels half of benign flows as attacks. What the demo shows is the
  mechanism: a threshold crossed, a host blocked (simulated), an incident
  recorded, the dashboard updated.

What to say in the presentation, word for word from
`mininet/demo/DEMO_SETUP.md`, "What to say about the labels":

> - The model that acts is binary. **The attack type on the dashboard is a
>   port and volume heuristic, not a model output.** Say this before the first
>   label appears.
> - "DDoS": the heuristic's name for a source with more than five thousand packets.
>   It is one host flooding another, not a distributed attack.
> - "SSHBrute": port 22 and more than 250 packets. Anything the heuristic does not
>   match is called "Botnet"; if that label appears, it is the fall-through.
> - The `v2: DRY-RUN` header badge: v2 runs beside v1 and only advises. Its rules
>   are logged, not enforced, and not shown in the incident list.
> - Accuracy figures on the landing page are offline results on the 2017 CICIDS
>   dataset. They are not a property of this live demo; do not quote them as one.
> - If asked whether v1 detects attacks: it flags completed TCP conversations. It
>   flagged ordinary web fetches in testing, and it does not see a ping flood or a
>   scan of closed ports. What the demo shows is the mechanism: threshold crossed,
>   host blocked (simulated), incident recorded, dashboard updated.

The tested demo run was v1 only, with v2 off to save memory, no Ganache, and no
browser (`DEMO_SETUP.md`, "Tested"). Running it with v2 on, with the chain, in
front of the dashboard has not been done once. Do that rehearsal on the
presentation machine before anything else in this file.

# GraphSentinel — Naming Map

One concept, several names. This is the map of what each object is called at
each hop between the switch, the backend, the chain and the dashboard. It comes
from Phase 10 of the 2026-10-04 integration audit (`AUDIT_2026-10-04.md`), read
from the code, not from a run. Read it before changing a field name or adding a
consumer.

It describes the **v1 path** (`MODEL_BEHAVIOUR.md` §1.1) unless a row says v2.

## Objects and who handles them

| Object | Producer | Consumer | Key fields | Validation | Known failure mode |
|---|---|---|---|---|---|
| Flow | `flow_parser._parse_output`, frontend `simulateAttack` | `analyze_flows` | `src_ip`, `dst_ip`, ports, `packet_count`, `byte_count`, `duration_sec` (seconds), `data_source` | `FlowRecord` (IPv4 only) | One malformed flow fails the batch |
| Feature vector | `graph_builder._feature_row` | GraphSAGE (v1) | 7 floats | NaN/Inf zeroed | Three features are constants on OVS data (audit B08) |
| Model graph | `build_pyg_graph` | `InferenceService.predict` | `x` N×7, `edge_index` 2×E | Empty handled | Falls back to the heuristic |
| Prediction | `InferenceService.predict` | `ThreatAnalyzer`, `graph_state` | `flow_scores`, `ip_scores`, `source_scores`, `mode` | None | The mode key is `mode`; `analyze_flows` re-exports it as `ml_mode` (audit B03) |
| Incident | `ThreatAnalyzer._create_incident` | alerts, forensics, reconciler | int `id`, `source_ip`, `threat_score`, `severity` 1–10 | Idempotency key, per minute | Duplicates across minutes unless the host is already blocked (audit B02) |
| Alert | `_alert_record`, `/alerts` | store `alerts` | `id` = `alert-<n>`, `severity` string | `AlertRecord` on REST only | Socket copy lacks the triage fields |
| Healing event | `SelfHealingEngine._healing_event`, `/healing` | store `healingEvents` | `ip`, `trigger_score`, `enforcement_status` | `HealingEvent` on REST only | Different ids on socket and REST (audit B33) |
| Chain tx | `BlockchainClient.log_incident` | incident row, `/forensics` | `tx_hash`, `incident_id`, `status` | Receipt + event | Duplicate on timeout (audit B05, open) |
| Graph (UI) | `graph_state.graph_response` | `setGraphData` | `nodes[id=ip]`, `links[source,target,value]` | `GraphResponse` on REST | Socket copy truncated to 50 nodes / 100 links |

The model graph and the UI graph are different graphs. In the model graph a node
is one **flow**; in the UI graph a node is one **IP**.

## Same concept, different names

| Concept | Names in use | Where they differ |
|---|---|---|
| Host address | `src_ip`, `source_ip`, `ip`, `ip_address`, `sourceIP`, node `id` | flow · incident and alert · healing event · `BlockedIP` and enforcement log · contract · UI graph |
| Score | `score`, `threat_score`, `trigger_score`, link `value` | flow score · incident and alert · healing event · UI graph link |
| Severity | string label (`critical` / `warning` / `info`) and integer 1–10 | alerts carry the label; incidents and the chain carry the integer |
| Attack label | `attack_type`, `attackLabel`, `attack_class` | backend · contract · v2 |
| Inference mode | `mode`, `ml_mode` | `InferenceService.predict` and `/health` use `mode`; the `/analyze` response uses `ml_mode` |
| Timestamp | ISO string without a zone, ISO string with a zone, epoch seconds, epoch float | `/alerts` `acknowledged_at` · `/forensics` · chain · v2 (which also uses microsecond durations) |
| Protocol | name string, IANA number | v1 · v2 |
| Tx hash | with `0x`, without `0x` | pending path · confirmed path (hexbytes 1.3.1; audit B30). The reconciler accepts both |

## Thresholds that should be one number and are not

| Where | Value | Configurable |
|---|---|---|
| Block decision, `ThreatAnalyzer` | `THREAT_THRESHOLD` — 0.75 in every tracked file | yes |
| Alert severity, `threat_analyzer.score_to_severity_label` | 0.75 → `critical`, 0.50 → `warning`, below → `info` | **no**, hard-coded (audit B24) |
| Node status, `graph_state.severity_status` | 0.75 → `malicious`, 0.50 → `suspicious`, below → `normal` | **no**, hard-coded (audit B24) |

When the threshold is set below 0.50, the backend blocks hosts at a score whose
alert is labelled `info` and whose node would otherwise be drawn `normal`. The
untracked `backend/.env` on the development machine sets 0.40 (`RUN_GUIDE.md` §3).

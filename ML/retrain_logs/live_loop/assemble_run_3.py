"""Assemble the third live run's evidence from the files it wrote. Run from the
repository root. The daemon's own responses are parsed with the project's own
flow_parser, so 'flows the parser produced' is computed, not asserted."""
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

G = Path("C:/dev/gs_live")
REPO = Path("C:/dev/GraphSentinal")
os.environ.setdefault("SQLITE_PATH", str(Path(tempfile.gettempdir()) / "gs_assemble.db"))
os.chdir(REPO / "backend")
sys.path.insert(0, str(REPO / "backend"))
from app.mininet_monitor.flow_parser import _parse_output  # noqa: E402

LIVE = REPO / "ML" / "retrain_logs" / "live_loop"


def text(name):
    return (G / name).read_text(encoding="utf-8", errors="replace").replace("\x00", "").replace("\r\n", "\n")


dumps_raw = text("daemon_dumps_run3.txt")
(LIVE / "daemon_responses_run3.txt").write_text(dumps_raw, encoding="utf-8", newline="\n")
(LIVE / "traffic_manyflow.sh").write_text(text("traffic_manyflow.sh"), encoding="utf-8", newline="\n")
log_lines = [l for l in text("backend_run3.log").splitlines() if l.strip()]
v2 = [l for l in log_lines if "graphsentinel" in l]
health = json.loads(text("run3_health.json"))
m, c = health["monitor"], health["ml_v2"]["client"]

# what the parser makes of each response the daemon returned
responses = []
for block in dumps_raw.split("=== ")[1:]:
    head, _, body = block.partition("\n")
    t = datetime.strptime(head.split()[0], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).timestamp()
    flows = _parse_output(body)
    responses.append((t, flows))
parsed_total = sum(len(f) for _, f in responses)
assert all(f["data_source"] == "ovs" for _, fl in responses for f in fl)

FETCH = {("10.0.0.7", "10.0.0.3", "80"), ("10.0.0.8", "10.0.0.3", "80"),
         ("10.0.0.9", "10.0.0.1", "80"), ("10.0.0.10", "10.0.0.1", "80")}


def kind(src, dst, port):
    if (src, dst, port) in FETCH:
        return "benign_http_fetch"
    if (src, dst, port) == ("10.0.0.5", "10.0.0.4", "22"):
        return "bruteforce_shaped_connections"
    if src in ("10.0.0.2", "10.0.0.5") and (dst, port) == ("10.0.0.3", "80"):
        return "flood"
    if src == "10.0.0.1" and dst == "10.0.0.2":
        return "reply_to_port_scan"
    if src in ("10.0.0.1", "10.0.0.3") and int(port) > 1024:
        return "reply_to_benign_http_fetch"
    return "other"


rules = []
for l in v2:
    r = re.search(r"window \[(\d+),\d+\]: rule (\S+)/(\S+) on (\S+) -> (\S+?):(\d+) proto \d+, confidence ([0-9.]+)", l)
    if r:
        w, cls, act, src, dst, port, conf = r.groups()
        rules.append({"window_start": int(w), "attack_class": cls, "action": act, "src_ip": src, "dst_ip": dst,
                      "dst_port": port, "confidence": float(conf), "what_it_was": kind(src, dst, port)})
by_kind = Counter(r["what_it_was"] for r in rules)

windows = []
for w, n, pred in re.findall(r"window \[(\d+),\d+\]: scored (\d+) flow\(s\) from \d+ host\(s\); predicted (\{.*?\})", "\n".join(v2)):
    w, n, pred = int(w), int(n), json.loads(pred.replace("'", '"'))
    below = sum(int(x) for x in re.findall(rf"window \[{w},\d+\]: withheld (\d+) Volumetric_Flood flow\(s\): below_floor", "\n".join(v2)))
    inwin = [f for t, fl in responses if w <= t < w + 60 for f in fl]
    keys = {(f["src_ip"], f["dst_ip"], f["src_port"], f["dst_port"], f["protocol"]) for f in inwin}
    flood = {k for k in keys if k[0] in ("10.0.0.2", "10.0.0.5") and k[1] == "10.0.0.3" and k[3] == 80}
    vf = pred.get("Volumetric_Flood", 0)
    windows.append({
        "window_start": w, "scored_by_backend": n, "predicted": pred, "predicted_attack": n - pred.get("BENIGN", 0),
        "flows_parsed_from_daemon_responses_in_window": len(inwin),
        "distinct_conversations": len(keys), "flood_conversations": len(flood),
        "resubmission_factor": round(n / max(len(keys), 1), 2),
        "volumetric_flood_predicted": vf, "volumetric_flood_below_floor": below,
        "volumetric_flood_at_or_above_floor": vf - below,
        "rules_admitted": sum(1 for r in rules if r["window_start"] == w),
    })

summary = {
    "what": "third live run: as run 2 with ONE change, the flood sent as many conversations (a new source port per "
            "packet, from two hosts) instead of one. Derived from ML/retrain_logs/live_loop_run3.txt and the "
            "daemon's own responses.",
    "route": "B: local WSL2, Mininet with the OVS kernel datapath, no Docker; live polling, not a replay",
    "labels": "by construction: the traffic script knows what it sent. Not a dataset.",
    "backend_started_with_log_config": False,
    "raw_input": "ML/retrain_logs/live_loop/daemon_responses_run3.txt: every dump_flows answer as the daemon "
                 "returned it to the backend (DAEMON_DUMP_LOG), not a parallel capture",
    "daemon_responses": len(responses),
    "flows_parsed_from_daemon_responses": parsed_total,
    "flows_admitted_by_gate": m["v2_provenance"]["flows_admitted"],
    "batches_admitted_by_gate": m["v2_provenance"]["batches_admitted"],
    "batches_refused_non_ovs": m["v2_provenance"]["batches_refused_non_ovs"],
    "polls": m["poll_counts"],
    "windows_closed": m["v2_windows_closed"], "windows_unscored": c["windows_unscored"],
    "flows_sent": c["flows_sent"], "flows_dropped_in_mapping": c["flows_dropped_in_mapping"],
    "policy_sha256": health["ml_v2"]["policy"]["sha256"], "dry_run": health["ml_v2"]["policy"]["dry_run"],
    "rules_admitted": len(rules),
    "rules_by_what_the_flow_was": {k: by_kind.get(k, 0) for k in
                                   ("benign_http_fetch", "reply_to_benign_http_fetch", "reply_to_port_scan",
                                    "bruteforce_shaped_connections", "flood", "other")},
    "rules_by_class": dict(Counter(r["attack_class"] for r in rules)),
    "flood_rule_confidences": sorted(r["confidence"] for r in rules if r["what_it_was"] == "flood"),
    "benign_fetch_rule_confidences": sorted(r["confidence"] for r in rules if r["what_it_was"] == "benign_http_fetch"),
    "windows": windows,
    "totals": {k: sum(wd[k] for wd in windows) for k in
               ("scored_by_backend", "predicted_attack", "distinct_conversations", "flood_conversations",
                "volumetric_flood_predicted", "volumetric_flood_below_floor", "volumetric_flood_at_or_above_floor")},
    "rules": rules,
}
(REPO / "ML" / "live_loop_run3.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="")

out = []
w = out.append
w("GraphSentinel -- the live loop, third run: the flood sent as many conversations")
w("=" * 78)
w("")
w("Same route, machine, topology, daemon and services as ML/retrain_logs/live_loop_run.txt.")
w("ONE variable changed in the traffic: the flood. Runs 1 and 2 sent it as a single")
w("conversation (fixed source port); this run sends 500 SYNs from each of two hosts")
w("with a new source port per packet, so the controller installs one table entry each.")
w("Diff of the traffic scripts: ML/retrain_logs/live_loop/traffic.sh against traffic_manyflow.sh.")
w("")
w("Three things differ in how the run was evidenced, all from code changed after run 2:")
w("  * the backend was started with NO --log-config; its graphsentinel.* INFO lines")
w("    print by default now (backend/app/logging_setup.py);")
w("  * the provenance gate logs admissions (first, then once a minute);")
w("  * the raw input is the daemon's own responses (DAEMON_DUMP_LOG), byte for byte")
w("    what flow_parser was given, in ML/retrain_logs/live_loop/daemon_responses_run3.txt.")
w(f"    Parsed again with flow_parser._parse_output they give {parsed_total} flows, every one")
w(f"    tagged 'ovs'; the gate reports {m['v2_provenance']['flows_admitted']} flows admitted.")
w("")
w("TRAFFIC (UTC, from the generator's own log)")
for l in text("traffic_run3.log").splitlines():
    w("  " + l)
w("")
w("THE BACKEND'S OWN LOG (every graphsentinel.* line, and startup)")
w("-" * 78)
for l in log_lines:
    if "FlowParser" not in l:
        w(l)
w("")
w("/health AFTER THE RUN")
w("-" * 78)
w(json.dumps({"poll_counts": m["poll_counts"], "v2_provenance": m["v2_provenance"],
              "v2_windows_closed": m["v2_windows_closed"], "v2_last_error": m["v2_last_error"],
              "client": {k: c[k] for k in ("windows_seen", "windows_unscored", "flows_sent",
                                           "flows_dropped_in_mapping", "last_error")},
              "policy_sha256": health["ml_v2"]["policy"]["sha256"],
              "policy_alert_only": health["ml_v2"]["policy"]["alert_only"], "v1": health["v1"]}, indent=2))
w("")
w("PER WINDOW (ML/live_loop_run3.json has the same)")
w("-" * 78)
for wd in windows:
    w(f"  {wd['window_start']}: scored {wd['scored_by_backend']}, distinct conversations {wd['distinct_conversations']} "
      f"(flood {wd['flood_conversations']}), predicted attack {wd['predicted_attack']}, "
      f"VF at/above floor {wd['volumetric_flood_at_or_above_floor']} of {wd['volumetric_flood_predicted']}, "
      f"rules {wd['rules_admitted']}")
w("")
w("WHAT THE RULES WERE MADE ON")
w("-" * 78)
for k, n in summary["rules_by_what_the_flow_was"].items():
    w(f"  {n:>3}  {k}")
w(f"  confidence of the rules on the flood:        {summary['flood_rule_confidences']}")
w(f"  confidence of the rules on benign fetches:   {summary['benign_fetch_rule_confidences']}")
(REPO / "ML" / "retrain_logs" / "live_loop_run3.txt").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")

print(json.dumps({k: summary[k] for k in ("daemon_responses", "flows_parsed_from_daemon_responses", "flows_admitted_by_gate",
                                          "polls", "windows_closed", "rules_admitted", "rules_by_what_the_flow_was",
                                          "flood_rule_confidences", "benign_fetch_rule_confidences", "totals")}, indent=1))
for wd in windows:
    print({k: wd[k] for k in ("window_start", "scored_by_backend", "flows_parsed_from_daemon_responses_in_window", "distinct_conversations", "flood_conversations", "resubmission_factor", "predicted_attack", "volumetric_flood_at_or_above_floor", "rules_admitted")})
print("dump bytes", len(dumps_raw))

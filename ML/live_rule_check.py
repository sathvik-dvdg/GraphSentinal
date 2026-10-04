"""What the wired mitigation policy does on real flows, through the live service.

Sends ML/testdata/cicids2017_sample.csv to a running inference container with
the backend's validated policy (``MitigationPolicy.wire()``), exactly as the
backend does, and records:

  * whether every window echoed the policy's digest;
  * the rules admitted (dry run) and the flows withheld, by class and reason;
  * each admitted rule's true label, joined back on the 5-tuple;
  * per true class, how many correct predictions reach the policy's floor.

Run from the repository root with the inference container up
(``docker compose up -d inference``):

    PYTHONPATH="backend;ML/graphsentinel_v2" python ML/live_rule_check.py

(``backend:ML/graphsentinel_v2`` on Linux.) Writes ML/live_rule_check.json.
The sample is a small, 91%-benign slice: figures from it carry their counts.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx
import pandas as pd

from app.config import settings
from app.services.mitigation_policy import build_policy
from app.services.model_contract import load_contract
from graphsentinel.config import Config
from graphsentinel.data import preprocess as pre

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "ML" / "testdata" / "cicids2017_sample.csv"
OUT = REPO / "ML" / "live_rule_check.json"
URL = "http://localhost:8081"

# The label map follows the active taxonomy: set the card's before mapping.
Config.from_dict(json.loads((REPO / "ML" / "model_card.json").read_text(encoding="utf-8"))["config"])
policy = build_policy(load_contract(settings.resolved_gs2_model_dir))
wire, digest = policy.wire(), policy.wire_sha256()

raw = pd.read_csv(SAMPLE, low_memory=False, encoding="latin-1")
raw.columns = [str(c).strip() for c in raw.columns]
truth = raw["Label"].astype(str).str.strip().map(pre.RAW_LABEL_MAP)
raw = raw[truth.notna()].copy()
raw["Label"] = truth[truth.notna()]
ts = pre._parse_timestamps(raw["Timestamp"], fix_12h=True, pm_hours=[1, 7])
raw = raw[ts.notna()].assign(t=ts[ts.notna()].to_numpy(dtype="datetime64[s]").astype("int64"))
raw = raw.sort_values("t", kind="mergesort")
records = json.loads(raw.drop(columns=["Timestamp"]).to_json(orient="records"))

results = []
with httpx.Client(timeout=300) as c:
    contract = c.get(f"{URL}/contract").json()
    for i in range(0, len(records), 2000):
        r = c.post(f"{URL}/flows", json={"flows": records[i:i + 2000], "policy": wire})
        r.raise_for_status()
        results += r.json()["results"]
    last = c.post(f"{URL}/flush", json={"policy": wire}).json()["result"]
    results += [last] if last else []


def key(s, d, sp, dp, pr):
    return (str(s), str(d), int(sp), int(dp), int(pr))


truth_by: dict = {}
for r in records:
    truth_by.setdefault(key(r["Source IP"], r["Destination IP"], r["Source Port"],
                            r["Destination Port"], r["Protocol"]), set()).add(r["Label"])

admitted, withheld = Counter(), defaultdict(Counter)
rules = []
for w in results:
    for rule in w["rules"]:
        t = truth_by.get(key(rule["src_ip"], rule["dst_ip"], rule["src_port"],
                             rule["dst_port"], rule["protocol"]), set())
        admitted[f"{rule['attack_class']}:{rule['action']}"] += 1
        rules.append({"attack_class": rule["attack_class"], "action": rule["action"],
                      "confidence": round(rule["confidence"], 4),
                      "policy_floor": rule["policy_floor"], "true_label": sorted(t)})
    for cls, by in w["withheld_summary"].items():
        for reason, n in by.items():
            withheld[cls][reason] += n

verdicts = []
for w in results:
    for f in w["flows"]:
        t = truth_by.get(key(f["src_ip"], f["dst_ip"], f["src_port"], f["dst_port"], f["protocol"]), set())
        verdicts.append((next(iter(t)) if len(t) == 1 else None, f["attack_class"], f["confidence"]))
df = pd.DataFrame(verdicts, columns=["true", "pred", "conf"])
per_class = {}
for cls, entry in wire.items():
    d = df[df["true"] == cls]
    ok = d[d["pred"] == cls]
    per_class[cls] = {
        "true_flows": int(len(d)),
        "predicted_as": {k: int(v) for k, v in d["pred"].value_counts().items()},
        "correct": int(len(ok)),
        "correct_conf_p50": None if ok.empty else round(float(ok["conf"].median()), 4),
        "policy_floor": entry["min_conf"],
        "correct_at_or_above_floor": int((ok["conf"] >= entry["min_conf"]).sum()),
    }

report = {
    "what": "the wired mitigation policy on the Phase 2b sample, through the live inference service",
    "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "sample": {"path": "ML/testdata/cicids2017_sample.csv",
               "sha256": hashlib.sha256(SAMPLE.read_bytes()).hexdigest(), "flows_sent": len(records)},
    "service_contract_version": contract.get("contract_version"),
    "policy_sha256": digest,
    "windows": len(results),
    "windows_echoing_the_policy_digest": sum(w["policy_sha256"] == digest for w in results),
    "dry_run_on_every_window": all(w["dry_run"] for w in results),
    "rules_admitted": dict(admitted),
    "rules": rules,
    "withheld": {c: dict(v) for c, v in withheld.items()},
    "per_true_class": per_class,
    "unmatched_or_ambiguous_verdicts": int(df["true"].isna().sum()),
    "note": ("Dry run: no rule was installed. One rule covers a (source, destination, "
             "protocol) pair per window, so admitted rules are far fewer than flows above "
             "the floor. Small, 91%-benign slice: not the test split."),
}
OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: report[k] for k in ("windows", "windows_echoing_the_policy_digest",
                                          "rules_admitted", "withheld")}, indent=1))
for cls, p in per_class.items():
    print(f"  {cls:<17s} correct {p['correct']:>4} of {p['true_flows']:>4}; "
          f">= floor {p['policy_floor']}: {p['correct_at_or_above_floor']}")
print(f"wrote {OUT}")

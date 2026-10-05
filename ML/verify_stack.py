"""The ten checks of RUN_GUIDE.md section 6, against a running stack.

Works the same on the Docker Compose path and the manual path, because both
publish the inference service on 8081 and the backend on 8001.

    python ML/verify_stack.py                 # from the repository root
    python ML/verify_stack.py --skip-sample   # checks 1-7 only (seconds)

Checks 1-9 are about v2, the audited model, which blocks nothing. Check 10 reads
back what v1 -- the path that does block -- is configured to do, and fails if
that differs from the tracked defaults. It scores nothing.

Checks 8 and 9 send the committed sample (18,264 flows) through the inference
service with the backend's policy, via ML/live_rule_check.py, and take about a
minute. They need the backend and ML packages importable; this script sets
PYTHONPATH for that itself.

A check has three outcomes. UNVERIFIABLE means the thing it reads was not there
to be read -- checks 5 and 6 describe the loaded model, and the service serves
its model card whether or not a model is in memory -- so it is neither a pass
nor evidence of a fault of its own. Exit code 0 only if every check passes.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INFER = os.environ.get("GS_INFER_URL", "http://localhost:8081")
BACKEND = os.environ.get("GS_BACKEND_URL", "http://localhost:8001")
CLASSES = ["BENIGN", "Volumetric_Flood", "PortScan", "BruteForce", "Botnet"]
TIMEOUT = 120
results: list[tuple[str, bool | None, str]] = []


def get(url: str):
    """(status, body). A service that answers with an error, or does not answer,
    is a failed check with its reason, never a traceback: without ML/weights.pt
    the inference service answers 503 by design."""
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            status, raw = r.status, r.read()
        try:
            body = json.loads(raw.decode("utf-8"))
        except ValueError:
            return status, {"detail": f"answered HTTP {status} with a body that is not JSON: {raw[:60]!r}"}
        if not isinstance(body, dict):
            return status, {"detail": f"answered HTTP {status} with JSON that is not an object"}
        return status, body
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            body = {}
        return exc.code, body if isinstance(body, dict) else {}
    except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
        return None, {"detail": f"no answer: {exc!r}"}


STATE = {True: "PASS", False: "FAIL", None: "UNVERIFIABLE"}


def check(name: str, ok: bool | None, detail: str) -> None:
    """``ok`` None is UNVERIFIABLE: what the check reads was not there to read."""
    ok = None if ok is None else bool(ok)
    results.append((name, ok, detail))
    print(f"  [{STATE[ok]}] {name}: {detail}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-sample", action="store_true")
    args = ap.parse_args(argv)
    results.clear()
    print(f"inference {INFER} | backend {BACKEND}")

    # 1. the inference service is OURS, not just something answering 200
    status, h = get(f"{INFER}/health")
    loaded = status == 200 and "model_dir" in h and "memory" in h
    check("1 inference /health", loaded,
          f"HTTP {status}, model_dir {h.get('model_dir')!r}"
          + (f" -- {h['detail']}" if h.get("detail") else ""))
    _, card = get(f"{INFER}/contract")
    check("2 inference /contract", card.get("contract_version") == "2.0.0",
          f"contract_version {card.get('contract_version')}"
          + (f" -- {card['detail']}" if card.get("detail") else ""))

    status, bh = get(f"{BACKEND}/health")
    v2 = bh.get("ml_v2") or {}
    policy = v2.get("policy") or {}
    check("3 backend /health lists the policy", status == 200 and bool(policy.get("floors")),
          (f"HTTP {status}, enforceable {policy.get('enforceable')}, alert_only "
           f"{policy.get('alert_only')}, floors {policy.get('floors')}") if policy else
          (f"HTTP {status}, ml_v2 = {v2} -- the v2 path is off; see RUN_GUIDE.md section 4"
           if status == 200 else f"HTTP {status} -- {bh.get('detail', 'no health from the backend')}"))

    manifest = json.loads((REPO / "ML" / "MANIFEST.json").read_text(encoding="utf-8"))
    want = next(f["sha256"] for f in manifest["files"] if f["file"] == "weights.pt")
    served = (card.get("artifacts") or {}).get("weights", {}).get("sha256")
    weights = REPO / "ML" / "weights.pt"
    on_disk = hashlib.sha256(weights.read_bytes()).hexdigest() if weights.exists() else None
    check("4 weights identity", served == want == on_disk,
          f"served card {str(served)[:16]}, MANIFEST {want[:16]}, ML/weights.pt {str(on_disk)[:16]}"
          + ("" if served else " -- the file matches the manifest, but nothing is serving it"
             if want == on_disk else ""))
    # 5 and 6 are facts about the model in memory, read from the card. The card
    # is served with no model loaded, so without check 1 they would pass on a
    # model that is not there.
    absent = " -- read from the card; no model is loaded (check 1), so this describes nothing running"
    params = card.get("parameters")
    check("5 parameter count", (params == 654851) if loaded else None,
          (f"{params:,}" if isinstance(params, int) else "not served") + ("" if loaded else absent))
    classes = (card.get("outputs") or {}).get("classes")
    check("6 class order",
          (classes == CLASSES == (v2.get("contract") or {}).get("classes")) if loaded else None,
          (", ".join(classes) if isinstance(classes, list) else "not served") + ("" if loaded else absent))
    check("7 dry_run", (policy.get("dry_run") is True) if policy else None,
          f"backend policy.dry_run = {policy.get('dry_run')}"
          + ("" if policy else " -- the backend published no policy (check 3)"))

    if args.skip_sample:
        print("  checks 8 and 9 skipped (--skip-sample)")
    else:
        out = Path(tempfile.gettempdir()) / "gs_live_rule_check.json"
        env = dict(os.environ, PYTHONIOENCODING="utf-8", GS_LIVE_RULE_OUT=str(out),
                   PYTHONPATH=os.pathsep.join([str(REPO / "backend"),
                                               str(REPO / "ML" / "graphsentinel_v2")]))
        run = subprocess.run([sys.executable, str(REPO / "ML" / "live_rule_check.py")],
                             cwd=REPO, env=env, capture_output=True, text=True)
        if run.returncode != 0:
            reason = (run.stderr.strip().splitlines() or ["no output"])[-1]  # the exception, not its traceback
            check("8 policy digest echo", False, f"live_rule_check.py failed: {reason[:300]}")
            check("9 rules admitted / withheld", None, "not run: the sample could not be scored (check 8)")
        else:
            r = json.loads(out.read_text(encoding="utf-8"))
            echoed = r["windows_echoing_the_policy_digest"]
            check("8 policy digest echo",
                  echoed == r["windows"] and r["policy_sha256"] == policy.get("sha256")
                  and r["dry_run_on_every_window"],
                  f"{echoed} of {r['windows']} windows echoed {r['policy_sha256'][:16]}, "
                  f"backend publishes {str(policy.get('sha256'))[:16]}")
            wrong = [x for x in r["rules"] if x["true_label"] != [x["attack_class"]]]
            check("9 rules admitted / withheld",
                  sum(r["rules_admitted"].values()) > 0 and not wrong,
                  f"admitted {r['rules_admitted']}, on a wrong or benign flow: {len(wrong)}; "
                  f"withheld {r['withheld']}")

    # 10. v1 is the path that creates incidents and blocks hosts. Two stacks
    # can pass checks 1-9 identically while running v1 at different thresholds,
    # so read back what it is running with and compare to the tracked template.
    tracked = {}
    for line in (REPO / "backend" / ".env.example").read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() in ("THREAT_THRESHOLD", "ENFORCEMENT_MODE"):
            tracked[key.strip()] = value.split("#")[0].strip()
    v1 = bh.get("v1") or {}
    same = None if status != 200 else (
            v1.get("threat_threshold") is not None
            and abs(float(v1["threat_threshold"]) - float(tracked["THREAT_THRESHOLD"])) < 1e-9
            and v1.get("enforcement_mode") == tracked["ENFORCEMENT_MODE"])
    check("10 v1 threshold and enforcement mode", same,
          f"running threshold {v1.get('threat_threshold')}, mode {v1.get('enforcement_mode')!r}; "
          f"tracked default {tracked['THREAT_THRESHOLD']}, {tracked['ENFORCEMENT_MODE']!r}"
          + {True: "", False: " -- v1 is not running the tracked configuration (RUN_GUIDE.md section 3)",
             None: " -- the backend did not answer, so what v1 runs with is unknown"}[same])

    failed = [n for n, ok, _ in results if ok is False]
    unverifiable = [n for n, ok, _ in results if ok is None]
    print(f"\n{len(results) - len(failed) - len(unverifiable)} of {len(results)} checks passed"
          + (f"; FAILED: {failed}" if failed else "")
          + (f"; UNVERIFIABLE: {unverifiable}" if unverifiable else "")
          + ("; NOT RUN: checks 8 and 9 (--skip-sample)" if args.skip_sample else ""))
    return 1 if failed or unverifiable else 0


if __name__ == "__main__":
    sys.exit(main())

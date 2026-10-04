"""Load the retrained artefacts the way the inference service does, and score a
fixed synthetic window. Run in the container (torch 2.4.0) and locally; the
probability vectors must agree across versions."""
import hashlib, json, platform, sys
from pathlib import Path

import numpy as np
import torch

model_dir = Path(sys.argv[1])
import pandas, torch_geometric
from graphsentinel.inference.engine import InferenceEngine

man = json.loads((model_dir / "MANIFEST.json").read_text(encoding="utf-8"))
card = json.loads((model_dir / "model_card.json").read_text(encoding="utf-8"))
want = {f["file"]: f["sha256"] for f in man["files"]}
got = hashlib.sha256((model_dir / "weights.pt").read_bytes()).hexdigest()

eng = InferenceEngine.from_artifacts(model_dir, threat_threshold=0.5)
n_params = sum(p.numel() for p in eng.model.parameters())

rng = np.random.default_rng(0)
recs = [{
    "Source IP": f"10.0.0.{1 + i % 6}",
    "Destination IP": f"10.0.1.{1 + (i * 3) % 4}",
    "Source Port": int(rng.integers(1024, 65535)),
    "Destination Port": int(rng.integers(1, 1024)),
    "Protocol": 6, "t": 1_500_000_000 + i,
    "Flow Duration": float(rng.integers(100, 5_000_000)),
    "Total Fwd Packets": int(rng.integers(1, 50)),
    "Total Backward Packets": 0,
    "Total Length of Fwd Packets": float(rng.integers(60, 50_000)),
    "Total Length of Bwd Packets": 0.0,
} for i in range(40)]
eng.ingest(recs)
res = eng.flush()
probs = np.array([[f.class_probs[c] for c in card["outputs"]["classes"]] for f in res.flows])

print(json.dumps({
    "python": platform.python_version(), "torch": torch.__version__,
    "torch_geometric": torch_geometric.__version__, "pandas": pandas.__version__,
    "numpy": np.__version__,
    "weights_sha256_matches_manifest": got == want["weights.pt"],
    "parameters": n_params, "card_parameters": card["parameters"],
    "classes": card["outputs"]["classes"],
    "dry_run": eng.translator.dry_run,
    "scored_flows": len(res.flows), "unscored": res.unscored,
    "probs": probs.round(6).tolist(),
}))

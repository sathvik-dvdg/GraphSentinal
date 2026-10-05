# GraphSentinel v2

Graph-based network intrusion detection on CICIDS2017. **Nodes are hosts, edges
are flows.**

A rewrite of the v1 training notebook, addressing a code review that identified
twelve defects. Each one is fixed in code, and where a fix is *not* fully
possible on this dataset that is stated rather than papered over.

---

## Before anything else: you need the right CICIDS2017

CICIDS2017 ships in two distributions **with identical filenames**:

| distribution | columns | first column | has IPs? |
|---|---|---|---|
| `MachineLearningCSV.zip` → `MachineLearningCVE/` | 79 | `' Destination Port'` | **no** |
| `GeneratedLabelledFlows.zip` → `TrafficLabelling_/` | 85 | `Flow ID` | **yes** |

v1 was pointed at the first one. That is *why* it made flow rows into nodes —
there were no addresses in the data to make nodes out of, so the graph was built
out of row adjacency instead. You need the second.

Download `GeneratedLabelledFlows.zip` from
<https://www.unb.ca/cic/datasets/ids-2017.html> and drop the same five filenames
into the same folder. `graphsentinel.data.schema` checks this at startup and
fails with instructions rather than degrading silently.

---

## Quick start

```bash
pip install torch torch-geometric pandas pyarrow scikit-learn
pip install onnx onnxscript onnxruntime   # optional, for ONNX export
pip install fastapi uvicorn               # optional, for the service

# train
python -m graphsentinel.train --base-dir /path/to/GraphSentinel --epochs 60

# other split protocols
python -m graphsentinel.train --split temporal
python -m graphsentinel.train --split attack_holdout      # zero-day
python -m graphsentinel.train --split host_holdout        # new-attacker

# no data yet? synthesise a CICIDS2017-shaped capture with real attack topology
python tests/make_synthetic.py --out /tmp/gs/datasets/cicids2017
python -m graphsentinel.train --base-dir /tmp/gs --epochs 12
```

**On Colab:** open `notebooks/GraphSentinel_Colab_Execution.ipynb`. It mounts
Drive, auto-detects your project folder (`GraphSentinel` or `GraphSentinelV2`),
installs deps, validates the dataset variant, trains with per-epoch checkpoints
on Drive so an OOM restart costs one epoch, and gives you a granular RESET cell.
`GraphSentinel_v2_Training.ipynb` is the shorter driver.

---

## The twelve fixes

| # | defect | fix | where |
|---|---|---|---|
| 1 | Flows as nodes; synthetic edges from row adjacency and shared ports | Nodes are IPs, edges are flows carrying features. Port scan = one node to many; botnet = many to one; DDoS = many to one at volume | `data/graph_builder.py` |
| 2 | Rigid 500-flow windows fragment low-and-slow attacks | Time windows + a persistent GRU memory per host, carried across window boundaries, plus `dt_pair`/`dt_src` gap features computed globally | `models/memory.py`, `data/graph_builder.py` |
| 3 | `aggr='mean'` dilutes one malicious neighbour among 99 benign; scalar class weights only scale gradient magnitude | GATv2 attention (or median aggregation) + focal loss with effective-number alpha + degree reweighting + node/edge consistency | `models/layers.py`, `losses.py` |
| 4 | Binary output collapses five structurally opposite attacks | 6-way multi-class, node head **and** per-flow edge head | `models/net.py` |
| 5 | Tethered to offline CSVs | Streaming engine + replay / CICFlowMeter / scapy sources + FastAPI service | `inference/` |
| 6 | `port / 65535.0` — false similarity (22 vs 23), false distance (80 vs 8080) | Learned embeddings over a curated port vocabulary with bucketed ephemeral tail | `data/ports.py`, `models/layers.py` |
| 7 | `in_channels=7` frozen by a backend `import` | Model card + HTTP service + TorchScript/ONNX; compat shim for migration | `export.py`, `models/compat.py` |
| 8 | `scaler.pkl` fitted once offline; drift → false positives | EMA scaler with warm start, drift alarms, and an anti-poisoning clamp | `inference/ema_scaler.py` |
| 9 | Per-file 70/15/15 splits one attack burst across train and test | Four protocols, none of which cuts a burst; missing-class warnings | `data/preprocess.py` |
| 10 | 3 bare SAGEConv layers over-smooth a dense window | 2 layers + residuals + Jumping Knowledge + LayerNorm | `models/net.py` |
| 11 | `for i in range(n)` + `.iloc[i]` per row | Fully vectorised — **measured 80x** faster than the v1 loop | `data/graph_builder.py` |
| 12 | Raw logit is unusable by an SDN controller | Per-flow verdicts → OpenFlow rules with exact 5-tuple matches, per-class mitigation, safety rails | `inference/sdn.py` |

Plus four bugs found while reading v1 that the review did not mention:

- `input("Resume? [y/n]")` inside the training cell — hangs any unattended run.
- `scaler.pkl` was fitted on 15 raw flow features but the model consumed 7
  derived node features, so it could not be applied at inference at all. v1's
  own contract document admitted this while still exporting it.
- Graph/split boundary alignment relied on `len(df) // window_size` matching the
  order graphs were built in — a silent misalignment if either changed.
- Accuracy / weighted-F1 / ROC-AUC targets are all satisfiable by a model that
  never detects a botnet.

---

## Layout

```
graphsentinel/
  config.py                 all hyperparameters; serialises into every checkpoint
  losses.py                 focal + degree-aware + node/edge consistency
  train.py                  training loop (no input() prompts)
  evaluate.py               macro F1, PR-AUC, recall@FPR, evasion ablation
  export.py                 model card, TorchScript, ONNX, artefact hashes
  data/
    schema.py               CICIDS2017 variant detection; fails loudly
    preprocess.py           vectorised load/clean + four split protocols
    graph_builder.py        IP-as-node / flow-as-edge, vectorised
    ports.py                port + protocol vocabularies
  models/
    net.py                  GraphSentinelNet
    layers.py               categorical encoder, conv factory, residual block
    memory.py               bounded three-tier host memory
    compat.py               v1 shim + LegacyBinaryAdapter
  inference/
    engine.py               stateful streaming inference
    ema_scaler.py           adaptive scaling with drift detection
    sdn.py                  detections -> OpenFlow rules
    capture.py              replay / CICFlowMeter / scapy sources
    service.py              FastAPI microservice
  ood.py                    open-set rejection: projection, Mahalanobis
                            mixture, cascade/blended scores, adaptive conformal
  models/recon.py           joint self-supervised heads: masked edge-attribute,
                            degree-matched link, structural profile
docs/
  MEMORY.md                 the memory-budget answer, with numbers
  BACKEND_CONTRACT.md       integration guide (replaces NODE_FEATURES.md)
  OPEN_SET.md               open-set results -- including what failed
tests/
  make_synthetic.py         CICIDS2017-shaped data with real attack topology
  test_pipeline.py          22 tests
  test_export_inference.py  7 tests
  test_ood.py               17 tests
  test_recon.py             7 tests
notebooks/
  GraphSentinel_Colab_Execution.ipynb   <- START HERE for Colab (36 cells,
                                           crash-safe, granular reset)
  GraphSentinel_v2_Training.ipynb       <- concise driver
```

---

## Tests

```bash
python -m pytest tests/ -v
```

53 tests. They check specific claims, not just that nothing throws:

- a port scanner's `dst_port_entropy` exceeds the 99th percentile of all other
  hosts — i.e. the graph really does encode scan topology
- a DDoS victim's `log_unique_src_ips` does the same for fan-in
- focal loss suppresses an easy example by >100x relative to a hard one
- effective-number alpha lifts the minority class **without** reaching the raw
  500:1 frequency ratio
- 100 000 distinct IPs pushed through `NodeMemory` do not grow the tensor
- the EMA scaler absorbs a modest baseline shift silently and clamps + alarms on
  a violent one
- the vectorised builder beats a faithful reproduction of the v1 row loop by
  >20x (measured ~80x)
- the wrong CICIDS2017 distribution raises with migration instructions
- TorchScript and ONNX exports reproduce eager outputs
- generated OpenFlow rules carry a real 5-tuple and a finite timeout
- allowlisted hosts never produce a drop rule
- `cholupdate` reproduces an explicit re-factorisation to 1e-9
- the EMA gate refuses to absorb the anomalies it is meant to flag, and the
  covariance does not ratchet shut on stationary input
- ACI holds its false-alarm target under drift where static conformal blows out
- OSCR penalises a detector that rejects knowns to look safe
- edge masking happens BEFORE encoding (otherwise reconstruction is an identity
  map), link negatives are degree-matched, and the eval path never masks

---

## Honest limitations

Worth reading before quoting any number from this.

**Episode splitting degrades on CICIDS2017.** Most attacks in the dataset are a
single continuous burst, so `episode` falls back to a chronological cut with a
dead zone and reports that it did. Where the fallback applies, the number means
*within-episode* generalisation. The zero-day claim must come from
`attack_holdout`, and the new-attacker claim from `host_holdout`.

**The memory is stateful windows, not a full TGN.** Per-host memory is updated
once per window rather than per event. This catches low-and-slow behaviour and
trains on a T4; it is not continuous-time. `models/memory.py` is the piece a
real TGN would replace.

**eBPF is an interface, not an implementation.** `capture.py` defines the
contract an eBPF ring-buffer reader would satisfy, and ships replay,
CICFlowMeter-tail and scapy sources. The kernel-side flow assembly must be
written in C — it is a deployment component, not a Python module. Above ~1 Gb/s
the scapy path is the bottleneck; use CICFlowMeter or eBPF.

**The SDN translator has never touched a real controller.** Rules are emitted as
OpenFlow 1.3 dicts and `ovs-ofctl` strings and are structurally valid, but
`dry_run=True` is the default and should stay that way until they have been
validated against your controller in a lab. Set `allow_networks` for gateways,
DNS and the controller itself before enabling enforcement.

**The open-set scorer is instrumentation, not an improvement.** Post-hoc
Mahalanobis on the JK embedding loses to the plain `1 - P(BENIGN)` baseline in
5 of 6 paired runs. It is wired into `attack_holdout` reporting so it stays
measured, not because it is recommended. `docs/OPEN_SET.md` has the numbers and
the reasoning, including two of my own earlier claims that failed replication.

**Joint reconstruction is on by default but unproven in magnitude.** It cut
open-set FPR@95TPR on the collapse family from 0.553 to 0.249 at zero closed-set
cost, and improved every scorer — but across 3 seeds the effect ranged from
−0.61 to −0.04, and one seed's OSCR moved the wrong way. Direction is
consistent; size is not established. Disable with
`cfg.model.recon_enabled = False`.

**Every number in the test suite comes from synthetic traffic.** The synthetic
generator reproduces attack *topology* faithfully, which is what the structural
tests need — but it is much cleaner than real traffic. Real CICIDS2017 numbers
will be lower, and that is the correct expectation, not a regression.

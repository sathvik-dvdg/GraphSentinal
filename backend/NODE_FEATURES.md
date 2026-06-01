
# GraphSentinel Node Feature Contract
# Author: Sathvik | Share with Sairaj for graph_builder.py
# ⚠️  Updated: IP-based node design was replaced — nodes are FLOWS, not IPs.
#     Read carefully before implementing graph_builder.py.

MODEL_INPUT_FEATURES = 7

# ── Graph structure ───────────────────────────────────────────────────────────
NODE  : Each network flow (one row of CICFlowMeter output) = one node
EDGES : Two types per window:
  1. Temporal chain  — flow[i] → flow[i+1]  (captures activity sequence)
  2. Port-same link  — flow[j] → flow[i] where j is the most recent prior
                       flow sharing the same Destination Port
                       (captures DDoS/SSHBrute/DoSHulk repeated-port patterns)

# ── Feature order (MUST match this exactly in graph_builder.py) ──────────────
  Index 0: fwd_ratio        = fwd_packets / (fwd_packets + bwd_packets + 1e-6)
  Index 1: avg_packet_size  = (fwd_bytes + bwd_bytes) / (total_packets + 1e-6)
  Index 2: connection_rate  = log1p(total_packets / flow_duration_sec)
  Index 3: port_norm        = destination_port / 65535.0
  Index 4: byte_asymmetry   = (fwd_bytes - bwd_bytes) / (total_bytes + 1e-6)
  Index 5: syn_ratio        = syn_flag_count / (total_packets + 1e-6), capped at 1.0
  Index 6: bytes_rate_norm  = log1p(min(Flow_Bytes_per_s, 3e8)) / log1p(3e8)

Source columns from CICFlowMeter CSV:
  fwd_packets    ← " Total Fwd Packets"
  bwd_packets    ← " Total Backward Packets"
  fwd_bytes      ← " Total Length of Fwd Packets"
  bwd_bytes      ← " Total Length of Bwd Packets"
  flow_duration  ← " Flow Duration"  (microseconds → divide by 1e6 for seconds, min 0.001)
  destination_port ← " Destination Port"
  syn_flag_count ← " SYN Flag Count"
  Flow_Bytes_per_s ← " Flow Bytes/s"

# ── Scaling (IMPORTANT — do NOT use scaler.pkl for node features) ─────────────
  Per-window z-score normalization is applied INSIDE graph construction,
  not via scaler.pkl. For each window of flows, after building the (N, 7)
  feature matrix x:

      mean = x.mean(dim=0, keepdim=True)
      std  = x.std(dim=0,  keepdim=True) + 1e-6
      x    = (x - mean) / std

  scaler.pkl (15-feature StandardScaler) is NOT used at inference time.
  It was fitted during preprocessing only and does not apply to these 7 features.

# ── Model ─────────────────────────────────────────────────────────────────────
  File  : ml/src/model.py
  Class : GraphSAGEClassifier       ← do NOT rename
  Import: from model import GraphSAGEClassifier
  Init  : GraphSAGEClassifier(in_channels=7, hidden_channels=256,
                               out_channels=2, num_layers=3)

# ── Loading weights ───────────────────────────────────────────────────────────
  import torch
  model = GraphSAGEClassifier(in_channels=7, hidden_channels=256,
                               out_channels=2, num_layers=3)
  model.load_state_dict(torch.load("graphsage_weights.pt", map_location="cpu"))
  model.eval()

# ── Inference ─────────────────────────────────────────────────────────────────
  probs = model.predict_proba(x_tensor, edge_index_tensor)
  # probs shape: (N,) — malicious probability for each flow node
  # Threshold: probs > 0.5 → malicious

# ── Files ─────────────────────────────────────────────────────────────────────
  graphsage_weights.pt → ml/models/graphsage_weights.pt
  scaler.pkl           → ml/models/scaler.pkl  (preprocessing only, not inference)
  NODE_FEATURES.md     → this file

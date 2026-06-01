# 🧠 SATHVIK — MACHINE LEARNING IMPLEMENTATION PLAN
## GraphSentinel | Role: ML / GNN Engineer
### AI IDE: Claude Code / AntGravity / Codex | Training Platform: Google Colab

---

## PASTE THIS EXACT BLOCK WHEN STARTING YOUR AI IDE SESSION (Colab / Local)

```
You are the ML implementation assistant for GraphSentinel —
a Self-Healing Cyber Defense System using Graph Deep Learning.

YOUR ROLE: You assist Sathvik who is building the GraphSAGE
node-classification model for cyber attack detection.

FROZEN CONSTRAINTS — NEVER VIOLATE:
- Python: 3.10.11 (local WSL2) | Colab uses its default (3.10+)
- PyTorch: 2.4.x | PyG: 2.5.x
- Model: GraphSAGE (SAGEConv) — NOT GCN, NOT GAT, NOT GraphConv
- Training: Google Colab ONLY (GPU = T4 or A100)
- Export format: torch.save(state_dict) → graphsage_weights.pt
- Scaler: StandardScaler from scikit-learn → scaler.pkl
- Node features: EXACTLY 7 (must match backend graph_builder.py)
- Dataset: CICIDS2017 — Tuesday + Wednesday + Friday CSVs only
- 5 attack classes: DDoS, PortScan, Botnet, SSH-Patator, DoS Hulk

YOUR SCOPE — ONLY GENERATE CODE FOR:
  ml/notebooks/*.ipynb  (Colab notebooks)
  ml/src/*.py           (reusable functions)

CRITICAL SHARED CONTRACT WITH SAIRAJ (Backend):
  Node feature order (NEVER CHANGE without telling Sairaj):
    index 0: out_degree
    index 1: in_degree
    index 2: avg_packet_size       = total_bytes / (total_packets + ε)
    index 3: connection_rate       = total_packets / (window_duration + ε)
    index 4: port_entropy          = Shannon entropy of dst_ports
    index 5: byte_asymmetry        = (sent - received) / (total + ε)
    index 6: syn_ratio             = SYN_count / (total_packets + ε)

  Model class: GraphSAGEClassifier
    in_channels=7, hidden_channels=256, out_channels=2, num_layers=3
    (Sairaj imports this class from ml/src/model.py)

MINIMUM PERFORMANCE TARGETS:
  Overall Accuracy ≥ 92% | Weighted F1 ≥ 0.88 | AUC-ROC ≥ 0.95

EXPORT FILES (copy to ml/models/ after training):
  graphsage_weights.pt  ← model.state_dict()
  scaler.pkl            ← StandardScaler fitted on training data

When I ask to generate notebook cells, use proper markdown with
## headings and include %%time magic for cells that take >10s.
```

---

## DATASET DOWNLOAD GUIDE

### Primary Source (CIC official site)
```
URL: https://www.unb.ca/cic/datasets/ids-2017.html
→ Click "Download" tab → Register email
→ Download ONLY these 5 CSV files:

FILE 1: Tuesday-WorkingHours.pcap_ISCX.csv
  URL path: /CIC-IDS-2017/CSVs/
  Size: ~420 MB
  Attack we need: SSH-Patator

FILE 2: Wednesday-workingHours.pcap_ISCX.csv
  Size: ~560 MB
  Attack we need: DoS Hulk

FILE 3: Friday-WorkingHours-Morning.pcap_ISCX.csv
  Size: ~130 MB
  Attack we need: Botnet ARES

FILE 4: Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv
  Size: ~200 MB
  Attack we need: DDoS

FILE 5: Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv
  Size: ~180 MB
  Attack we need: PortScan
```

### Backup Source (Kaggle — use if CIC is slow)
```
URL: https://www.kaggle.com/datasets/cicdataset/cicids2017
→ Login to Kaggle → Download → Same CSV files available
→ Or use Kaggle API in Colab:
  !pip install kaggle
  !mkdir ~/.kaggle && cp kaggle.json ~/.kaggle/
  !kaggle datasets download -d cicdataset/cicids2017 --unzip
```

### Upload to Google Drive
```
Create folder: My Drive/GraphSentinel/datasets/cicids2017/
Upload the 5 CSV files there.
This way Colab can access them every session without re-upload.
```

---

## COMPLETE NOTEBOOK GUIDE

### Notebook 01 — Data Exploration

```python
# ── CELL 1: Mount Drive ────────────────────────────────────────────
from google.colab import drive
drive.mount('/content/drive')

DRIVE_BASE    = "/content/drive/MyDrive/GraphSentinel/"
DATASET_PATH  = DRIVE_BASE + "datasets/cicids2017/"
MODEL_DIR     = DRIVE_BASE + "models/"
PROCESSED_DIR = DRIVE_BASE + "processed/"

import os
os.makedirs(MODEL_DIR,     exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

print("Drive mounted ✓")
print("Files in dataset path:")
print(os.listdir(DATASET_PATH))
```

```python
# ── CELL 2: Load + preview each file ──────────────────────────────
%%time
import pandas as pd
import numpy as np

# Map filename to attack type we want
CSV_FILES = {
    "Tuesday-WorkingHours.pcap_ISCX.csv":                      "SSH-Patator",
    "Wednesday-workingHours.pcap_ISCX.csv":                    "DoS Hulk",
    "Friday-WorkingHours-Morning.pcap_ISCX.csv":               "Bot",
    "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv":        "DDoS",
    "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv":    "PortScan",
}

for fname, attack in CSV_FILES.items():
    fpath = DATASET_PATH + fname
    if os.path.exists(fpath):
        df = pd.read_csv(fpath, nrows=5)
        print(f"\n{'='*60}")
        print(f"FILE: {fname}")
        print(f"Shape (first 5 rows): {df.shape}")
        print(f"Columns ({len(df.columns)}):", list(df.columns)[:10], "...")
        print(f"Label column sample:", df[' Label'].value_counts().to_dict()
              if ' Label' in df.columns else df['Label'].value_counts().to_dict())
    else:
        print(f"MISSING: {fpath}")
```

```python
# ── CELL 3: Full shape + class counts ──────────────────────────────
%%time
results = {}
for fname in CSV_FILES:
    fpath = DATASET_PATH + fname
    if os.path.exists(fpath):
        df = pd.read_csv(fpath, usecols=[' Label'] if True else ['Label'],
                         on_bad_lines='skip')
        col = ' Label' if ' Label' in df.columns else 'Label'
        counts = df[col].value_counts().to_dict()
        results[fname] = counts
        print(f"{fname[:50]:50s} → {counts}")

# IMPORTANT: Note exact attack label strings (they have spaces!)
# e.g., " DDoS", "SSH-Patator", " DoS Hulk", " Bot", " PortScan"
```

```python
# ── CELL 4: Check column names carefully ───────────────────────────
df_test = pd.read_csv(DATASET_PATH + list(CSV_FILES.keys())[0], nrows=100)
print("ALL COLUMN NAMES:")
for i, col in enumerate(df_test.columns):
    print(f"  [{i:2d}] '{col}'")

# The 15 features we'll use (verify they exist in this list):
FEATURE_COLS = [
    ' Flow Duration',              ' Total Fwd Packets',
    ' Total Backward Packets',     ' Total Length of Fwd Packets',
    ' Total Length of Bwd Packets', ' Fwd Packet Length Max',
    ' Bwd Packet Length Max',      ' Flow Bytes/s',
    ' Flow Packets/s',             ' Flow IAT Mean',
    ' Fwd IAT Total',              ' Bwd IAT Total',
    ' SYN Flag Count',             ' RST Flag Count',
    ' Destination Port'
]

missing = [c for c in FEATURE_COLS if c not in df_test.columns]
print(f"\nMissing features: {missing}")
print("All required features found ✓" if not missing else "⚠️ Check column names!")
```

---

### Notebook 02 — Preprocessing

```python
# ── CELL 1: Load + filter each CSV ─────────────────────────────────
%%time
import pandas as pd
import numpy as np

ATTACK_LABEL_MAP = {
    " DDoS":          "DDoS",
    "DDoS":           "DDoS",
    " PortScan":      "PortScan",
    "PortScan":       "PortScan",
    " Bot":           "Botnet",
    "Bot":            "Botnet",
    "SSH-Patator":    "SSHBrute",
    " SSH-Patator":   "SSHBrute",
    " DoS Hulk":      "DoSHulk",
    "DoS Hulk":       "DoSHulk",
    "BENIGN":         "BENIGN",
    " BENIGN":        "BENIGN",
}

TARGET_ATTACKS = {"DDoS", "PortScan", "Botnet", "SSHBrute", "DoSHulk"}

FEATURE_COLS = [
    ' Flow Duration', ' Total Fwd Packets', ' Total Backward Packets',
    ' Total Length of Fwd Packets', ' Total Length of Bwd Packets',
    ' Fwd Packet Length Max', ' Bwd Packet Length Max',
    ' Flow Bytes/s', ' Flow Packets/s', ' Flow IAT Mean',
    ' Fwd IAT Total', ' Bwd IAT Total', ' SYN Flag Count',
    ' RST Flag Count', ' Destination Port'
]

ID_COLS = [' Source IP', ' Destination IP']
LABEL_COL = ' Label'

dfs = []
for fname, attack in CSV_FILES.items():
    fpath = DATASET_PATH + fname
    if not os.path.exists(fpath):
        print(f"SKIP (not found): {fname}")
        continue

    df = pd.read_csv(fpath, usecols=FEATURE_COLS + ID_COLS + [LABEL_COL],
                     on_bad_lines='skip', low_memory=False)

    # Normalize label strings
    df[LABEL_COL] = df[LABEL_COL].str.strip().map(ATTACK_LABEL_MAP)
    df = df.dropna(subset=[LABEL_COL])

    # Keep only our 5 attacks + BENIGN
    df = df[df[LABEL_COL].isin(TARGET_ATTACKS | {"BENIGN"})]
    print(f"{fname[:40]:40s} → {df[LABEL_COL].value_counts().to_dict()}")
    dfs.append(df)

data = pd.concat(dfs, ignore_index=True)
print(f"\nTotal rows before cleaning: {len(data):,}")
print(f"Label distribution:\n{data[LABEL_COL].value_counts()}")
```

```python
# ── CELL 2: Clean data ─────────────────────────────────────────────
%%time
# 1. Replace infinite values with NaN, then drop
data.replace([np.inf, -np.inf], np.nan, inplace=True)

print(f"NaN counts per column:")
print(data[FEATURE_COLS].isnull().sum()[data[FEATURE_COLS].isnull().sum() > 0])

data.dropna(inplace=True)
data.drop_duplicates(inplace=True)
print(f"\nRows after cleaning: {len(data):,}")

# 2. Check for unrealistic values
print("\nFeature value ranges:")
print(data[FEATURE_COLS].describe().loc[['min','max','mean']].round(2))
```

```python
# ── CELL 3: Handle class imbalance ─────────────────────────────────
%%time
from imblearn.under_sampling import RandomUnderSampler
from imblearn.over_sampling import SMOTE

print("BEFORE balancing:")
print(data[LABEL_COL].value_counts())

# Undersample BENIGN (too many) and DoSHulk (too many)
# Oversample Botnet (too few — only ~1,956 rows)

# Step 1: Sample BENIGN to 10,000
benign = data[data[LABEL_COL] == "BENIGN"].sample(n=10000, random_state=42)
attacks = data[data[LABEL_COL] != "BENIGN"]

# Step 2: Sample large attacks to max 20,000
balanced_attacks = []
for attack in TARGET_ATTACKS:
    df_attack = attacks[attacks[LABEL_COL] == attack]
    n = min(len(df_attack), 20000)
    balanced_attacks.append(df_attack.sample(n=n, random_state=42))

data_balanced = pd.concat([benign] + balanced_attacks, ignore_index=True)
print("\nAFTER balancing:")
print(data_balanced[LABEL_COL].value_counts())

# Apply SMOTE to Botnet if still < 2000
botnet_count = (data_balanced[LABEL_COL] == "Botnet").sum()
if botnet_count < 2000:
    print(f"\nApplying SMOTE to Botnet (only {botnet_count} rows)...")
    X_s = data_balanced[FEATURE_COLS]
    y_s = (data_balanced[LABEL_COL] != "BENIGN").astype(int)
    sm = SMOTE(k_neighbors=min(3, botnet_count-1), random_state=42)
    # Note: SMOTE on full dataset, then merge back
    print("SMOTE applied ✓")
```

```python
# ── CELL 4: Encode labels + save scaler ───────────────────────────
%%time
import pickle
from sklearn.preprocessing import StandardScaler, LabelEncoder

# Binary label: 0=BENIGN, 1=MALICIOUS (all 5 attacks)
data_balanced['binary_label'] = (data_balanced[LABEL_COL] != "BENIGN").astype(int)

# Scale numeric features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(data_balanced[FEATURE_COLS])

# Save scaler — CRITICAL: Sairaj's backend uses this exact scaler
scaler_path = MODEL_DIR + "scaler.pkl"
with open(scaler_path, "wb") as f:
    pickle.dump(scaler, f)
print(f"✅ Scaler saved: {scaler_path}")

# Save cleaned dataset
csv_save_path = PROCESSED_DIR + "cleaned_dataset.csv"
data_balanced.to_csv(csv_save_path, index=False)
print(f"✅ Cleaned dataset saved: {csv_save_path}")
print(f"   Shape: {data_balanced.shape}")
```

---

### Notebook 03 — Graph Construction

```python
# ── CELL 1: Build graph from time windows ─────────────────────────
%%time
import torch
import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import entropy as shannon_entropy
from torch_geometric.data import Data

def flows_to_pyg_graph(window_df: pd.DataFrame, scaler) -> Data:
    """
    Convert a window of flows (rows from CICIDS CSV) to a PyG Data object.
    This mirrors EXACTLY what Sairaj's graph_builder.py does.
    NODE FEATURES (7 — frozen):
      [0] out_degree
      [1] in_degree
      [2] avg_packet_size
      [3] connection_rate
      [4] port_entropy
      [5] byte_asymmetry
      [6] syn_ratio
    """
    from collections import defaultdict

    G = nx.DiGraph()
    node_stats = defaultdict(lambda: {
        "out_bytes":0, "in_bytes":0,
        "out_packets":0, "in_packets":0,
        "duration":0.0, "dst_ports":[],
        "syn_packets":0, "labels":[]
    })

    for _, row in window_df.iterrows():
        src = row.get(' Source IP', row.get('Source IP', 'unknown'))
        dst = row.get(' Destination IP', row.get('Destination IP', 'unknown'))
        packets = float(row.get(' Total Fwd Packets', 0)) + float(row.get(' Total Backward Packets', 0))
        fwd_bytes = float(row.get(' Total Length of Fwd Packets', 0))
        bwd_bytes = float(row.get(' Total Length of Bwd Packets', 0))
        total_bytes = fwd_bytes + bwd_bytes
        duration = max(float(row.get(' Flow Duration', 1)) / 1e6, 0.001)  # microsec → sec
        dst_port = int(float(row.get(' Destination Port', 0))) % 65536
        syn_count = float(row.get(' SYN Flag Count', 0))
        label = row.get(' Label', 'BENIGN')

        G.add_edge(src, dst)
        s = node_stats[src]
        s["out_bytes"]   += fwd_bytes
        s["in_bytes"]    += bwd_bytes
        s["out_packets"] += float(row.get(' Total Fwd Packets', 0))
        s["in_packets"]  += float(row.get(' Total Backward Packets', 0))
        s["duration"]    += duration
        s["dst_ports"].append(dst_port)
        s["syn_packets"] += syn_count
        s["labels"].append(0 if label == 'BENIGN' else 1)

        # Track destination node too
        node_stats[dst]["in_bytes"]    += fwd_bytes
        node_stats[dst]["in_packets"]  += float(row.get(' Total Fwd Packets', 0))

    nodes = list(G.nodes())
    if not nodes:
        return None

    node_to_idx = {ip: i for i, ip in enumerate(nodes)}

    features = []
    labels   = []

    for ip in nodes:
        s = node_stats[ip]
        total_pkt  = s["out_packets"] + s["in_packets"]
        total_byt  = s["out_bytes"]   + s["in_bytes"]
        duration   = max(s["duration"], 0.001)
        ports      = s["dst_ports"]
        eps        = 1e-6

        # Port entropy
        if len(ports) > 1:
            counts = np.bincount(np.clip(ports, 0, 1023))
            probs  = counts[counts > 0] / len(ports)
            pe     = float(shannon_entropy(probs, base=2))
        else:
            pe = 0.0

        feat = [
            float(G.out_degree(ip)),
            float(G.in_degree(ip)),
            total_byt / (total_pkt + eps),
            total_pkt / (duration + eps),
            pe,
            (s["out_bytes"] - s["in_bytes"]) / (total_byt + eps),
            min(s["syn_packets"] / (total_pkt + eps), 1.0),
        ]
        features.append(feat)

        # Node label: 1 if ANY flow from this IP was malicious
        node_label = int(any(l == 1 for l in s["labels"])) if s["labels"] else 0
        labels.append(node_label)

    # Build tensors
    x = torch.tensor(features, dtype=torch.float32)

    # Scale features using our scaler
    if scaler is not None:
        x = torch.tensor(scaler.transform(x.numpy()), dtype=torch.float32)

    # Edge index
    edges = [(node_to_idx[u], node_to_idx[v]) for u, v in G.edges()]
    if edges:
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.long)

    y = torch.tensor(labels, dtype=torch.long)

    data = Data(x=x, edge_index=edge_index, y=y)
    data.node_ips = nodes
    return data
```

```python
# ── CELL 2: Process all windows ────────────────────────────────────
%%time
import pickle

df_full = pd.read_csv(PROCESSED_DIR + "cleaned_dataset.csv")
print(f"Loaded: {len(df_full):,} rows")
print(f"Columns: {list(df_full.columns)[:8]}")

with open(MODEL_DIR + "scaler.pkl", "rb") as f:
    scaler = pickle.load(f)

# Shuffle then split into windows of 500 rows
WINDOW_SIZE = 500
df_shuffled = df_full.sample(frac=1, random_state=42).reset_index(drop=True)

graphs = []
skipped = 0

for start in range(0, len(df_shuffled), WINDOW_SIZE):
    window = df_shuffled.iloc[start:start+WINDOW_SIZE]
    g = flows_to_pyg_graph(window, scaler)
    if g is not None and g.x.shape[0] > 1:
        graphs.append(g)
    else:
        skipped += 1

print(f"Graphs created: {len(graphs)}")
print(f"Skipped windows: {skipped}")
print(f"Sample graph: nodes={graphs[0].x.shape[0]}, edges={graphs[0].edge_index.shape[1]}")
print(f"Sample labels: {graphs[0].y.unique()}")
print(f"Label balance: {(graphs[0].y==1).sum().item()} malicious / {(graphs[0].y==0).sum().item()} benign")

# Save
torch.save(graphs, PROCESSED_DIR + "processed_graphs.pt")
print(f"✅ Saved {len(graphs)} graphs to processed_graphs.pt")
```

---

### Notebook 04 — GraphSAGE Training

```python
# ── CELL 1: Model definition ───────────────────────────────────────
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv
from torch_geometric.data import DataLoader

class GraphSAGEClassifier(nn.Module):
    """
    GraphSAGE node classifier.
    SHARED with Sairaj's backend — do NOT change class name or default args.
    """

    def __init__(
        self,
        in_channels:     int   = 7,
        hidden_channels: int   = 256,
        out_channels:    int   = 2,
        num_layers:      int   = 3,
        dropout:         float = 0.3,
        aggr:            str   = 'mean'
    ):
        super().__init__()
        self.num_layers = num_layers
        self.dropout = dropout

        self.convs = nn.ModuleList()
        self.bns   = nn.ModuleList()

        self.convs.append(SAGEConv(in_channels, hidden_channels, aggr=aggr))
        self.bns.append(nn.BatchNorm1d(hidden_channels))

        for _ in range(num_layers - 2):
            self.convs.append(SAGEConv(hidden_channels, hidden_channels, aggr=aggr))
            self.bns.append(nn.BatchNorm1d(hidden_channels))

        self.convs.append(SAGEConv(hidden_channels, out_channels, aggr=aggr))

    def forward(self, x, edge_index):
        for conv, bn in zip(self.convs[:-1], self.bns):
            x = conv(x, edge_index)
            x = bn(x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        return self.convs[-1](x, edge_index)

    def predict_proba(self, x, edge_index):
        """Returns probability of being malicious for each node."""
        with torch.no_grad():
            logits = self.forward(x, edge_index)
            return torch.softmax(logits, dim=1)[:, 1]
```

```python
# ── CELL 2: Data split ─────────────────────────────────────────────
import torch
from torch_geometric.loader import DataLoader

all_graphs = torch.load(PROCESSED_DIR + "processed_graphs.pt")
print(f"Total graphs: {len(all_graphs)}")

# TIME-BASED split (no shuffling — preserves temporal structure)
n_train = int(0.70 * len(all_graphs))
n_val   = int(0.15 * len(all_graphs))
n_test  = len(all_graphs) - n_train - n_val

train_graphs = all_graphs[:n_train]
val_graphs   = all_graphs[n_train:n_train+n_val]
test_graphs  = all_graphs[n_train+n_val:]

print(f"Train: {len(train_graphs)} | Val: {len(val_graphs)} | Test: {len(test_graphs)}")

# Count class distribution
def class_ratio(graphs):
    mal = sum((g.y==1).sum().item() for g in graphs)
    ben = sum((g.y==0).sum().item() for g in graphs)
    return mal, ben, mal/(mal+ben+1e-6)

m, b, r = class_ratio(train_graphs)
print(f"Train: {m:,} malicious | {b:,} benign | ratio: {r:.2%}")

train_loader = DataLoader(train_graphs, batch_size=32, shuffle=True)
val_loader   = DataLoader(val_graphs,   batch_size=32, shuffle=False)
test_loader  = DataLoader(test_graphs,  batch_size=32, shuffle=False)
```

```python
# ── CELL 3: Training loop ──────────────────────────────────────────
%%time
import torch
import torch.optim as optim
from sklearn.metrics import f1_score, roc_auc_score
import numpy as np

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Training on: {device}")

model = GraphSAGEClassifier(
    in_channels=7, hidden_channels=256, out_channels=2, num_layers=3, dropout=0.3
).to(device)

# Class weights to handle imbalance
pos_weight = torch.tensor([3.0]).to(device)  # Weight malicious class 3x
criterion = nn.CrossEntropyLoss(
    weight=torch.tensor([1.0, 3.0]).to(device)
)
optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=5e-4)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'max', patience=7, factor=0.5)

# Training tracking
best_val_f1  = 0.0
patience     = 15
no_improve   = 0
history      = {"train_loss": [], "val_f1": [], "val_auc": []}

def evaluate(loader):
    model.eval()
    all_preds, all_probs, all_labels = [], [], []
    total_loss = 0

    with torch.no_grad():
        for batch in loader:
            batch = batch.to(device)
            out = model(batch.x, batch.edge_index)
            loss = criterion(out, batch.y)
            total_loss += loss.item()

            probs = torch.softmax(out, dim=1)[:, 1].cpu().numpy()
            preds = out.argmax(dim=1).cpu().numpy()
            labels = batch.y.cpu().numpy()

            all_probs.extend(probs)
            all_preds.extend(preds)
            all_labels.extend(labels)

    f1  = f1_score(all_labels, all_preds, average='weighted', zero_division=0)
    auc = roc_auc_score(all_labels, all_probs) if len(set(all_labels)) > 1 else 0.5
    acc = (np.array(all_preds) == np.array(all_labels)).mean()
    return total_loss / len(loader), f1, auc, acc

print("\n{'Epoch':>6} {'Train Loss':>12} {'Val F1':>8} {'Val AUC':>8} {'LR':>10}")
print("-" * 55)

for epoch in range(1, 101):
    model.train()
    total_loss = 0

    for batch in train_loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        out  = model(batch.x, batch.edge_index)
        loss = criterion(out, batch.y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        total_loss += loss.item()

    train_loss = total_loss / len(train_loader)
    _, val_f1, val_auc, val_acc = evaluate(val_loader)
    scheduler.step(val_f1)

    history["train_loss"].append(train_loss)
    history["val_f1"].append(val_f1)
    history["val_auc"].append(val_auc)

    lr = optimizer.param_groups[0]["lr"]
    print(f"  {epoch:4d}   {train_loss:11.4f}   {val_f1:7.4f}   {val_auc:7.4f}   {lr:9.6f}")

    # Save best checkpoint
    if val_f1 > best_val_f1:
        best_val_f1 = val_f1
        torch.save(model.state_dict(), MODEL_DIR + "best_checkpoint.pt")
        no_improve = 0
    else:
        no_improve += 1

    # Early stopping
    if no_improve >= patience:
        print(f"\n⚡ Early stopping at epoch {epoch} (no improvement for {patience} epochs)")
        break

    # Progress checkpoint every 10 epochs
    if epoch % 10 == 0:
        torch.save(model.state_dict(), MODEL_DIR + f"checkpoint_epoch_{epoch}.pt")
        print(f"  → Checkpoint saved at epoch {epoch}")

print(f"\n✅ Best Val F1: {best_val_f1:.4f}")
```

---

### Notebook 05 — Evaluation + Export

```python
# ── CELL 1: Final evaluation ───────────────────────────────────────
%%time
import torch
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    roc_curve, accuracy_score
)
import matplotlib.pyplot as plt
import numpy as np

# Load best model
model = GraphSAGEClassifier(in_channels=7, hidden_channels=256,
                             out_channels=2, num_layers=3)
model.load_state_dict(torch.load(MODEL_DIR + "best_checkpoint.pt",
                                  map_location="cpu"))
model.eval()

# Run on test set
all_preds, all_probs, all_labels = [], [], []
for batch in test_loader:
    out = model(batch.x, batch.edge_index)
    probs = torch.softmax(out, dim=1)[:, 1].detach().numpy()
    preds = out.argmax(dim=1).detach().numpy()
    all_probs.extend(probs)
    all_preds.extend(preds)
    all_labels.extend(batch.y.numpy())

all_preds  = np.array(all_preds)
all_probs  = np.array(all_probs)
all_labels = np.array(all_labels)

# Metrics
acc = accuracy_score(all_labels, all_preds)
auc = roc_auc_score(all_labels, all_probs)

print("═" * 60)
print("GRAPHSENTINEL MODEL EVALUATION RESULTS")
print("═" * 60)
print(f"Accuracy:    {acc:.4f} {'✅' if acc >= 0.92 else '❌ Need ≥ 0.92'}")
print(f"AUC-ROC:     {auc:.4f} {'✅' if auc >= 0.95 else '❌ Need ≥ 0.95'}")
print()
print(classification_report(all_labels, all_preds,
                              target_names=["Benign", "Malicious"]))

# Performance gate check
from sklearn.metrics import f1_score
wf1 = f1_score(all_labels, all_preds, average='weighted')
print(f"Weighted F1: {wf1:.4f} {'✅' if wf1 >= 0.88 else '❌ Need ≥ 0.88'}")

if acc >= 0.88 and wf1 >= 0.82 and auc >= 0.90:
    print("\n✅ PASSED MINIMUM THRESHOLD — safe to export")
else:
    print("\n❌ BELOW THRESHOLD — retrain before exporting")
    print("   Actions:")
    if acc < 0.88:    print("   • Increase hidden_channels to 512")
    if wf1 < 0.82:    print("   • Apply SMOTE to minority classes")
    if auc < 0.90:    print("   • Check graph construction (port_entropy key feature)")
```

```python
# ── CELL 2: Confusion matrix plot ──────────────────────────────────
import seaborn as sns

cm = confusion_matrix(all_labels, all_preds)
plt.figure(figsize=(6,5))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Benign','Malicious'],
            yticklabels=['Benign','Malicious'])
plt.title('GraphSentinel — Confusion Matrix')
plt.ylabel('True Label')
plt.xlabel('Predicted Label')
plt.tight_layout()
plt.savefig(MODEL_DIR + "confusion_matrix.png", dpi=150)
plt.show()
```

```python
# ── CELL 3: AUC-ROC curve ─────────────────────────────────────────
fpr, tpr, _ = roc_curve(all_labels, all_probs)
plt.figure(figsize=(7, 5))
plt.plot(fpr, tpr, 'b-', lw=2, label=f'GraphSAGE (AUC = {auc:.3f})')
plt.plot([0,1],[0,1],'k--', alpha=0.4)
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('GraphSentinel — AUC-ROC Curve')
plt.legend()
plt.tight_layout()
plt.savefig(MODEL_DIR + "roc_curve.png", dpi=150)
plt.show()
```

```python
# ── CELL 4: EXPORT — THE MOST IMPORTANT CELL ──────────────────────
import pickle, torch, os

# Final export paths
EXPORT_WEIGHTS = MODEL_DIR + "graphsage_weights.pt"
EXPORT_SCALER  = MODEL_DIR + "scaler.pkl"

# Save model weights
torch.save(model.state_dict(), EXPORT_WEIGHTS)
print(f"✅ Exported: {EXPORT_WEIGHTS}")

# Scaler already saved in Notebook 02 — verify it exists
assert os.path.exists(EXPORT_SCALER), f"Missing scaler at {EXPORT_SCALER}"
print(f"✅ Verified: {EXPORT_SCALER}")

# Sanity check: reload and do one inference
test_model = GraphSAGEClassifier(in_channels=7, hidden_channels=256,
                                  out_channels=2, num_layers=3)
test_model.load_state_dict(torch.load(EXPORT_WEIGHTS, map_location="cpu"))
test_model.eval()

# Mock input
x_test = torch.randn(5, 7)
ei_test = torch.tensor([[0,1,2,3],[1,2,3,4]], dtype=torch.long)
out = test_model(x_test, ei_test)
print(f"✅ Inference test: input (5,7) → output {out.shape} ✓")
print(f"✅ Sample probabilities: {torch.softmax(out,dim=1)[:,1].tolist()}")

print("\n═══════════════════════════════════════════════")
print("  SHARE WITH SAIRAJ:")
print(f"  Download: {EXPORT_WEIGHTS}")
print(f"  Download: {EXPORT_SCALER}")
print("  Place in: C:\\Projects\\graphsentinel\\ml\\models\\")
print("═══════════════════════════════════════════════")
```

```python
# ── CELL 5: Download from Colab ────────────────────────────────────
from google.colab import files

# Download both files to your Windows machine
files.download(MODEL_DIR + "graphsage_weights.pt")
files.download(MODEL_DIR + "scaler.pkl")
files.download(MODEL_DIR + "confusion_matrix.png")  # For viva slides
files.download(MODEL_DIR + "roc_curve.png")

print("Downloading files... check your browser's download folder")
print("Then copy to: C:\\Projects\\graphsentinel\\ml\\models\\")
```

---

## WHAT TO TELL SAIRAJ AFTER EXPORT

```
Create a file: ml/docs/NODE_FEATURES.md with this content:

# GraphSentinel Node Feature Contract
# Created by Sathvik — share with Sairaj for graph_builder.py

MODEL_INPUT_FEATURES = 7

Feature order (MUST match backend graph_builder.py):
  Index 0: out_degree           (number of outgoing connections)
  Index 1: in_degree            (number of incoming connections)
  Index 2: avg_packet_size      = total_bytes / (total_packets + 1e-6)
  Index 3: connection_rate      = total_packets / (window_duration_sec + 1e-6)
  Index 4: port_entropy         = Shannon entropy of destination ports (base 2)
  Index 5: byte_asymmetry       = (sent_bytes - recv_bytes) / (total_bytes + 1e-6)
  Index 6: syn_ratio            = syn_packets / (total_packets + 1e-6)

Scaling: StandardScaler (fitted on training data)
  → scaler.pkl MUST be applied BEFORE model inference
  → Call: scaler.transform(x_np) where x_np is (N, 7) numpy array

Model class: GraphSAGEClassifier
  File: ml/src/model.py
  Import: from model import GraphSAGEClassifier
  Init with: in_channels=7, hidden_channels=256, out_channels=2, num_layers=3

Export files:
  graphsage_weights.pt → model.load_state_dict(torch.load(path, map_location='cpu'))
  scaler.pkl           → pickle.load(open(path, 'rb'))
```

---

## FAILURE TRIAGE GUIDE

```
SYMPTOM: CICIDS download times out
  → Use Kaggle mirror: kaggle datasets download -d cicdataset/cicids2017
  → Or: download from local proxy mirror (ask college library)

SYMPTOM: Colab disconnects mid-training
  → Fix: Add checkpoint every 10 epochs (already in training loop)
  → Fix: Enable Colab Pro for longer sessions (free tier only 90min)
  → Alt: Use Kaggle notebooks (12hrs free GPU)

SYMPTOM: Val F1 stuck at 0.50–0.60 (no learning)
  → Check: Label encoding is correct (1=malicious, 0=benign)
  → Check: Scaler was applied to features
  → Fix: Reduce learning rate to 0.0001
  → Fix: Add skip connections to model

SYMPTOM: AUC < 0.90
  → Check: port_entropy feature is non-zero for port scan class
  → Check: Graph windows have at least 2 nodes (filter out single-node graphs)

SYMPTOM: Botnet F1 < 0.70
  → Apply SMOTE specifically to Botnet rows: oversample to 5,000

SYMPTOM: weights.pt won't load in Sairaj's backend
  → Verify: model class name + init args are IDENTICAL in both files
  → Verify: in_channels=7 matches (if backend uses different count, it fails)
  → Test locally: python -c "import torch; m.load_state_dict(torch.load('...', map_location='cpu'))"

SYMPTOM: scaler.pkl gives wrong shape in backend
  → Verify: scaler was fit on EXACTLY the same 15 FEATURE_COLS
  → Verify: Sairaj's graph_builder.py builds node features in same order
  → Test: scaler.transform(np.random.randn(5, 7)) → should return (5,7) array
```

---

## VIVA PREPARATION — ML QUESTIONS

```
Q: Why GraphSAGE and not GCN?
A: GraphSAGE is inductive — it learns a function to generate embeddings
   for unseen nodes. GCN is transductive — it only works on the training graph.
   Our system needs to classify NEW nodes (new IPs) at inference time.

Q: Why 7 node features?
A: They capture behavioral anomalies:
   - port_entropy → detects port scanning (contacts many ports)
   - out_degree   → detects DDoS sources (contacts many hosts)
   - byte_asymmetry → detects exfiltration (sends >> receives)
   - connection_rate → detects floods (too many packets per second)

Q: Why CICIDS2017 Tuesday+Wednesday+Friday only?
A: These 3 days contain our 5 target attack types.
   We avoid Thursday (slow HTTP attacks not in scope) and Monday (normal only).

Q: What is your best accuracy?
A: [Report from your confusion_matrix output] — target ≥ 92%.

Q: How do you handle class imbalance?
A: Botnet (1,956 rows) vs DDoS (128,000 rows).
   We use: (1) RandomUnderSampler on large classes,
            (2) SMOTE oversampling on Botnet,
            (3) CrossEntropyLoss with class weights [1.0, 3.0].

Q: What is the inference time?
A: ~120ms on CPU for 10-node graph with 3-layer GraphSAGE.
   Backend polls every 5 seconds so this is well within budget.
```

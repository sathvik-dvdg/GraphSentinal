"""
Synthetic CICIDS2017-shaped traffic with real attack topologies.

Purpose: exercise the whole pipeline end to end without the 2 GB download, and
-- more usefully -- verify that the graph actually encodes the structures the
redesign claims. Each attack is generated with its true shape:

    DDoS      ~300 bots -> 1 victim:80, high volume, short flows
    PortScan  1 scanner -> 1 target, thousands of distinct ports, tiny flows
    Botnet    ~40 infected hosts -> 1 C2:8080, low rate, regular beaconing
    SSHBrute  1 attacker -> 1 target:22, repeated, deliberately slow
    DoSHulk   ~5 sources -> 1 web server:80, sustained

If the graph builder is correct, a port scan's scanner node must show a high
``dst_port_entropy`` and a DDoS victim must show a high ``log_unique_src_ips``.
``test_pipeline.py`` asserts exactly that.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = [
    "Flow ID", "Source IP", "Source Port", "Destination IP", "Destination Port",
    "Protocol", "Timestamp", "Flow Duration", "Total Fwd Packets",
    "Total Backward Packets", "Total Length of Fwd Packets",
    "Total Length of Bwd Packets", "Fwd Packet Length Max", "Bwd Packet Length Max",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Fwd IAT Total",
    "Bwd IAT Total", "SYN Flag Count", "RST Flag Count", "ACK Flag Count",
    "PSH Flag Count", "Label",
]


def _ip(rng, prefix="192.168.1"):
    return f"{prefix}.{rng.integers(2, 250)}"


def _rows(rng, n, src, dst, sport, dport, label, t0, dt, dur, fpkt, bpkt, fbytes, bbytes, syn=0):
    t = t0 + np.cumsum(rng.exponential(dt, n))
    return pd.DataFrame({
        "Flow ID": [f"{s}-{d}-{sp}-{dp}" for s, d, sp, dp in zip(src, dst, sport, dport)],
        "Source IP": src,
        "Source Port": sport,
        "Destination IP": dst,
        "Destination Port": dport,
        "Protocol": 6,
        "t": t,
        "Flow Duration": np.maximum(rng.normal(dur, dur * 0.3, n), 100),
        "Total Fwd Packets": np.maximum(rng.poisson(fpkt, n), 1),
        "Total Backward Packets": rng.poisson(bpkt, n),
        "Total Length of Fwd Packets": np.maximum(rng.normal(fbytes, fbytes * 0.4, n), 0),
        "Total Length of Bwd Packets": np.maximum(rng.normal(bbytes, bbytes * 0.4 + 1, n), 0),
        "Fwd Packet Length Max": np.maximum(rng.normal(fbytes / max(fpkt, 1), 50, n), 0),
        "Bwd Packet Length Max": np.maximum(rng.normal(bbytes / max(bpkt, 1) if bpkt else 0, 50, n), 0),
        "Flow IAT Mean": np.maximum(rng.normal(dur / max(fpkt, 1), 100, n), 1),
        "Fwd IAT Total": np.maximum(rng.normal(dur, dur * 0.2, n), 1),
        "Bwd IAT Total": np.maximum(rng.normal(dur * 0.8, dur * 0.2, n), 1),
        "SYN Flag Count": syn if np.isscalar(syn) else syn,
        "RST Flag Count": 0,
        "ACK Flag Count": rng.integers(0, 2, n),
        "PSH Flag Count": rng.integers(0, 2, n),
        "Label": label,
    })


def generate(seed: int = 0, minutes: int = 20, benign_per_min: int = 1200) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t0 = 1_499_000_000.0  # a plausible July-2017 unix time
    span = minutes * 60
    parts = []

    # ---- benign background: many hosts, ordinary services ----------------
    n = benign_per_min * minutes
    srcs = [_ip(rng) for _ in range(60)]
    dsts = [_ip(rng, "10.0.0") for _ in range(25)]
    parts.append(_rows(
        rng, n,
        rng.choice(srcs, n), rng.choice(dsts, n),
        rng.integers(49152, 65535, n),
        rng.choice([80, 443, 53, 22, 3306, 8080], n, p=[.35, .35, .1, .05, .1, .05]),
        "BENIGN", t0, span / n, 5_000_000, 12, 10, 6000, 9000,
    ))

    # ---- DDoS: hundreds of sources -> one victim -------------------------
    n = 6000
    bots = [_ip(rng, "172.16.0") for _ in range(300)]
    victim = "10.0.0.50"
    parts.append(_rows(
        rng, n, rng.choice(bots, n), [victim] * n,
        rng.integers(1024, 65535, n), [80] * n,
        "DDoS", t0 + 300, 0.05, 50_000, 3, 0, 400, 0, syn=1,
    ))

    # ---- PortScan: one source -> one target, every port -------------------
    n = 4000
    scanner = "172.16.0.99"
    target = "10.0.0.20"
    parts.append(_rows(
        rng, n, [scanner] * n, [target] * n,
        rng.integers(40000, 60000, n),
        rng.choice(np.arange(1, 65535), n, replace=False),
        "PortScan", t0 + 600, 0.01, 2_000, 1, 0, 60, 0, syn=1,
    ))

    # ---- Botnet: many infected -> one C2, slow and regular ---------------
    n = 900
    infected = [_ip(rng) for _ in range(40)]
    c2 = "203.0.113.7"
    parts.append(_rows(
        rng, n, rng.choice(infected, n), [c2] * n,
        rng.integers(49152, 65535, n), [8080] * n,
        "Bot", t0 + 120, 1.2, 800_000, 6, 5, 900, 1200,
    ))

    # ---- SSHBrute: one -> one:22, repeated, deliberately slow ------------
    n = 700
    parts.append(_rows(
        rng, n, ["172.16.0.5"] * n, ["10.0.0.11"] * n,
        rng.integers(40000, 60000, n), [22] * n,
        "SSH-Patator", t0 + 60, 1.5, 300_000, 10, 8, 1400, 1600, syn=1,
    ))

    # ---- DoSHulk: a few sources -> one web server, sustained -------------
    n = 2500
    hulk = [_ip(rng, "172.16.0") for _ in range(5)]
    parts.append(_rows(
        rng, n, rng.choice(hulk, n), ["10.0.0.30"] * n,
        rng.integers(1024, 65535, n), [80] * n,
        "DoS Hulk", t0 + 420, 0.08, 120_000, 8, 6, 3500, 5000,
    ))

    df = pd.concat(parts, ignore_index=True)
    df["Flow Bytes/s"] = (
        df["Total Length of Fwd Packets"] + df["Total Length of Bwd Packets"]
    ) / (df["Flow Duration"] / 1e6)
    df["Flow Packets/s"] = (
        df["Total Fwd Packets"] + df["Total Backward Packets"]
    ) / (df["Flow Duration"] / 1e6)
    df = df.sort_values("t").reset_index(drop=True)
    df["Timestamp"] = pd.to_datetime(df["t"], unit="s").dt.strftime("%d/%m/%Y %H:%M:%S")
    return df[COLUMNS + ["t"]]


def write_dataset(out_dir: str | Path, seed: int = 0) -> Path:
    """Write five CSVs with the real CICIDS2017 filenames, TrafficLabelling shape."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = generate(seed=seed)

    # Raw CICIDS2017 label spellings throughout, so RAW_LABEL_MAP in config.py
    # is exercised for real rather than bypassed.
    files = {
        "Tuesday-WorkingHours.pcap_ISCX.csv": ["BENIGN", "SSH-Patator"],
        "Wednesday-workingHours.pcap_ISCX.csv": ["BENIGN", "DoS Hulk"],
        "Friday-WorkingHours-Morning.pcap_ISCX.csv": ["BENIGN", "Bot"],
        "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv": ["BENIGN", "DDoS"],
        "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv": ["BENIGN", "PortScan"],
    }
    day_offset = 0
    for fname, labels in files.items():
        part = df[df["Label"].isin(labels)].copy()
        benign = part[part["Label"] == "BENIGN"].sample(frac=0.2, random_state=seed)
        attack = part[part["Label"] != "BENIGN"].copy()

        # Break each attack into ``n_bursts`` episodes separated by an hour of
        # silence. Real campaigns come in bursts, and it means the episode split
        # protocol is exercised for real rather than always hitting its
        # single-episode fallback.
        if len(attack):
            n_bursts = 4
            burst = np.arange(len(attack)) % n_bursts
            attack["t"] = attack["t"].to_numpy() + burst * 3600.0

        part = pd.concat([benign, attack]).sort_values("t")
        # shift each "day" so the pooled chronological order is realistic
        part["t"] = part["t"] + day_offset * 86400
        part["Timestamp"] = pd.to_datetime(part["t"], unit="s").dt.strftime("%d/%m/%Y %H:%M:%S")
        part.drop(columns=["t"]).to_csv(out_dir / fname, index=False)
        day_offset += 1
    return out_dir


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="synthetic/datasets/cicids2017")
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    d = write_dataset(a.out, a.seed)
    print(f"wrote synthetic CICIDS2017 (TrafficLabelling shape) -> {d}")
    for f in sorted(Path(d).glob("*.csv")):
        print(f"  {f.name:<52s} {f.stat().st_size/1e6:6.2f} MB")

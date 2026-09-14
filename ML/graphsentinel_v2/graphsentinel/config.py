"""
Centralised configuration for GraphSentinel v2.

Everything that used to be scattered across notebook cells lives here. The
config is a plain dataclass tree so it round-trips to JSON and gets embedded
verbatim into every checkpoint and every exported model card -- which is how
the backend learns the feature contract instead of having it hard-coded.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------
# Label taxonomy
# --------------------------------------------------------------------------
# Index 0 is BENIGN by convention; every downstream head assumes that.
CLASS_NAMES: List[str] = ["BENIGN", "DDoS", "PortScan", "Botnet", "SSHBrute", "DoSHulk"]
CLASS_TO_IDX: Dict[str, int] = {name: i for i, name in enumerate(CLASS_NAMES)}
NUM_CLASSES: int = len(CLASS_NAMES)

# CICIDS2017 raw label -> canonical class. Raw labels are stripped before lookup,
# so only the stripped form needs to appear here.
RAW_LABEL_MAP: Dict[str, str] = {
    "BENIGN": "BENIGN",
    "DDoS": "DDoS",
    "PortScan": "PortScan",
    "Bot": "Botnet",
    "SSH-Patator": "SSHBrute",
    "DoS Hulk": "DoSHulk",
}

# --------------------------------------------------------------------------
# Taxonomies
# --------------------------------------------------------------------------
# WHY MORE THAN ONE. The split protocol needs each family to have several
# separate attack BURSTS; with one burst it can only cut inside that burst, and
# train and test come from the same attack instance. Measured on the real data
# by the label audit:
#
#     class        cicids6 bursts   grouped bursts   built from
#     BruteForce         1                2          FTP-Patator + SSH-Patator
#     DoS                2                6          Hulk + GoldenEye +
#                                                    slowloris + Slowhttptest
#     PortScan           4                4
#     Botnet             2                2
#     DDoS               1                1          (still one burst)
#
# Grouping is not just more rows: each CICIDS2017 subtype ran at a different
# time of day, so it multiplies the burst count and makes a genuine
# episode-held-out split possible for DoS and BruteForce.
#
# HONEST CAVEAT. Under "grouped", leave-one-subtype-out measures transfer
# BETWEEN SUBTYPES (train on Hulk + GoldenEye, test on slowloris), which is a
# stronger test than leave-one-burst-out -- but it must be named as such, not
# reported as ordinary episode generalisation. DDoS still has one burst either
# way, so its number keeps the within-episode caveat regardless.
TAXONOMIES: Dict[str, Dict[str, Any]] = {
    "cicids6": {
        "classes": ["BENIGN", "DDoS", "PortScan", "Botnet", "SSHBrute", "DoSHulk"],
        "map": {
            "BENIGN": "BENIGN",
            "DDoS": "DDoS",
            "PortScan": "PortScan",
            "Bot": "Botnet",
            "SSH-Patator": "SSHBrute",
            "DoS Hulk": "DoSHulk",
        },
    },
    # MEASURED 2026-08-29 by the topology audit, and it changes the design:
    #
    #   class        flows     src IPs  dst IPs  dst ports   top source
    #   DDoS       128,027        2        2         4       172.16.0.1
    #   DoS        252,661        1        1         1       172.16.0.1
    #   PortScan   158,930        1        1     1,000       172.16.0.1
    #   BruteForce  13,835        1        1         3       172.16.0.1
    #   Botnet       1,966        8        8       706       205.174.165.73
    #
    # FOUR OF THE FIVE ATTACK FAMILIES ARE THE SAME (source, victim) PAIR:
    # 172.16.0.1 -> 192.168.10.50. CICIDS2017's attacker network sits behind
    # one NATed address, so as a GRAPH these attacks are one edge pair wearing
    # different labels. DDoS is a two-machine flood, not a distributed one.
    #
    # What that means, class by class:
    #   PortScan    separable -- 1,000 destination ports vs 1-4. Port entropy.
    #   BruteForce  separable -- ports 21/22, distinctive packet-size ratios.
    #   DoS / DDoS  NOT separable -- same source, same victim, same port 80,
    #               both floods. Fan-in ratio 2.0x. No aggregator, centrality
    #               feature or loss reweighting can create a distinction the
    #               capture does not contain. Merged into Volumetric_Flood.
    #   Botnet      the only family with real multi-host structure, and the
    #               only one that has never scored above 0.17.
    "flood4": {
        "classes": ["BENIGN", "Volumetric_Flood", "PortScan", "BruteForce",
                    "Botnet"],
        "map": {
            "BENIGN": "BENIGN",
            "DDoS": "Volumetric_Flood",
            "DoS Hulk": "Volumetric_Flood",
            "DoS GoldenEye": "Volumetric_Flood",
            "DoS slowloris": "Volumetric_Flood",
            "DoS Slowhttptest": "Volumetric_Flood",
            "PortScan": "PortScan",
            "FTP-Patator": "BruteForce",
            "SSH-Patator": "BruteForce",
            "Bot": "Botnet",
        },
    },
    "grouped": {
        "classes": ["BENIGN", "DDoS", "PortScan", "Botnet", "BruteForce", "DoS"],
        "map": {
            "BENIGN": "BENIGN",
            "DDoS": "DDoS",
            "PortScan": "PortScan",
            "Bot": "Botnet",
            "FTP-Patator": "BruteForce",
            "SSH-Patator": "BruteForce",
            "DoS Hulk": "DoS",
            "DoS GoldenEye": "DoS",
            "DoS slowloris": "DoS",
            "DoS Slowhttptest": "DoS",
        },
    },
}

# Families deliberately NOT mapped by either taxonomy. They are not waste --
# a family the model has never seen is the only defensible way to measure
# novel-attack behaviour, so they are the open-set test set.
UNSEEN_FAMILY_LABELS: List[str] = [
    "Web Attack  Brute Force",
    "Web Attack  XSS",
    "Web Attack  Sql Injection",
    "Infiltration",
    "Heartbleed",
]
UNSEEN_FAMILY_FILES: List[str] = [
    "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
    "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv",
]


def taxonomy_fingerprint() -> str:
    """Short hash of the ACTIVE class list and label map.

    Comparing the taxonomy by name is not enough: someone can edit a mapping
    without renaming it, and a checkpoint written before taxonomies existed
    carries no name at all. The fingerprint catches both, and an absent
    fingerprint is treated as "unknown", never as "matches".
    """
    import hashlib
    payload = json.dumps(
        {"classes": list(CLASS_NAMES), "map": dict(sorted(RAW_LABEL_MAP.items()))},
        sort_keys=True,
    )
    return hashlib.blake2b(payload.encode(), digest_size=8).hexdigest()


def apply_taxonomy(name: str) -> int:
    """Switch the active taxonomy IN PLACE and return the class count.

    The module-level containers are mutated rather than rebound, because every
    module does `from .config import CLASS_NAMES` and therefore holds a
    reference to these exact objects. Rebinding here would leave them pointing
    at the old list and silently mis-label everything downstream -- the class
    of bug this project has spent a week finding.
    """
    if name not in TAXONOMIES:
        raise ValueError(f"Unknown taxonomy {name!r}; choose from {list(TAXONOMIES)}")
    spec = TAXONOMIES[name]
    CLASS_NAMES[:] = list(spec["classes"])
    CLASS_TO_IDX.clear()
    CLASS_TO_IDX.update({n: i for i, n in enumerate(CLASS_NAMES)})
    RAW_LABEL_MAP.clear()
    RAW_LABEL_MAP.update(spec["map"])
    return len(CLASS_NAMES)

# Which capture day each CSV belongs to. Used by the day-holdout split so a
# whole day can be left out of training.
FILE_DAYS: Dict[str, str] = {
    "Tuesday-WorkingHours.pcap_ISCX.csv": "tuesday",
    "Wednesday-workingHours.pcap_ISCX.csv": "wednesday",
    "Friday-WorkingHours-Morning.pcap_ISCX.csv": "friday_am",
    "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv": "friday_pm_ddos",
    "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv": "friday_pm_portscan",
}


@dataclass
class DataConfig:
    """Ingestion, cleaning and splitting."""

    dataset_dir: str = "datasets/cicids2017/"
    processed_dir: str = "processed/"

    # TrafficLabelling_ variant is required: it carries Source IP / Destination IP /
    # Timestamp, without which an IP-as-node graph cannot be built at all.
    require_ip_columns: bool = True

    csv_files: List[str] = field(default_factory=lambda: list(FILE_DAYS.keys()))

    # "cicids6" (default, one raw label per class) or "grouped" (subtypes merged
    # into BruteForce and DoS). See TAXONOMIES above for the burst counts that
    # motivate the choice. Applied by Config.__post_init__, so setting it is
    # enough -- nothing else needs touching.
    taxonomy: str = "cicids6"

    # Capture files held out of training entirely, to be scored afterwards as
    # UNSEEN families. This is the open-set experiment; it is not optional if
    # the project intends to say anything about novel attacks.
    unseen_family_files: List[str] = field(
        default_factory=lambda: list(UNSEEN_FAMILY_FILES)
    )

    # Continuous per-flow columns kept as EDGE attributes. Deliberately short:
    # volumetric headers are trivially spoofable, so they are supporting
    # evidence, not the backbone. Structural features carry the signal.
    edge_feature_cols: List[str] = field(
        default_factory=lambda: [
            "Flow Duration",
            "Total Fwd Packets",
            "Total Backward Packets",
            "Total Length of Fwd Packets",
            "Total Length of Bwd Packets",
            "Fwd Packet Length Max",
            "Bwd Packet Length Max",
            "Flow IAT Mean",
            "Fwd IAT Total",
            "Bwd IAT Total",
            "SYN Flag Count",
            "RST Flag Count",
            "ACK Flag Count",
            "PSH Flag Count",
        ]
    )
    # ENGINEERED edge features to zero at graph-build time, by their name in
    # EDGE_FEATURE_NAMES -- NOT raw CSV column names.
    #
    # These are two different things and confusing them wastes a retrain.
    # edge_feature_cols above lists RAW CICIDS2017 columns ("Total Length of
    # Fwd Packets"). EDGE_FEATURE_NAMES lists the 20 features COMPUTED from
    # them ("log_total_bytes", "byte_asymmetry", ...), several of which share
    # the same raw columns. Removing a raw column would take out three
    # engineered features at once; this knob removes exactly one.
    #
    # Measured 2026-09-13, leave-one-out on test with the epoch-31 checkpoint:
    #     log_total_bytes   +0.0723 macro F1 when zeroed  (BruteForce 0.55 -> 0.91)
    #     iat_burstiness    +0.0451 macro F1 when zeroed  (BruteForce 0.55 -> 0.77)
    # i.e. the model is actively MISLED by them: they are what drives 490 of
    # 792 BruteForce edges into PortScan. Set this and retrain to test whether
    # a model that never saw them does better from the start.
    drop_edge_features: List[str] = field(default_factory=list)

    # Volumetric rate features, kept but flagged so they can be ablated / dropped
    # to prove the model is not leaning on them (see evaluate.evasion_ablation).
    volumetric_cols: List[str] = field(
        default_factory=lambda: ["Flow Bytes/s", "Flow Packets/s"]
    )

    clip_quantile: float = 0.999  # computed per split, never from train->test
    drop_duplicates: bool = True

    # --- splitting -------------------------------------------------------
    # Four protocols, each measuring something different. Report more than one:
    # a single number cannot tell you whether a model generalises.
    #
    # "episode"       DEFAULT. Attack traffic is grouped into contiguous
    #                 episodes (bursts separated by > episode_gap_seconds) and
    #                 whole episodes are assigned to a split. Every class
    #                 appears in train and test, no burst is cut in half, and a
    #                 dead zone separates the boundaries. This is the only
    #                 protocol under which a 6-way classifier can actually be
    #                 trained on CICIDS2017, because the dataset gives each
    #                 attack exactly one capture day.
    # "temporal"      One global chronological cut across pooled traffic. The
    #                 most honest "future traffic" test -- but on CICIDS2017 it
    #                 degenerates into a partial zero-day test, since DDoS and
    #                 PortScan only ever occur in the final hours. Use it as an
    #                 evaluation, not as the training protocol.
    # "host_holdout"  Attacker/victim IPs in test are disjoint from those in
    #                 train. Answers "does this generalise to a NEW attacker
    #                 performing the same technique" -- which is what a
    #                 memorised signature fails.
    # "attack_holdout" One family never seen in training at all -> true zero-day.
    split_strategy: str = "episode"
    train_frac: float = 0.70
    val_frac: float = 0.15
    holdout_days: List[str] = field(
        default_factory=lambda: ["friday_pm_ddos", "friday_pm_portscan"]
    )
    holdout_attacks: List[str] = field(default_factory=lambda: ["Botnet"])
    # Gap (seconds) discarded either side of a split boundary so no single
    # attack burst straddles train and test.
    split_gap_seconds: int = 300
    # Silence longer than this starts a new attack episode.
    episode_gap_seconds: int = 120
    # A class with fewer episodes than this cannot be episode-split cleanly; it
    # falls back to a chronological cut with a dead zone, and says so.
    min_episodes_for_split: int = 3


@dataclass
class GraphConfig:
    """Window -> graph conversion. Nodes are IPs, edges are flows."""

    # A window is now a *time* interval, not a fixed flow count: 500 flows is a
    # different amount of wall-clock time during a DDoS than at 3am.
    window_seconds: int = 60
    window_stride_seconds: int = 60  # == window_seconds means non-overlapping
    min_edges_per_graph: int = 8
    max_edges_per_graph: int = 200_000  # safety valve for volumetric floods

    # Node identity. "ip" is the real thing; "ip_subnet24" collapses to /24 which
    # bounds node count on very wide scans.
    node_key: str = "ip"
    subnet_fallback_prefix: int = 24

    # Structural node features computed per window (see graph_builder for the
    # authoritative list and order).
    use_structural_features: bool = True
    # Directed flow edges are duplicated in reverse with a direction flag so
    # message passing can travel both ways without losing directionality.
    add_reverse_edges: bool = True

    # Node label = worst class observed on any incident/outgoing flow.
    label_mode: str = "max_severity"


@dataclass
class ModelConfig:
    """Architecture."""

    name: str = "GraphSentinelNet"

    # --- embeddings for categorical fields -------------------------------
    port_vocab_size: int = 1024  # curated well-known ports + buckets + OOV
    port_embed_dim: int = 16
    proto_vocab_size: int = 8
    proto_embed_dim: int = 4

    # --- encoders ---------------------------------------------------------
    edge_hidden: int = 64
    node_hidden: int = 128
    hidden_channels: int = 128

    # --- message passing ---------------------------------------------------
    conv_type: str = "gatv2"  # gatv2 | sage_median | sage_max
    num_layers: int = 2  # 2, not 3: a 3-hop field over a dense window over-smooths
    heads: int = 4
    dropout: float = 0.3
    attn_dropout: float = 0.1
    residual: bool = True
    jumping_knowledge: str = "cat"  # cat | max | none

    # --- memory ------------------------------------------------------------
    use_memory: bool = True
    memory_dim: int = 64
    memory_capacity: int = 262_144  # slots; see docs/MEMORY.md for the sizing math
    memory_ttl_seconds: int = 1800
    memory_hash_tail: bool = True  # tail IPs share hashed slots instead of evicting

    # --- heads --------------------------------------------------------------
    num_classes: int = NUM_CLASSES
    edge_head: bool = True  # per-flow classification -> SDN drop rules
    node_head: bool = True

    # --- joint self-supervised reconstruction (see models/recon.py) ---------
    # Anchors the JK embedding against collapsing unmodelled structural
    # variance. ON by default: the ablation improved open-set FPR@95TPR on the
    # collapse family in 3/3 seeds at no closed-set cost (macro F1 -0.003 mean
    # over 6 runs). Magnitude is unverified on real traffic -- see
    # docs/OPEN_SET.md section 9.
    recon_enabled: bool = True
    recon_weight: float = 0.3
    recon_edge_weight: float = 1.0    # masked edge-attribute recon (primary)
    recon_link_weight: float = 0.5    # degree-matched link recon (secondary)
    recon_node_weight: float = 0.2    # structural profile recon (stabiliser)
    edge_mask_rate: float = 0.15
    recon_warmup_epochs: int = 3


@dataclass
class LossConfig:
    focal_gamma: float = 2.0
    # alpha per class; None -> derived from inverse effective-number weighting.
    focal_alpha: Optional[List[float]] = None
    effective_number_beta: float = 0.9999
    label_smoothing: float = 0.02
    degree_penalty_weight: float = 0.05  # graph-aware regulariser
    # 2.0, not 0.5. The edge head has 993-823,170 labels per class; the node
    # head has 24-125 for every attack class. Weighting the node head higher
    # spends gradient on the labels that barely exist.
    edge_loss_weight: float = 2.0  # node head : edge head balance


@dataclass
class TrainConfig:
    epochs: int = 60
    batch_size: int = 16  # graphs per batch (ignored when model.use_memory)
    # With memory on, windows must be seen one at a time and in order, so the
    # effective batch comes from gradient accumulation instead.
    grad_accum_steps: int = 8
    learning_rate: float = 2e-3
    weight_decay: float = 1e-4
    gradient_clip: float = 1.0
    mixed_precision: bool = True
    scheduler: str = "cosine_warmup"
    warmup_epochs: int = 3
    early_stop_patience: int = 12
    # Selects the checkpoint. edge_macro_f1, NOT node: validation holds only
    # 2-26 attack nodes per class, so node_macro_f1 swings on noise and has
    # demonstrably chosen a worse edge model. The edge head carries 993-823k
    # labels per class and is what the SDN layer consumes.
    early_stop_metric: str = "edge_macro_f1"
    # Abort if any class loses more than this share of its training edges to
    # non-finite windows. Not a tuning knob -- a class above this threshold was
    # not trained, so every metric bearing its name is meaningless.
    max_class_edge_loss: float = 0.02
    # Fit per-class decision offsets on VALIDATION after training and report
    # raw and adjusted metrics side by side. Fixes classes that are well ranked
    # but never win the argmax; cannot fix a class the model cannot see.
    # OFF by default, on evidence. The idea is sound -- a class can be well
    # ranked and still lose the argmax -- but on CICIDS2017 the offsets do not
    # transfer from validation to test, three runs in a row:
    #     run 4  DDoS     0.5404 -> 0.1183   macro +0.14 by sacrificing a class
    #     run 5  SSHBrute 0.8647 -> 0.2308   macro -0.0091
    #     run 6  Botnet   0.1398 -> 0.0000   macro -0.0397  (and it PASSED the
    #                                        held-out gate at +0.0467)
    # The reason is sample size: validation holds 44 Botnet and 118 SSHBrute
    # edges against 266 and 344 in test, so a per-class offset is fitted on a
    # few dozen examples and cannot generalise. Set True only if you have a
    # validation split large enough per class -- min_holdout_per_class below
    # is the guard that enforces it.
    fit_logit_adjustment: bool = False
    min_holdout_per_class: int = 200
    # No class may lose more than this much F1 to the offsets. Without it,
    # macro F1 happily trades one working class for two zeros -- measured
    # 2026-08-29: DDoS 0.5404 -> 0.1183 while the macro "improved" by 0.14.
    max_class_f1_drop: float = 0.05
    num_workers: int = 2
    seed: int = 42
    # Windows are fed in chronological order within an epoch so node memory is
    # updated in the order the traffic actually happened.
    preserve_temporal_order: bool = True
    memory_detach_every: int = 1  # TBPTT horizon in windows


@dataclass
class ExportConfig:
    model_dir: str = "models/"
    export_torchscript: bool = True
    export_onnx: bool = True
    # 18, not 17: the GNN's scatter reduce uses "max"/"min", which the opset-17
    # downgrade path rejects outright.
    onnx_opset: int = 18
    write_compat_shim: bool = True
    contract_version: str = "2.0.0"


@dataclass
class Config:
    data: DataConfig = field(default_factory=DataConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    loss: LossConfig = field(default_factory=LossConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

    base_dir: str = "."
    log_dir: str = "logs/"
    checkpoint_dir: str = "checkpoints/"

    def __post_init__(self) -> None:
        """Apply the taxonomy and keep num_classes consistent with it.

        Done here rather than at the call site so a config loaded from a
        checkpoint restores its own taxonomy automatically. A model trained on
        six classes named one way must never be evaluated against six classes
        named another -- the labels would line up by index and be silently
        wrong.
        """
        self.sync_taxonomy()

    def sync_taxonomy(self) -> None:
        n = apply_taxonomy(self.data.taxonomy)
        self.model.num_classes = n

    # ---------------- path helpers ----------------
    def path(self, *parts: str) -> Path:
        return Path(self.base_dir).joinpath(*parts)

    @property
    def dataset_path(self) -> Path:
        return self.path(self.data.dataset_dir)

    @property
    def processed_path(self) -> Path:
        return self.path(self.data.processed_dir)

    @property
    def model_path(self) -> Path:
        return self.path(self.export.model_dir)

    @property
    def log_path(self) -> Path:
        return self.path(self.log_dir)

    @property
    def checkpoint_path(self) -> Path:
        return self.path(self.checkpoint_dir)

    def ensure_dirs(self) -> None:
        for p in (
            self.processed_path,
            self.model_path,
            self.log_path,
            self.checkpoint_path,
        ):
            p.mkdir(parents=True, exist_ok=True)

    # ---------------- serialisation ----------------
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Config":
        return cls(
            data=DataConfig(**d.get("data", {})),
            graph=GraphConfig(**d.get("graph", {})),
            model=ModelConfig(**d.get("model", {})),
            loss=LossConfig(**d.get("loss", {})),
            train=TrainConfig(**d.get("train", {})),
            export=ExportConfig(**d.get("export", {})),
            base_dir=d.get("base_dir", "."),
            log_dir=d.get("log_dir", "logs/"),
            checkpoint_dir=d.get("checkpoint_dir", "checkpoints/"),
        )

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def with_overrides(self, **kwargs: Any) -> "Config":
        return replace(self, **kwargs)


def default_config(base_dir: str = ".") -> Config:
    cfg = Config()
    cfg.base_dir = base_dir
    return cfg

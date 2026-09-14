"""GraphSentinel v2 -- graph-based network intrusion detection.

Nodes are hosts, edges are flows, ports are embeddings, the loss is focal, the
split protocol is leakage-free, and the model emits per-flow verdicts a
software-defined network can actually enforce.
"""
from .config import CLASS_NAMES, NUM_CLASSES, Config, default_config

__version__ = "2.0.0"

__all__ = [
    "Config",
    "default_config",
    "CLASS_NAMES",
    "NUM_CLASSES",
    "__version__",
]

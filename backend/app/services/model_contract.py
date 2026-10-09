# [WSL2]
"""GraphSentinel v2 model contract — loaded from `model_card.json` at startup.

WHY THIS MODULE EXISTS

The v2 model indexes its output logits POSITIONALLY. `edge_logits[:, 3]` is
whatever class sits at index 3 of the card's class list, and nothing in the
tensor says which name that is. So a reordered, truncated or stale class list
does not raise — it silently relabels every prediction in the product. The
training package hit exactly this: `CLASS_NAMES` there is a mutable module
global, and read before `Config.from_dict` rewrites it, index 3 reads `Botnet`
where the live model means `BruteForce`.

Therefore: the class list, the feature names and their ORDER are read from the
card at runtime and never hardcoded here. The only constant in this file is the
contract VERSION this code was written against, because checking a version
against itself proves nothing.

Failing loudly at boot beats mislabelling traffic silently.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The contract revision this backend was written against. A card declaring
# anything else has not been reviewed against this code — refuse to boot rather
# than guess which fields moved.
EXPECTED_CONTRACT_VERSION = "2.0.0"

# sha256 over the ORDERED class names and ORDERED feature names of the contract
# above. See `contract_fingerprint()` for exactly what is hashed.
#
# ON THE RULE "never hardcode a class list in the backend": this is a hash, not
# a list. No code here enumerates class or feature names — every label, index
# and ordering still comes from the card at runtime. The fingerprint exists to
# serve the same purpose the rule does: the backend indexes logits POSITIONALLY,
# so a card that reorders its classes while keeping `contract_version` at 2.0.0
# relabels every prediction with nothing in the output to show for it. Comparing
# names as a set cannot catch that; comparing order can.
#
# Changing the class list, the feature list, or either ORDER is a contract
# change: bump EXPECTED_CONTRACT_VERSION and this fingerprint together.
EXPECTED_CONTRACT_FINGERPRINT = "b7538663677e93dec1a6df255a5fa253b4191fdc4846c7893c8e984fbe52e63f"

# The one class name the backend needs to know by name rather than by index:
# threat score is defined by the card as `1 - softmax(logits)[BENIGN]`, so the
# benign class has to be identifiable. Its POSITION is still read from the card.
BENIGN_CLASS = "BENIGN"


class ContractError(RuntimeError):
    """Raised when the model card is missing, unreadable, or not the contract
    this code was written against. Always fatal at startup — never downgraded
    to a warning, because every downstream label depends on getting this right.
    """


@dataclass(frozen=True)
class ModelContract:
    """An immutable, validated view of `model_card.json`."""

    contract_version: str
    classes: tuple[str, ...]          # ORDER IS THE CONTRACT — logit index -> name
    node_feature_names: tuple[str, ...]
    edge_feature_names: tuple[str, ...]
    port_vocab_size: int
    proto_vocab_size: int
    window_seconds: int
    min_edges_per_graph: int
    scaling_mode: str
    edge_logit_bias: Any
    metrics_split: str | None         # "validation" on cards that label it
    card_sha256: str
    card_path: str

    # -- derived ------------------------------------------------------------
    @property
    def benign_index(self) -> int:
        return self.classes.index(BENIGN_CLASS)

    @property
    def attack_classes(self) -> tuple[str, ...]:
        """Every class that is not BENIGN, in card order."""
        return tuple(c for c in self.classes if c != BENIGN_CLASS)

    @property
    def node_feature_count(self) -> int:
        return len(self.node_feature_names)

    @property
    def edge_feature_count(self) -> int:
        return len(self.edge_feature_names)

    def class_name(self, index: int) -> str:
        """Map a logit index to its class NAME via the card's ordering.

        Raises rather than returning a placeholder: an out-of-range index means
        the loaded weights and the card disagree on class count, and inventing
        a label there is how a mislabelled detection reaches an operator.
        """
        if not 0 <= index < len(self.classes):
            raise ContractError(
                f"Class index {index} is outside the contract's {len(self.classes)} "
                f"classes {list(self.classes)}. The weights and the card disagree."
            )
        return self.classes[index]


def contract_fingerprint(
    classes: list[str] | tuple[str, ...],
    node_features: list[str] | tuple[str, ...],
    edge_features: list[str] | tuple[str, ...],
) -> str:
    """sha256 over the ordered class and feature names.

    Order-sensitive by design: `["BENIGN", "PortScan", ...]` and
    `["BENIGN", "Volumetric_Flood", ...]` hash differently, which is the whole
    point. Uses compact separators so the digest depends on content, not on how
    the card happened to be formatted.
    """
    payload = json.dumps(
        {
            "classes": list(classes),
            "node_features": list(node_features),
            "edge_features": list(edge_features),
        },
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require(card: dict, path: str) -> Any:
    """Fetch a dotted path out of the card or fail with the path that's missing."""
    node: Any = card
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ContractError(
                f"model_card.json is missing required field '{path}'. "
                f"This is not a v{EXPECTED_CONTRACT_VERSION} contract."
            )
        node = node[part]
    return node


def load_contract(model_dir: str | Path) -> ModelContract:
    """Read and validate `model_card.json`. Raises ContractError on any problem.

    Read with an EXPLICIT utf-8 encoding. `Path.read_text()` defaults to the
    locale codec, which is cp1252 on Windows and raises UnicodeDecodeError on
    the first non-ASCII byte (an em-dash in a note is enough). The backend does
    not depend on the card happening to be ASCII, nor on the training package
    having got its own encoding right.
    """
    model_dir = Path(model_dir)
    card_path = model_dir / "model_card.json"

    if not card_path.is_file():
        raise ContractError(
            f"model_card.json not found at {card_path}.\n"
            "The backend cannot score traffic without the model contract: class "
            "names, feature names and their order all come from it at runtime.\n"
            "See INTEGRATION.md for how to fetch the model artefacts."
        )

    raw = card_path.read_bytes()
    try:
        card = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ContractError(f"model_card.json at {card_path} is not valid UTF-8: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"model_card.json at {card_path} is not valid JSON: {exc}") from exc

    if not isinstance(card, dict):
        raise ContractError(f"model_card.json at {card_path} is not a JSON object.")

    version = card.get("contract_version")
    if version != EXPECTED_CONTRACT_VERSION:
        raise ContractError(
            f"model_card.json declares contract_version {version!r}, but this "
            f"backend was written against {EXPECTED_CONTRACT_VERSION!r}.\n"
            "Field names and output semantics may have moved. Refusing to boot "
            "rather than mislabel traffic against an unreviewed contract."
        )

    classes = _require(card, "outputs.classes")
    if not isinstance(classes, list) or not classes:
        raise ContractError("model_card.json outputs.classes must be a non-empty list.")
    if len(set(classes)) != len(classes):
        raise ContractError(f"model_card.json outputs.classes has duplicates: {classes}")
    if BENIGN_CLASS not in classes:
        raise ContractError(
            f"model_card.json outputs.classes has no {BENIGN_CLASS!r} entry: {classes}. "
            "Threat score is defined as 1 - P(BENIGN); it cannot be computed."
        )

    node_names = _require(card, "inputs.node_features.names")
    edge_names = _require(card, "inputs.edge_features.names")
    for label, names, count_path in (
        ("node", node_names, "inputs.node_features.count"),
        ("edge", edge_names, "inputs.edge_features.count"),
    ):
        if not isinstance(names, list) or not names:
            raise ContractError(f"model_card.json {label} feature names must be a non-empty list.")
        declared = _require(card, count_path)
        if declared != len(names):
            raise ContractError(
                f"model_card.json {label} feature count ({declared}) disagrees with the "
                f"number of names listed ({len(names)}). The card contradicts itself."
            )

    # ORDER CHECK. Everything above validates that the right NAMES are present;
    # this validates that they are in the right ORDER. A reordered class list is
    # the failure mode with no symptom: the model still runs, every logit index
    # still resolves to some name, and every prediction is silently relabelled.
    fingerprint = contract_fingerprint(classes, node_names, edge_names)
    if fingerprint != EXPECTED_CONTRACT_FINGERPRINT:
        raise ContractError(
            f"model_card.json declares contract_version {version!r}, but its class "
            "and feature ordering does not match the contract of that name.\n"
            f"  expected fingerprint: {EXPECTED_CONTRACT_FINGERPRINT}\n"
            f"  card fingerprint    : {fingerprint}\n"
            f"  classes in card     : {list(classes)}\n"
            "The backend indexes logits positionally, so a reordered list relabels "
            "every prediction with nothing in the output to show for it. If this "
            "change is intended, bump EXPECTED_CONTRACT_VERSION and "
            "EXPECTED_CONTRACT_FINGERPRINT together."
        )

    return ModelContract(
        contract_version=version,
        classes=tuple(classes),
        node_feature_names=tuple(node_names),
        edge_feature_names=tuple(edge_names),
        port_vocab_size=int(_require(card, "port_vocabulary.port_vocab_size")),
        proto_vocab_size=int(_require(card, "port_vocabulary.proto_vocab_size")),
        window_seconds=int(_require(card, "graph.window_seconds")),
        # The builder refuses to make a graph below this many flows, so a window
        # under the floor is UNSCORED, not clean. The backend has to surface that.
        min_edges_per_graph=int(card.get("config", {}).get("graph", {}).get("min_edges_per_graph", 0)),
        scaling_mode=str(_require(card, "scaling.mode")),
        edge_logit_bias=card.get("outputs", {}).get("edge_logit_bias"),
        metrics_split=card.get("metrics_split"),
        card_sha256=hashlib.sha256(raw).hexdigest(),
        card_path=str(card_path),
    )

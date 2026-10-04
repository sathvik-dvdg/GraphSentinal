"""
Detection -> enforcement translation.

Closes the SDN gap. A node-level logit says "10.0.0.7 scores 0.91". A
controller cannot install that. It needs a *match*: which source, which
destination, which protocol, which port -- and an action, a priority, and a
lifetime.

The edge head gives exactly that, because every edge in the graph is one flow
with its endpoints and its 5-tuple attached. This module turns scored edges
into OpenFlow rules and, importantly, decides which ones are safe to install.

THE POLICY IS NOT DEFINED HERE. Actions, floors, timeouts and priorities come
from the caller: the backend's validated ``MitigationPolicy`` (one entry per
class of the model card, an explicit ``alert_only`` for a class that must never
be enforced), sent with every request. Without a policy the translator emits no
rules at all. This module used to carry its own table keyed on the retired
six-class taxonomy (DDoS, SSHBrute, DoSHulk, ...), under which Volumetric_Flood
and BruteForce could never fire and Botnet was ``drop_and_quarantine`` at 0.80;
it ran in the service while the backend's policy reached nothing. It is gone,
and ``validate_policy`` refuses any class the live taxonomy does not have.

Every attack-classified flow that does not become a rule is recorded as
WITHHELD with its reason, so an operator sees what was held back and why.

Safety rails, because an IDS with write access to the network is a
denial-of-service tool if it is wrong:

  * a confidence floor per class (the policy's),
  * a corroboration rule (a flow's own endpoint must also look bad),
  * a never-block allowlist (gateways, DNS, the controller itself),
  * a hard cap on rules per interval,
  * finite idle/hard timeouts on everything -- no permanent rules,
  * dry-run mode by default.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import torch

from ..config import CLASS_NAMES

#: An entry with this action is recognised, scored and reported, and never
#: turned into a rule.
ACTION_ALERT_ONLY = "alert_only"
_REQUIRED = ("action", "idle", "hard", "priority", "min_conf")

#: Why an attack-classified flow did not become a rule.
WITHHELD_REASONS = ("no_policy", "class_suppressed", "below_floor", "allowlisted",
                    "node_corroboration_absent", "rule_cap")


class PolicyRejected(ValueError):
    """The policy names a class the live taxonomy does not have, or is malformed."""


def validate_policy(policy: Dict[str, dict]) -> Dict[str, dict]:
    """Check a policy against the LIVE class list. Returns a copy."""
    live = [c for c in CLASS_NAMES if c != "BENIGN"]
    unknown = [c for c in policy if c not in live]
    if unknown:
        raise PolicyRejected(
            f"policy names {unknown}, which are not attack classes of the live "
            f"taxonomy {live}. A rule path keyed on another taxonomy is refused.")
    for cls, entry in policy.items():
        missing = [k for k in _REQUIRED if k not in entry]
        if missing:
            raise PolicyRejected(f"policy entry for {cls} lacks {missing}")
    return {c: dict(e) for c, e in policy.items()}


def policy_sha256(policy: Dict[str, dict]) -> str:
    """Canonical digest of a policy. The backend computes the same digest over
    what it sends and accepts rules only when the service echoes it."""
    blob = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


DEFAULT_ALLOWLIST = ["255.255.255.255", "0.0.0.0"]


@dataclass
class FlowRule:
    """One installable rule plus the evidence that produced it."""

    src_ip: str
    dst_ip: str
    protocol: int
    dst_port: int
    src_port: int
    attack_class: str
    confidence: float
    node_confidence: float
    action: str
    priority: int
    idle_timeout: int
    hard_timeout: int
    table_id: int = 0
    cookie: int = 0
    meter_kbps: Optional[int] = None
    policy_floor: float = 0.0          # the min_conf of the policy that admitted it
    window_start: float = 0.0
    window_end: float = 0.0
    reason: str = ""

    # ------------------------------------------------------------------
    def to_openflow(self) -> dict:
        """OpenFlow 1.3 flow-mod as a plain dict (Ryu / ONOS / OpenDaylight)."""
        match = {
            "eth_type": 0x0800,
            "ipv4_src": self.src_ip,
            "ipv4_dst": self.dst_ip,
            "ip_proto": self.protocol,
        }
        if self.protocol in (6, 17) and self.dst_port > 0:
            key = "tcp_dst" if self.protocol == 6 else "udp_dst"
            match[key] = self.dst_port

        if self.action in ("drop", "drop_port", "drop_and_quarantine"):
            instructions = []  # empty action set == drop in OpenFlow
        elif self.action == "meter":
            instructions = [{"type": "METER", "meter_id": self.cookie or 1}]
        else:
            instructions = [{"type": "APPLY_ACTIONS", "actions": [{"type": "OUTPUT", "port": "NORMAL"}]}]

        return {
            "table_id": self.table_id,
            "priority": self.priority,
            "idle_timeout": self.idle_timeout,
            "hard_timeout": self.hard_timeout,
            "cookie": self.cookie,
            "match": match,
            "instructions": instructions,
        }

    def to_ovs_ofctl(self, bridge: str = "br0") -> str:
        """Copy-pasteable ``ovs-ofctl`` command, useful for lab validation."""
        proto = {6: "tcp", 17: "udp", 1: "icmp"}.get(self.protocol, "ip")
        parts = [
            f"priority={self.priority}",
            proto,
            f"nw_src={self.src_ip}",
            f"nw_dst={self.dst_ip}",
        ]
        if self.protocol in (6, 17) and self.dst_port > 0:
            parts.append(f"tp_dst={self.dst_port}")
        parts += [f"idle_timeout={self.idle_timeout}", f"hard_timeout={self.hard_timeout}"]
        action = "drop" if self.action.startswith("drop") else "normal"
        return f"ovs-ofctl add-flow {bridge} \"{','.join(parts)},actions={action}\""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SDNTranslator:
    allowlist: List[str] = field(default_factory=lambda: list(DEFAULT_ALLOWLIST))
    allow_networks: List[str] = field(default_factory=list)
    max_rules_per_window: int = 50
    require_node_corroboration: bool = True
    node_threshold: float = 0.60
    dry_run: bool = True
    #: The caller's policy. Empty means no rules: every attack-classified flow
    #: is withheld with reason "no_policy".
    policy: Dict[str, dict] = field(default_factory=dict)
    _cookie: int = 1

    def __post_init__(self):
        self._nets = [ipaddress.ip_network(n, strict=False) for n in self.allow_networks]
        self._allow = set(self.allowlist)
        self.policy = validate_policy(self.policy)
        #: Flows the last translate() held back, one record each.
        self.withheld: List[dict] = []

    def set_policy(self, policy: Optional[Dict[str, dict]]) -> None:
        self.policy = validate_policy(policy or {})

    @property
    def policy_sha256(self) -> Optional[str]:
        return policy_sha256(self.policy) if self.policy else None

    def install(self, rules: List[FlowRule], writer) -> dict:
        """The boundary between a rule and a switch.

        In dry-run nothing reaches ``writer``. Outside dry-run this still
        refuses: v2 enforcement is not enabled, and the allowlist does not yet
        cover gateways, DNS and the controller. Enabling it is a code change
        here, not a flag flip somewhere else.
        """
        if self.dry_run:
            return {"dry_run": True, "installed": 0, "would_install": len(rules)}
        raise RuntimeError("v2 rule installation is not enabled; dry_run must stay True")

    def _is_allowlisted(self, ip: str) -> bool:
        if ip in self._allow:
            return True
        if not self._nets:
            return False
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return True  # unparseable -> never act on it
        return any(addr in n for n in self._nets)

    # ------------------------------------------------------------------
    def translate(
        self,
        edge_probs: torch.Tensor | np.ndarray,
        node_probs: torch.Tensor | np.ndarray,
        edge_index: torch.Tensor | np.ndarray,
        node_ips: Sequence[str],
        dst_ports: Sequence[int],
        src_ports: Sequence[int],
        protocols: Sequence[int],
        real_edge_mask: Optional[np.ndarray] = None,
        window_start: float = 0.0,
        window_end: float = 0.0,
    ) -> List[FlowRule]:
        """Score every flow, keep the ones that clear policy, emit rules.

        Every attack-classified flow that is not emitted is recorded in
        ``self.withheld`` with its reason.
        """
        self.withheld = []
        ep = edge_probs.detach().cpu().numpy() if isinstance(edge_probs, torch.Tensor) else np.asarray(edge_probs)
        npb = node_probs.detach().cpu().numpy() if isinstance(node_probs, torch.Tensor) else np.asarray(node_probs)
        ei = edge_index.detach().cpu().numpy() if isinstance(edge_index, torch.Tensor) else np.asarray(edge_index)

        idx = np.arange(ep.shape[0])
        if real_edge_mask is not None:
            idx = idx[np.asarray(real_edge_mask, dtype=bool)]
        if idx.size == 0:
            return []

        pred = ep[idx].argmax(axis=1)
        conf = ep[idx].max(axis=1)
        keep = pred > 0
        idx, pred, conf = idx[keep], pred[keep], conf[keep]
        if idx.size == 0:
            return []

        order = np.argsort(-conf)
        idx, pred, conf = idx[order], pred[order], conf[order]

        node_threat = 1.0 - npb[:, 0] if npb.ndim == 2 else npb
        rules: List[FlowRule] = []
        seen: set = set()

        for e, cls_id, c in zip(idx.tolist(), pred.tolist(), conf.tolist()):
            cls = CLASS_NAMES[cls_id]
            s_node, d_node = int(ei[0, e]), int(ei[1, e])
            src_ip, dst_ip = str(node_ips[s_node]), str(node_ips[d_node])
            proto = int(protocols[e])
            dport = int(dst_ports[e])
            policy = self.policy.get(cls)

            def withhold(reason: str) -> None:
                self.withheld.append({
                    "src_ip": src_ip, "dst_ip": dst_ip, "protocol": proto,
                    "dst_port": dport, "attack_class": cls, "confidence": float(c),
                    "policy_floor": None if policy is None else policy["min_conf"],
                    "reason": reason})

            if policy is None:
                withhold("no_policy")
                continue
            if policy["action"] == ACTION_ALERT_ONLY:
                withhold("class_suppressed")
                continue
            if c < policy["min_conf"]:
                withhold("below_floor")
                continue
            if self._is_allowlisted(src_ip) or self._is_allowlisted(dst_ip):
                withhold("allowlisted")
                continue

            n_conf = float(node_threat[s_node])
            if self.require_node_corroboration and n_conf < self.node_threshold:
                # The flow looks bad but its own source does not. Alert, do not
                # enforce -- one odd flow is not grounds for cutting a host off.
                withhold("node_corroboration_absent")
                continue
            if len(rules) >= self.max_rules_per_window:
                withhold("rule_cap")
                continue
            # Dedup key: one rule per (src, dst, proto, port) per window.
            key = (src_ip, dst_ip, proto, dport if policy["action"] == "drop_port" else -1)
            if key in seen:
                continue
            seen.add(key)

            self._cookie += 1
            rules.append(
                FlowRule(
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    protocol=proto,
                    dst_port=dport,
                    src_port=int(src_ports[e]),
                    attack_class=cls,
                    confidence=float(c),
                    node_confidence=n_conf,
                    action=policy["action"],
                    priority=policy["priority"],
                    idle_timeout=policy["idle"],
                    hard_timeout=policy["hard"],
                    cookie=self._cookie,
                    meter_kbps=policy.get("meter_kbps"),
                    policy_floor=float(policy["min_conf"]),
                    window_start=window_start,
                    window_end=window_end,
                    reason=(
                        f"{cls} flow at p={c:.3f}; source host threat "
                        f"{n_conf:.3f}; window [{window_start:.0f},{window_end:.0f}]"
                    ),
                )
            )

        return rules

    def withheld_summary(self) -> Dict[str, Dict[str, int]]:
        """{class: {reason: count}} for the last translate()."""
        out: Dict[str, Dict[str, int]] = {}
        for w in self.withheld:
            by = out.setdefault(w["attack_class"], {})
            by[w["reason"]] = by.get(w["reason"], 0) + 1
        return out

    # ------------------------------------------------------------------
    def emit(self, rules: List[FlowRule], path: Optional[str] = None) -> dict:
        payload = {
            "generated_at": time.time(),
            "dry_run": self.dry_run,
            "policy_sha256": self.policy_sha256,
            "count": len(rules),
            "rules": [r.to_dict() for r in rules],
            "openflow": [r.to_openflow() for r in rules],
            "ovs_ofctl": [r.to_ovs_ofctl() for r in rules],
        }
        if path:
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
        return payload

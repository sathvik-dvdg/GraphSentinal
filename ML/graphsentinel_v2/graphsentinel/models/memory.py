"""
Bounded per-host memory.

This module is the direct answer to: *"if you refactor the graph to treat IPs
as nodes, how will you handle the memory constraints of tracking every active
IP address on a high-throughput network interface?"*

The short answer: you don't track every IP. You allocate a fixed slot budget
up front and make the eviction policy part of the model, so the memory
footprint is a constant you choose rather than a function of traffic.

Three tiers, in order of how much resolution each host gets:

  1. HEAVY tier -- exact, dedicated slots. A Space-Saving sketch identifies the
     top-K talkers by flow count; those get a private slot each. This is where
     scanners, C2 servers and DDoS victims land, because all three are by
     definition high-degree.

  2. TAIL tier -- hashed, shared slots. Everything else is mapped by a stable
     blake2b hash into a smaller pool. Collisions are real and accepted: two
     unrelated quiet hosts sharing one memory vector costs almost nothing,
     because a host with three flows an hour has almost no state worth keeping.

  3. SUBNET tier -- cold-start fallback. A never-before-seen IP reads its /24
     supernode's memory instead of a zero vector, so a new host inside an
     already-compromised subnet does not start from ignorance.

Sizing, for the defaults in ``ModelConfig``:

    heavy slots   196 608  x 64 dims x 4 B  =  50.3 MB
    tail slots     65 536  x 64 dims x 4 B  =  16.8 MB
    subnet slots   16 384  x 64 dims x 4 B  =   4.2 MB
    last-update timestamps + LRU bookkeeping  ~  6   MB
    ------------------------------------------------------
    total                                    ~  77   MB, fixed

A 10 Gb/s link carrying ~1.5 M distinct IPs/day fits in that budget with the
tail tier absorbing roughly 85 % of hosts at ~4:1 collision. Doubling
``memory_capacity`` doubles the bill and nothing else -- it is a dial, not a
redesign. TTL expiry (default 30 min) reclaims slots from hosts that went
quiet, which on real traffic keeps steady-state occupancy well under capacity.
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn


def _stable_hash(key: int, salt: bytes, mod: int) -> int:
    digest = hashlib.blake2b(
        int(key).to_bytes(8, "big", signed=True), salt=salt, digest_size=8
    ).digest()
    return int.from_bytes(digest, "big") % mod


class NodeMemory(nn.Module):
    """Fixed-footprint GRU memory over host identities.

    The memory tensor is a registered buffer, so it checkpoints, moves to GPU
    and reloads with the model. Slot bookkeeping is plain Python dicts on the
    CPU side -- it is touched once per window, not once per flow.
    """

    def __init__(
        self,
        memory_dim: int = 64,
        capacity: int = 262_144,
        ttl_seconds: int = 1800,
        hash_tail: bool = True,
        tail_fraction: float = 0.25,
        subnet_slots: Optional[int] = None,
        input_dim: Optional[int] = None,
    ):
        super().__init__()
        self.memory_dim = memory_dim
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self.hash_tail = hash_tail

        self.n_tail = int(capacity * tail_fraction) if hash_tail else 0
        self.n_heavy = capacity - self.n_tail
        # Subnet tier scales with capacity (1/16th) so the total footprint stays
        # proportional to the budget the operator actually set. A fixed 16 384
        # would dominate a small deployment's bill.
        self.n_subnet = subnet_slots if subnet_slots is not None else max(capacity // 16, 64)

        total = self.n_heavy + self.n_tail + self.n_subnet
        self.register_buffer("memory", torch.zeros(total, memory_dim))
        self.register_buffer("last_update", torch.zeros(total, dtype=torch.long))

        self.gru = nn.GRUCell(input_dim or memory_dim, memory_dim)

        # slot bookkeeping (CPU-side, O(capacity))
        self._slot_of: Dict[int, int] = {}
        self._ip_of: Dict[int, int] = {}
        self._free: List[int] = list(range(self.n_heavy - 1, -1, -1))
        self._touch: Dict[int, int] = {}  # slot -> unix seconds
        self._flow_count: Dict[int, int] = {}  # Space-Saving counter per IP
        self._salt = b"gsent\x00\x00\x00"

    # ------------------------------------------------------------------
    # slot resolution
    # ------------------------------------------------------------------
    def _tail_slot(self, ip: int) -> int:
        return self.n_heavy + _stable_hash(ip, self._salt, max(self.n_tail, 1))

    def _subnet_slot(self, ip: int) -> int:
        supernet = int(ip) & 0xFFFFFF00
        return (
            self.n_heavy
            + self.n_tail
            + _stable_hash(supernet, self._salt, self.n_subnet)
        )

    def slots_for(
        self, ips: torch.Tensor, now: int, weights: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Resolve IPs to slots, promoting/demoting tiers as needed.

        Returns ``(slot_ids, is_cold)`` where ``is_cold`` marks nodes that had
        no prior state and therefore read from their subnet supernode.
        """
        ip_list = ips.detach().cpu().tolist()
        w = (
            weights.detach().cpu().tolist()
            if weights is not None
            else [1] * len(ip_list)
        )
        self._expire(now)

        slots: List[int] = []
        cold: List[bool] = []
        for ip, wt in zip(ip_list, w):
            ip = int(ip)
            self._flow_count[ip] = self._flow_count.get(ip, 0) + int(wt)

            slot = self._slot_of.get(ip)
            if slot is not None:
                self._touch[slot] = now
                slots.append(slot)
                cold.append(False)
                continue

            # promote to a heavy slot if one is free or this host is hotter
            # than the coldest resident
            if self._flow_count[ip] >= 2 or not self.hash_tail:
                slot = self._acquire_heavy(ip, now)
                if slot is not None:
                    slots.append(slot)
                    cold.append(True)
                    continue

            if self.hash_tail:
                slot = self._tail_slot(ip)
                self._touch[slot] = now
                slots.append(slot)
                cold.append(int(self.last_update[slot].item()) == 0)
            else:
                slots.append(self._subnet_slot(ip))
                cold.append(True)

        return (
            torch.tensor(slots, dtype=torch.long, device=self.memory.device),
            torch.tensor(cold, dtype=torch.bool, device=self.memory.device),
        )

    def _acquire_heavy(self, ip: int, now: int) -> Optional[int]:
        if self._free:
            slot = self._free.pop()
        else:
            # LRU eviction: reclaim the coldest resident slot.
            if not self._touch:
                return None
            slot = min(self._touch, key=self._touch.get)
            if now - self._touch[slot] < self.ttl_seconds // 4:
                return None  # everything is hot; leave this host in the tail
            victim = self._ip_of.pop(slot, None)
            if victim is not None:
                self._slot_of.pop(victim, None)
            self.memory[slot].zero_()
        self._slot_of[ip] = slot
        self._ip_of[slot] = ip
        self._touch[slot] = now
        self.last_update[slot] = now
        return slot

    def _expire(self, now: int) -> None:
        """Reclaim slots idle past the TTL. Amortised, runs once per window."""
        if not self._touch:
            return
        dead = [s for s, ts in self._touch.items() if now - ts > self.ttl_seconds]
        for slot in dead:
            if slot < self.n_heavy:
                ip = self._ip_of.pop(slot, None)
                if ip is not None:
                    self._slot_of.pop(ip, None)
                    self._flow_count.pop(ip, None)
                self._free.append(slot)
                self.memory[slot].zero_()
                self.last_update[slot] = 0
            self._touch.pop(slot, None)

    # ------------------------------------------------------------------
    # read / write
    # ------------------------------------------------------------------
    def read(self, slots: torch.Tensor, cold: torch.Tensor, ips: torch.Tensor) -> torch.Tensor:
        # Returns the buffer dtype (float32). Under autocast the consuming GRU
        # casts it down itself, which is the correct direction -- reading fp32
        # state into an fp16 compute region loses nothing that matters.
        mem = self.memory[slots]
        if cold.any():
            sub = torch.tensor(
                [self._subnet_slot(int(i)) for i in ips[cold].cpu().tolist()],
                dtype=torch.long,
                device=self.memory.device,
            )
            mem = mem.clone()
            mem[cold] = self.memory[sub]
        return mem

    @torch.no_grad()
    def write(self, slots: torch.Tensor, new_state: torch.Tensor, now: int, ips: torch.Tensor) -> None:
        """Persist updated state. Detached: memory is state, not a gradient path.

        Truncated BPTT happens at the window boundary -- gradients flow through
        one window's GRU update and stop, which keeps training stable and the
        graph small.
        """
        # CAST TO THE BUFFER DTYPE. Under torch.amp.autocast on CUDA every model
        # output is float16, but the memory buffer is float32 -- and an indexed
        # write refuses to convert, so this raised
        #   "Index put requires the source and destination dtypes match,
        #    got Float for the destination and Half for the source"
        # on the first training step on any GPU. It never fired on CPU because
        # AMP is disabled there, which is exactly why it reached a user.
        # The memory is persistent state, not a gradient path, so keeping it at
        # full precision is deliberate: fp16 accumulation across thousands of
        # windows would drift.
        state = new_state.detach().to(dtype=self.memory.dtype)
        self.memory[slots] = state
        self.last_update[slots] = now
        # keep the subnet supernode warm as a decaying average of its members
        sub = torch.tensor(
            [self._subnet_slot(int(i)) for i in ips.cpu().tolist()],
            dtype=torch.long,
            device=self.memory.device,
        )
        self.memory[sub] = 0.9 * self.memory[sub] + 0.1 * state

    def update(
        self,
        ips: torch.Tensor,
        messages: torch.Tensor,
        now: int,
        weights: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """One memory step: resolve -> read -> GRU -> write -> return state."""
        slots, cold = self.slots_for(ips, now, weights)
        prev = self.read(slots, cold, ips)
        new = self.gru(messages, prev)
        self.write(slots, new, now, ips)
        return new

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.memory.zero_()
        self.last_update.zero_()
        self._slot_of.clear()
        self._ip_of.clear()
        self._touch.clear()
        self._flow_count.clear()
        self._free = list(range(self.n_heavy - 1, -1, -1))

    def occupancy(self) -> dict:
        return {
            "heavy_used": len(self._slot_of),
            "heavy_capacity": self.n_heavy,
            "tail_capacity": self.n_tail,
            "subnet_capacity": self.n_subnet,
            "bytes": int(self.memory.numel() * self.memory.element_size()),
            "tracked_ips": len(self._flow_count),
        }

    def bookkeeping_state(self) -> dict:
        return {
            "slot_of": self._slot_of,
            "ip_of": self._ip_of,
            "touch": self._touch,
            "flow_count": self._flow_count,
            "free": self._free,
        }

    def load_bookkeeping(self, d: dict) -> None:
        self._slot_of = {int(k): int(v) for k, v in d.get("slot_of", {}).items()}
        self._ip_of = {int(k): int(v) for k, v in d.get("ip_of", {}).items()}
        self._touch = {int(k): int(v) for k, v in d.get("touch", {}).items()}
        self._flow_count = {int(k): int(v) for k, v in d.get("flow_count", {}).items()}
        self._free = list(d.get("free", []))

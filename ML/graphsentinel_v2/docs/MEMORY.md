# Memory budget for IP-as-node tracking

> *"If you refactor the graph to treat IPs as nodes and flows as edges, how will
> you handle the memory constraints of tracking every active IP address on a
> high-throughput network interface?"*

The short answer: **you don't track every IP.** You buy a fixed slot budget up
front and make eviction part of the model, so footprint is a number you choose
rather than a function of how much traffic arrives. A design whose memory grows
with the adversary's behaviour is a design the adversary can OOM — spraying
spoofed source addresses is free.

Three separate structures are involved. Only the third is unbounded-looking, and
it is the one that gets capped hardest.

---

## 1. The per-window graph — already bounded, and not by IP count

A window graph holds only the hosts that appeared in that window. Node count is
bounded by distinct endpoints per window, not by the address space:

| window | flows | distinct IPs | nodes×feat (16 f32) | edges×attr (20 f32) |
|---|---|---|---|---|
| 60 s, quiet | 5 000 | ~800 | 51 KB | 800 KB |
| 60 s, busy | 60 000 | ~9 000 | 576 KB | 9.6 MB |
| 60 s, DDoS burst | 400 000 | ~120 000 | 7.7 MB | 64 MB |

The DDoS row is the one that matters, and it is capped two ways:

* `graph.max_edges_per_graph` (default 200 000) subsamples the message-passing
  edge set. **Node features are computed on the full window before subsampling**,
  so the victim still reports its true in-degree of 120 000 — the topology
  signal survives, only the compute does not scale with the flood.
* `graph.node_key = "ip_subnet24"` collapses nodes to /24 supernodes, which
  turns a 120 000-node spoofed flood into at most 65 536 nodes and usually far
  fewer, since spoofed sources cluster.

Peak transient memory is therefore bounded by roughly
`max_edges_per_graph × 20 × 4 B ≈ 16 MB` regardless of traffic.

## 2. Long-horizon host counters — `HostHistory`

Plain Python dicts holding `windows_seen`, `flow_totals`, `last_seen` per IP.
Capacity-bounded: at `capacity` entries the coldest 10 % by `last_seen` are
dropped. At the default 262 144 entries this is ~35 MB of Python dict overhead
(the dominant cost is the dict, not the three ints).

## 3. The learned memory — `NodeMemory`, three tiers

This is the interesting one, because a GRU state vector per host is what makes
low-and-slow detection possible, and it is also what would explode if you let
it. Three tiers, in descending resolution:

**HEAVY — exact, dedicated slots.** A Space-Saving counter promotes a host to a
private slot on its second flow. Eviction is LRU, guarded so a slot is only
reclaimed if its resident has been idle for at least `ttl/4`. This is where the
hosts that matter land, and not by accident: scanners, C2 servers and DDoS
victims are *by definition* high-degree, so the same property that makes them
attackers makes them heavy hitters.

**TAIL — hashed, shared slots.** Everything else maps through a stable blake2b
hash into a smaller pool. Collisions are real and accepted. A host with three
flows an hour has almost no state worth preserving, so two such hosts sharing
one vector costs almost nothing. `hash_ip` is deterministic across processes,
so slots survive a service restart — unlike Python's salted `hash()`.

**SUBNET — cold-start fallback.** A never-before-seen IP reads its /24
supernode's memory instead of a zero vector, kept as a decaying average of its
members. A new host inside an already-compromised subnet therefore does not
start from ignorance.

### The bill

At defaults (`memory_dim=64`, `memory_capacity=262144`, `tail_fraction=0.25`,
subnet tier `= capacity/16`):

| tier | slots | bytes |
|---|---|---|
| heavy | 196 608 | 50.3 MB |
| tail | 65 536 | 16.8 MB |
| subnet | 16 384 | 4.2 MB |
| `last_update` (int64) | 278 528 | 2.2 MB |
| slot bookkeeping (dicts) | ≤ 196 608 | ~25 MB |
| **total** | | **≈ 99 MB, fixed** |

Verified in `tests/test_pipeline.py::test_memory_is_bounded_under_ip_churn`,
which pushes 100 000 distinct random IPs through the store and asserts the
tensor never grows.

### Sizing it for a real link

`memory_capacity` is the only dial:

| link | distinct IPs/day (typical) | suggested capacity | memory tensor |
|---|---|---|---|
| 1 Gb/s campus edge | ~150 k | 65 536 | ~19 MB |
| 10 Gb/s enterprise | ~1.5 M | 262 144 | ~71 MB |
| 40 Gb/s ISP-ish | ~15 M | 1 048 576 | ~285 MB |

Note the capacity does **not** need to equal the daily distinct-IP count. TTL
expiry (default 30 min) means what actually has to fit is the number of hosts
*concurrently active*, which on real traffic is one to two orders of magnitude
smaller — most of that daily 1.5 M is one-shot scanners and CDN edges that
appear once and never return. The tail tier absorbs those at ~4:1 collision
without ever touching a heavy slot.

### What degrades, and where

Being explicit about failure modes, since "it scales" is not a claim you should
accept without one:

* **Tail collisions** blur two quiet hosts into one state vector. Impact is low
  by construction — quiet hosts contribute little memory signal — but a
  *deliberately* quiet attacker sharing a slot with a busy benign host will be
  partially masked. Mitigation: raise `tail_fraction` or capacity; the model
  still sees that window's full per-window features regardless of memory.
* **Heavy-slot thrash** under a churning flood: if every resident is hot, the
  guard refuses to evict and new hosts fall to the tail. This is the correct
  behaviour — better to degrade newcomers to shared state than to evict the
  scanner you were tracking.
* **Spoofed-source floods** are the adversarial case. Random spoofed IPs never
  reach two flows, so they never get promoted out of the tail. Combined with
  `/24` node collapsing, a spoofing attacker cannot force slot allocation.

### Scaling past one box

Slot assignment is a pure function of the IP hash, so the store shards cleanly:
run *N* engines, route flows by `hash_ip(src) % N`, and each shard owns a
disjoint slice of the key space with no coordination. The only cross-shard
concern is a flow whose two endpoints hash to different shards — handled by
replicating the edge to both, which costs bandwidth but no correctness.

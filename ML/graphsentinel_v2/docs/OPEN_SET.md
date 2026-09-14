# Open-set rejection: what was built, what was measured, what failed

Implements the three mitigations from review, plus the OSCR / FPR@95TPR
evaluation suite. **The evaluation suite is the deliverable that worked. The
Mahalanobis scorer is not currently an improvement over the baseline it was
meant to replace**, and this document says so with the numbers.

All results: synthetic CICIDS2017-shaped traffic, 3 seeds x 2 held-out
families, 15–25 epochs. Small test sets (~800 unknown nodes), high variance.
Directional findings only.

---

## 1. What replicates perfectly: the two-regime diagnosis

Across **6 runs out of 6**, a held-out family is resolved by the closed-set
head into exactly one of two regimes:

| regime | family | head sends the unknown to | seeds |
|---|---|---|---|
| **COLLAPSE** | Botnet | **BENIGN** | 799/851, 757/805, 608/828 |
| **SHOEHORN** | SSHBrute | **DoSHulk** | 132/132, 130/130, 133/134 |

`1 - P(BENIGN)` is near-perfect in the shoehorn regime (FPR@95TPR = 0.000 on
all three seeds) and poor in the collapse regime (mean 0.533, range
0.246–0.815). It works *because of* the shoehorning, and fails when the unknown
is absorbed by the null class instead.

You cannot tell which regime you are in without labels. That is the real
indictment of the closed-set proxy, and it is unresolved.

## 2. What did not replicate: Mahalanobis as a fix

Paired against the closed-set baseline on FPR@95TPR, all six runs:

| scorer | mean delta | wins | losses | ties |
|---|---|---|---|---|
| mahalanobis (pca-32) | **+0.113** | 1 | **5** | 0 |
| cascade | +0.084 | 1 | 2 | 3 |
| blended | −0.025 | 1 | 2 | 3 |

Per family, mean FPR@95TPR (lower better) and OSCR (higher better):

| scorer | Botnet FPR@95 | Botnet OSCR | SSHBrute FPR@95 | SSHBrute OSCR |
|---|---|---|---|---|
| closed-set `1-P(BENIGN)` | 0.533 | **0.856** | **0.000** | **0.978** |
| blended | **0.484** | 0.787 | **0.000** | **0.978** |
| cascade | 0.700 | 0.640 | **0.000** | **0.978** |
| mahalanobis | 0.717 | 0.604 | 0.042 | 0.972 |

An earlier **single-seed** run showed Mahalanobis halving the baseline's
false-alarm rate (0.290 vs 0.744). It did not survive replication: that run
drew the baseline at the worst end of its own range. The seed-to-seed standard
deviation of FPR@95TPR (0.32–0.39 pooled) is larger than every difference
between methods.

**Conclusion: post-hoc Mahalanobis on the JK embedding is not a fix.** The
embedding does not carry the unseen family in a form an unsupervised Gaussian
distance reads better than the trained head reads it.

## 3. Where the review's mechanism was right and where it was not

The Information Bottleneck argument predicted that supervised focal training
discards the variance an unknown lives in, so **deeper layers should be worse
for OOD**. Measured per JK block:

| block | Botnet AUROC | SSHBrute AUROC |
|---|---|---|
| h0 (encoder, pre-message-passing) | 0.637 | 0.848 |
| h1 (1 hop) | 0.733 | 0.987 |
| h2 (2 hops) | **0.766** | **0.988** |
| JK (all three concatenated) | **0.783** | **0.997** |

The deepest block is the **strongest**, monotonically, in both families. The
prediction is refuted, and the reason is specific to graphs: h0 is a per-node
MLP over that node's own 16 structural features, and *a many-to-one C2 topology
does not exist at that level*. Message passing **constructs** the relational
signal rather than filtering it. Information-bottleneck reasoning assumes the
relevant information is present at the input and gets discarded; in a GNN the
relevant relational information is built by the layers.

**But the conclusion survives anyway.** The head still reads the embedding
better than a distance does (§2), and the collapse persists across every seed.
By the review's own decision rule — *"if the Botnet-to-Benign collapse
persists, retrain the encoder with a joint reconstruction loss"* — the next
step is joint training, not a better post-hoc probe. The mechanism differs; the
remedy is the same.

## 4. Projection: confirmed, with a floor

| projection | Botnet AUROC / FPR@95 | SSHBrute AUROC / FPR@95 | score latency |
|---|---|---|---|
| none (384-d) | 0.781 / 0.361 | 0.980 / 0.038 | 263 ms |
| random-128 | 0.796 / 0.345 | 0.988 / 0.018 | 83 ms |
| random-64 | 0.783 / 0.290 | 0.998 / 0.020 | 47 ms |
| **pca-32** | **0.793 / 0.261** | 0.995 / 0.025 | 23 ms |
| random-16 | 0.708 / 0.482 | 0.975 / 0.079 | 8 ms |

Projecting helps and the ≤64 guidance is right, but there is a **floor**: 16-d
degrades sharply in both families. 32–64 is the usable band. Latency drops
~10x, which is the more durable benefit.

The distance-concentration diagnostic is noisier than the theory suggests:
relative contrast rose from 5.85 (384-d) to 9.22 (64-d) for Botnet, but *fell*
from 7.67 to 4.53 for SSHBrute. Mahalanobis whitens per component, which
partially counteracts concentration; Ledoit-Wolf shrinkage pulls back toward
isotropic and partially reintroduces it. The effect is real but mitigated, and
the win shows up more reliably in latency and FPR@95TPR than in a contrast
statistic.

Both projections are **label-agnostic by design** — a supervised bottleneck
would compound exactly the information loss described in §3.

## 5. Rank-1 Cholesky: refuted at the recommended dimension

Benchmarked, 14 components per update:

| d | rebuild | rank-1 | winner |
|---|---|---|---|
| 384 | 77 ms | 58 ms | rank-1, 1.3x |
| 128 | 4.1 ms | 15 ms | **rebuild, 3.6x** |
| 64 | 0.8 ms | 7.0 ms | **rebuild, 9x** |
| 32 | 0.4 ms | 3.7 ms | **rebuild, 10x** |

The O(d²) vs O(d³) asymptotic is correct; the constants decide it. numpy's
Cholesky is blocked cache-aware LAPACK, the rank-1 update is an interpreted
loop over d iterations.

**The two mitigations interact: adopting the projection makes rank-1 updating
counterproductive.** At d≤64 a full re-factorisation costs 0.8 ms per window
against a 60 s budget — already free. `MahalanobisOOD` therefore selects by
dimension (`rank1_min_dim=256`), and `cholupdate` is kept, correct and tested,
for the unprojected path.

## 6. Adaptive Conformal: strongly confirmed

Target 1% false-alarm rate, benign baseline drifting up to 3x over 40 windows:

| | mean realised FPR | final 10 windows |
|---|---|---|
| static split conformal | 0.0744 | **0.1100** (11x target) |
| **ACI** (γ=0.02) | 0.0141 | **0.0115** (1.15x target) |

Split conformal's exchangeability assumption fails exactly as described, and
ACI recovers coverage. This is the least ambiguous result in the document.

**The caveat that limits it in production:** ACI needs to observe `err_t`, and
an IDS has no ground-truth labels at inference. It can only be driven from the
alarm rate on a *designated benign reference population* — a known-clean
subnet, an allowlisted host set, or analyst dispositions on a delay. That
controls the false-alarm side, which is the side with an operating budget. It
cannot control the miss rate without labels.

## 7. A bug this work surfaced

The EMA acceptance gate (which stops the detector absorbing the anomalies it is
meant to flag) feeds back only samples already close to a component. That
truncation biases the update sample's spread low, so **the covariance ratchets
shut a little every window**, Mahalanobis distances inflate, and the alarm rate
climbs on its own — indistinguishable from concept drift in production, but
entirely self-inflicted.

Fixed by blending a fixed fraction (`anchor=0.02`) of the originally fitted
covariance back in on every update, plus using the correct Welford/West
cross-moment about both old and new means. Regression test:
`test_covariance_does_not_ratchet_shut_under_gated_updates`.

## 9. Joint reconstruction: the fix that worked, on the encoder not the scorer

Three auxiliary tasks, trained jointly (`models/recon.py`):

    L_total = L_focal + lambda(t) * (1.0 * L_edge + 0.5 * L_link + 0.2 * L_node)

Selection criterion was not "is it a standard SSL objective" but **does solving
it require information the focal objective does not already need**. A task
predictable from the class label anchors nothing.

| task | what it forces into the embedding | class-redundant? |
|---|---|---|
| **masked edge-attribute reconstruction** (primary) | *what kind of traffic this host emits*, at feature resolution — small, regular, fixed-port. The beacon signature itself. | no — BENIGN spans wildly different edge profiles |
| **degree-matched link reconstruction** (secondary) | peer-set identity, i.e. the many-to-one C2 topology | no |
| **structural profile reconstruction** (stabiliser, low weight) | the node's own 16 features | partly — a DDoS victim's in-degree *is* its label |

Two implementation details decide whether this works at all:

* **Mask before encoding.** Edge attributes are fed to GATv2 as edge features,
  so an unmasked edge is copied through attention and reconstruction becomes an
  identity map.
* **Degree-matched negatives.** Uniform negative sampling in a network graph is
  solved perfectly by degree alone — a hub appears in most positive pairs — so
  the link task would collapse to "predict degree".

### Ablation, 3 seeds x 2 families x {recon off, on}

Closed-set cost — **none**:

| family | macro F1 off | on |
|---|---|---|
| Botnet | 0.3963 | 0.4075 |
| SSHBrute | 0.4882 | 0.4865 |

Open-set FPR@95TPR on the collapse family (lower better):

| scorer | Botnet off → on | paired: mean Δ | wins | losses |
|---|---|---|---|---|
| closed-set `1-P(BENIGN)` | 0.553 → **0.249** | −0.152 | 3 | **0** |
| blended | 0.468 → 0.270 | −0.099 | 2 | 1 |
| cascade | 0.658 → 0.384 | −0.137 | 3 | 0 |
| mahalanobis | 0.692 → 0.408 | −0.153 | 5 | 1 |

**Every scorer improved. The biggest beneficiary is the plain closed-set
score**, which at 0.249 now beats every post-hoc scorer — including Mahalanobis
at 0.408. The review's point 2 is confirmed and its remedy works, but the thing
it repaired was the encoder, not the distance metric. That is further evidence
against shipping the post-hoc scorer.

### Mechanism: it is not simply a regime flip

Per seed, Botnet, closed-set FPR@95TPR:

| seed | off | on | head sends unknown to (off → on) |
|---|---|---|---|
| 11 | 0.833 | 0.222 | BENIGN 797/851 → **DDoS 459/851** |
| 23 | 0.545 | 0.501 | BENIGN 753/805 → BENIGN 781/805 |
| 37 | 0.280 | 0.024 | BENIGN 591/828 → BENIGN 763/828 |

Only seed 11 flipped from COLLAPSE to SHOEHORN. Seeds 23 and 37 still put the
unknown in BENIGN by argmax, yet 37 improved by 0.256. So the anchor lowers the
model's *confidence* in BENIGN for unseen traffic even when it does not change
the argmax — which is exactly what a score threshold reads.

### Caveats that bound this result

Direction is consistent (3/3 on the collapse family) but **magnitude is not**:
−0.611, −0.044, −0.256. Seed 23's OSCR went the wrong way (0.855 → 0.725) even
as its FPR@95TPR improved slightly. n=3 on synthetic traffic cannot separate a
real effect of this size from seed noise, and the honest reading is
"promising and free, not established".

`recon_enabled` is ON by default because the direction is consistent and the
closed-set cost is zero, not because three seeds settled it.

### Phase two, not built

**Next-window forecasting from the memory state** is the strongest remaining
task and the only one that would supervise the GRU directly — a beacon is
periodic and therefore highly predictable, which is precisely the property no
current objective rewards. It needs a second forward pass and cross-window
gradient plumbing.

**A prototype / cosine head** is the complementary fix on the other side.
Softmax must assign its mass somewhere, so "none of the above" is not
representable in the architecture at all — the collapse/shoehorn dichotomy is
partly forced by the output layer, not just the encoder. A normalised-cosine
head with learned per-class prototypes makes "far from every prototype"
natively expressible.

## 8. Where this leaves the roadmap

1. **Ship the evaluation suite.** OSCR, FPR@95TPR/FPR@80TPR, and the
   head-assignment breakdown are what turned a plausible story into a measured
   one, twice over — they caught both the single-seed fluke and the covariance
   ratchet.
2. **Do not ship the Mahalanobis scorer as the production OOD score.** It is
   wired into `attack_holdout` reporting so it stays measured, and it is worse
   than the baseline it was meant to replace.
3. **Joint reconstruction training is now the indicated path**, per the review's
   own decision rule — the collapse persisted 6/6.
4. **Before any of that, get more seeds and real data.** Six runs on synthetic
   traffic with sd ≈ 0.35 on the headline metric cannot separate these methods.
   A leave-one-family-out rotation over all five CICIDS2017 families, several
   seeds each, is the minimum for a real recommendation.

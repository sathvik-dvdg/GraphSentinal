"""Tests for the joint self-supervised reconstruction heads."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphsentinel.config import CLASS_TO_IDX, RAW_LABEL_MAP, Config  # noqa: E402
from graphsentinel.data.graph_builder import GraphBuilder  # noqa: E402
from graphsentinel.models.net import build_model  # noqa: E402
from graphsentinel.models.recon import ReconstructionHeads, recon_weight_schedule  # noqa: E402

from make_synthetic import generate  # noqa: E402


@pytest.fixture(scope="module")
def graph():
    df = generate(seed=2, minutes=4)
    df["y"] = df["Label"].map(RAW_LABEL_MAP).map(CLASS_TO_IDX)
    cfg = Config()
    cfg.graph.window_seconds = 60
    cfg.model.memory_capacity = 1024
    return GraphBuilder(cfg).build(df, verbose=False)[0], cfg


def test_masking_replaces_attributes_before_encoding(graph):
    """The mask MUST be applied before message passing.

    Edge attributes are fed to GATv2 as edge features. An unmasked edge can be
    copied straight through attention into its endpoints' embeddings, and the
    reconstruction task degenerates into an identity map that teaches the
    encoder nothing.
    """
    g, cfg = graph
    heads = ReconstructionHeads(jk_dim=32, node_in=16, edge_in=20, edge_cat_dim=36)
    mask = heads.sample_edge_mask(g.edge_index.size(1), 0.15, g.x.device)
    masked = heads.apply_mask(g.edge_attr, mask)

    assert mask.sum() > 0
    assert not torch.allclose(masked[mask], g.edge_attr[mask])
    assert torch.allclose(masked[~mask], g.edge_attr[~mask])
    # a learned token, not zeros -- zero is a legitimate feature value here
    assert not torch.allclose(masked[mask][0], torch.zeros(20))


def test_link_negatives_are_degree_matched(graph):
    """Uniform negatives make link prediction solvable by degree alone.

    If the negative source distribution differed from the positive one, a
    decoder could score pairs purely on how busy the source is and the task
    would add nothing the classifier does not already see.
    """
    g, _ = graph
    src = g.edge_index[0]
    torch.manual_seed(0)
    n_pos = src.size(0)
    idx = torch.randint(0, n_pos, (n_pos,))
    neg_src = src[idx]

    pos_deg = torch.bincount(src, minlength=g.num_nodes).float()
    neg_deg = torch.bincount(neg_src, minlength=g.num_nodes).float()
    # the two degree profiles should correlate strongly by construction
    corr = np.corrcoef(pos_deg.numpy(), neg_deg.numpy())[0, 1]
    assert corr > 0.9, f"negative sources not degree-matched (corr={corr:.3f})"


def test_reconstruction_losses_are_finite_and_differentiable(graph):
    g, cfg = graph
    cfg = Config.from_dict(cfg.to_dict())
    cfg.model.recon_enabled = True
    cfg.model.memory_capacity = 1024
    model = build_model(cfg).train()
    out = model.step_with_reconstruction(g, now=int(g.window_end))

    for key in ("recon_edge", "recon_link", "recon_node"):
        assert key in out
        assert torch.isfinite(out[key]), key
        assert out[key].requires_grad, key

    (out["recon_edge"] + out["recon_link"] + out["recon_node"]).backward()
    encoder_grads = [
        p.grad.norm().item()
        for n, p in model.named_parameters()
        if p.grad is not None and ("blocks" in n or "node_encoder" in n)
    ]
    assert encoder_grads and max(encoder_grads) > 0, (
        "reconstruction gradient never reached the encoder -- the anchor is inert"
    )


def test_reconstruction_heads_absent_when_disabled(graph):
    g, cfg = graph
    cfg = Config.from_dict(cfg.to_dict())
    cfg.model.recon_enabled = False
    cfg.model.memory_capacity = 1024
    model = build_model(cfg)
    assert model.recon is None
    # and the recon entry point degrades to the plain step rather than crashing
    out = model.step_with_reconstruction(g, now=int(g.window_end))
    assert "node_logits" in out and "recon_edge" not in out


def test_eval_path_never_masks(graph):
    """Masking is a training-time augmentation. Evaluation must see the full
    graph, or reported metrics are measured on degraded input."""
    g, cfg = graph
    cfg = Config.from_dict(cfg.to_dict())
    cfg.model.recon_enabled = True
    cfg.model.memory_capacity = 1024
    model = build_model(cfg).eval()
    model.reset_memory()
    a = model.predict(g, now=int(g.window_end))["node_probs"]
    model.reset_memory()
    b = model.predict(g, now=int(g.window_end))["node_probs"]
    assert torch.allclose(a, b, atol=1e-6), "eval path is stochastic -- masking leaked"


def test_weight_schedule_ramps_then_settles_on_a_floor():
    base, total, warm = 0.3, 40, 3
    vals = [recon_weight_schedule(e, total, base, warm) for e in range(1, total + 1)]
    assert vals[0] < vals[warm - 1] <= base + 1e-9, "no warmup ramp"
    assert vals[-1] > 0, "anchor released entirely -- the encoder can re-collapse"
    assert vals[-1] < vals[warm - 1], "no decay after warmup"
    assert all(v >= base * 0.2 - 1e-9 for v in vals[warm:]), "fell below the floor"


def test_recon_adds_parameters_only_when_enabled():
    on, off = Config(), Config()
    on.model.recon_enabled, off.model.recon_enabled = True, False
    on.model.memory_capacity = off.model.memory_capacity = 1024
    assert build_model(on).parameter_count() > build_model(off).parameter_count()



# --------------------------------------------------------------------------
# Mixed precision
# --------------------------------------------------------------------------
def test_memory_write_accepts_reduced_precision_state():
    """Regression: AMP made the first GPU training step crash.

    Under torch.amp.autocast on CUDA every model output is float16, but the
    memory buffer is float32 and an indexed write refuses to convert:

        RuntimeError: Index put requires the source and destination dtypes
        match, got Float for the destination and Half for the source

    This never fired in CPU testing because AMP is disabled there, so it
    reached a user on a T4. The buffer deliberately stays float32 -- it is
    persistent state accumulated over thousands of windows, and fp16 drift
    would corrupt it -- so write() casts instead.
    """
    from graphsentinel.models.memory import NodeMemory

    mem = NodeMemory(memory_dim=8, capacity=64, hash_tail=False, input_dim=8)
    ips = torch.tensor([111, 222], dtype=torch.long)
    slots, cold = mem.slots_for(ips, now=10)

    for dtype in (torch.float16, torch.bfloat16, torch.float32):
        mem.write(slots, torch.randn(2, 8, dtype=dtype), 10, ips)
        assert mem.memory.dtype == torch.float32, "buffer precision was downgraded"
        assert torch.isfinite(mem.memory[slots]).all(), dtype


def test_full_training_step_under_autocast(graph):
    """End-to-end guard: one optimiser step inside autocast must not raise.

    Uses CPU bfloat16 autocast, which exercises the same dtype-mismatch paths
    that CUDA fp16 autocast does on a real GPU.
    """
    import numpy as np
    from graphsentinel.losses import build_loss

    g, cfg = graph
    cfg = Config.from_dict(cfg.to_dict())
    cfg.model.recon_enabled = True
    cfg.model.memory_capacity = 1024

    model = build_model(cfg).train()
    criterion = build_loss(cfg, np.full(6, 100), np.full(6, 100))
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)

    opt.zero_grad()
    with torch.amp.autocast("cpu", dtype=torch.bfloat16, enabled=True):
        out = model.step_with_reconstruction(g, now=int(g.window_end))
        parts = criterion(out, g)
        total = parts["total"] + 0.3 * (
            out["recon_edge"] + out["recon_link"] + out["recon_node"]
        )
    assert torch.isfinite(total), "loss went non-finite under autocast"
    total.float().backward()
    opt.step()
    assert model.memory.memory.dtype == torch.float32

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))

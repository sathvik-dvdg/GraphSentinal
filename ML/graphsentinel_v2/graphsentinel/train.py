"""
Training entry point.

Differences from the v1 loop that matter:

  * No ``input()`` prompt. v1 blocked on ``input("Resume? [y/n]")`` inside the
    training cell, which hangs any unattended or scheduled run forever.
    Resume is a flag.
  * Windows are fed in chronological order with gradient accumulation instead
    of shuffled mini-batches, because host memory only means something if
    window N+1 follows window N.
  * Early stopping and checkpoint selection track macro F1, not weighted F1 --
    so a model that quietly stops detecting botnets is not rewarded.
  * Cosine schedule with warmup; the plateau scheduler in v1 was keyed to a
    metric that could not fall.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import torch

from .config import CLASS_NAMES, Config, taxonomy_fingerprint

# --------------------------------------------------------------------------
#  CHECKPOINT I/O THAT SURVIVES A GOOGLE DRIVE MOUNT
#
#  Two runs were lost to the same failure and it is worth stating precisely,
#  because "just save to Drive" looks obviously correct and is not.
#
#  2026-09-13 (run A): logs/training_log.csv was listed by the state-inspector
#  cell and was gone after training. Fixed by writing the log atomically and
#  mirroring it to local disk.
#
#  2026-09-13 (run B): the SAME thing happened to best.pt, which is far worse
#  -- that is the model, not a log. The evidence is unambiguous:
#      * the state inspector listed  checkpoints/best.pt  at 76.2 MB, and in
#        the very next line train() reported "no checkpoint -- training will
#        start from epoch 1";
#      * 26 epochs ran, 14 of them wrote best.pt;
#      * the final torch.load(best.pt) raised FileNotFoundError.
#  A directory entry on that mount is not evidence that the file can be
#  opened, and a torch.save that returned is not evidence that it landed.
#
#  So three rules, applied to every checkpoint write and read below:
#
#    1. LOCAL DISK IS AUTHORITATIVE.  /content/gs_ckpt is a real filesystem.
#       Drive is a best-effort mirror for surviving a runtime restart -- the
#       one thing local disk cannot do -- and never a dependency.
#    2. EVERY WRITE IS ATOMIC.  torch.save opens 'wb', which truncates the
#       target first; a truncate that completes and a write that does not is
#       exactly how a 76 MB file becomes a missing one. Write a temp file,
#       fsync it, then os.replace -- the target is either the old bytes or
#       the new ones, never nothing.
#    3. EVERY READ IS A TRY-LOAD, NEVER AN .exists().  Existence lied here.
#
#  And a fourth rule that lives in train() itself: the best weights are kept
#  in memory for the duration of the run, so the final evaluation does not
#  read a file at all. No filesystem can lose a run any more.
# --------------------------------------------------------------------------

#: Local scratch that is not a network mount. Used only when it is plausible
#: (Colab); elsewhere the primary path is the only one, which keeps unit tests
#: and laptop runs from scattering files into a directory nobody asked for.
_LOCAL_CKPT_DIR = Path("/content/gs_ckpt")


def _mirror_dir() -> Optional[Path]:
    if not Path("/content").is_dir():
        return None
    try:
        _LOCAL_CKPT_DIR.mkdir(parents=True, exist_ok=True)
        return _LOCAL_CKPT_DIR
    except OSError:
        return None


def _atomic_torch_save(obj, path: Path) -> None:
    """Write via a temp file and os.replace, so the target is never truncated
    without being rewritten. Raises on failure -- the caller decides whether
    this particular destination is allowed to fail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as fh:
        torch.save(obj, fh)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def save_checkpoint(obj, primary: Path, verbose: bool = False,
                    label: str = "", mirror_only: bool = False) -> bool:
    """Local first, Drive second. Returns True if at least one write landed.

    WHY PER-EPOCH SAVES NO LONGER TOUCH DRIVE (mirror_only=True).

    Measured 2026-09-13: five probe files -- 2 MB and 84 MB, direct and
    temp+rename, root and subdirectory -- were all written to Drive and were
    all still intact 150 seconds later. So the loss is not caused by size, by
    os.replace, or by writing into a subdirectory. Every simple hypothesis is
    dead.

    What the probe did NOT reproduce is the thing the real run does: write to
    the SAME path over and over. A 40-epoch run overwrites best.pt and last.pt
    dozens of times. Google Drive is an object store where a "file" is an id,
    not a path, and it permits two objects with the same name in one folder --
    so repeated overwrite is the one pattern that can leave a folder holding
    several `best.pt` objects with the mount resolving to the wrong one, which
    is exactly what "verified on write, missing seconds later" looks like.

    That is a hypothesis, not a diagnosis. But the cost of acting on it is
    nil: the local copy is what the run actually depends on, and cutting ~28
    Drive writes per run down to 2 removes the pattern, removes a lot of
    waiting, and cannot make anything worse. Drive gets the final save only.
    """
    ok = False
    mirror = _mirror_dir()
    targets = [mirror / primary.name] if mirror else []
    if not (mirror_only and mirror):
        targets.append(primary)
    for t in targets:
        try:
            _atomic_torch_save(obj, t)
            ok = True
        except Exception as exc:
            if verbose:
                print(f"  note: could not write {label or primary.name} to "
                      f"{t.parent} ({type(exc).__name__})")
    return ok


def load_checkpoint(primary: Path, map_location="cpu"):
    """Try-load local mirror, then the primary. Returns (blob, path) or
    (None, None). Never trusts .exists(): on the Drive mount it lied."""
    mirror = _mirror_dir()
    for cand in ([mirror / primary.name] if mirror else []) + [primary]:
        try:
            return torch.load(cand, map_location=map_location,
                              weights_only=False), cand
        except Exception:
            continue
    return None, None
from .data.graph_builder import (
    VOLUMETRIC_EDGE_IDX,
    GraphBuilder,
    HostHistory,
    summarise_graphs,
)
from .data.preprocess import build_splits, class_counts
from .evaluate import (
    adjusted_metrics,
    collect_embeddings,
    evaluate_model,
    evasion_ablation,
    fit_logit_adjustment,
    full_report,
    open_set_metrics,
    run_inference,
)
from .ood import MahalanobisOOD, Projection, blended_score, cascade_score
from .losses import build_loss
from .models.net import build_model
from .models.recon import recon_weight_schedule
from .utils.seed import get_device, set_global_seed


# --------------------------------------------------------------------------
# Graph preparation
# --------------------------------------------------------------------------
def prepare_graphs(cfg: Config, force: bool = False, verbose: bool = True) -> Dict[str, List]:
    """Build (or load) window graphs for every split.

    The ``HostHistory`` is shared and advanced in chronological order across
    train -> val -> test. That is not leakage: at deployment the model has
    genuinely seen yesterday's traffic before it sees today's. What would be
    leakage is fitting *parameters* on future data, which never happens here.
    """
    # The taxonomy is part of the cache key. Without it, switching from
    # cicids6 to grouped silently reuses graphs whose edge_y was built under the
    # OLD label map -- the labels would line up by index and be wrong, which is
    # precisely the failure mode this project keeps hitting.
    # drop_edge_features belongs in the key for the same reason. A cached
    # graph set built with all 20 features looks identical on disk to one built
    # without log_total_bytes, and reusing the wrong one would report the
    # baseline as the ablation. This project has already lost two runs to a
    # cache key that was missing a term; it is not losing a third.
    _drop = sorted(getattr(cfg.data, "drop_edge_features", []) or [])
    _dtag = ("_drop-" + "-".join(d[:12] for d in _drop)) if _drop else ""
    cache = (cfg.processed_path /
             f"graphs_{cfg.data.taxonomy}_{cfg.data.split_strategy}"
             f"_w{cfg.graph.window_seconds}{_dtag}.pt")
    if cache.exists() and not force:
        if verbose:
            print(f"RESUME: loading cached graphs from {cache.name}")
        blob = torch.load(cache, weights_only=False)
        return blob["graphs"]

    splits = build_splits(cfg, force=force, verbose=verbose)
    history = HostHistory(capacity=cfg.model.memory_capacity)
    builder = GraphBuilder(cfg, history=history)

    graphs: Dict[str, List] = {}
    for name in ("train", "val", "test"):
        if verbose:
            print(f"\nBuilding {name} graphs ({len(splits[name]):,} flows)...")
        t0 = time.time()
        graphs[name] = builder.build(splits[name], update_history=True, verbose=verbose)
        dt = time.time() - t0
        rate = len(splits[name]) / max(dt, 1e-6)
        if verbose:
            print(f"  {name}: {len(graphs[name])} graphs in {dt:.1f}s ({rate:,.0f} flows/s)")
            print(f"  {json.dumps(summarise_graphs(graphs[name], cfg.model.num_classes))}")

    torch.save({"graphs": graphs, "history": history.state_dict()}, cache)
    if verbose:
        print(f"\nCached graphs -> {cache}")
    return graphs


def node_edge_class_counts(graphs: List, n_classes: int):
    node = np.zeros(n_classes, dtype=np.int64)
    edge = np.zeros(n_classes, dtype=np.int64)
    for g in graphs:
        node += np.bincount(g.y.numpy(), minlength=n_classes)[:n_classes]
        m = g.real_edge_mask.numpy()
        edge += np.bincount(g.edge_y.numpy()[m], minlength=n_classes)[:n_classes]
    return node, edge


# --------------------------------------------------------------------------
# Schedule
# --------------------------------------------------------------------------
def cosine_warmup(optimizer, warmup_epochs: int, total_epochs: int):
    def fn(epoch: int) -> float:
        if epoch < warmup_epochs:
            return (epoch + 1) / max(warmup_epochs, 1)
        progress = (epoch - warmup_epochs) / max(total_epochs - warmup_epochs, 1)
        return 0.5 * (1 + math.cos(math.pi * min(progress, 1.0)))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, fn)


# --------------------------------------------------------------------------
# Train
# --------------------------------------------------------------------------
def train(
    cfg: Config,
    resume: bool = True,
    force_rebuild: bool = False,
    verbose: bool = True,
) -> dict:
    set_global_seed(cfg.train.seed)
    device = get_device()
    cfg.ensure_dirs()
    if verbose:
        print(f"device: {device}")

    graphs = prepare_graphs(cfg, force=force_rebuild, verbose=verbose)
    train_g, val_g, test_g = graphs["train"], graphs["val"], graphs["test"]
    if not train_g:
        raise RuntimeError("No training graphs were built -- check window_seconds.")

    node_counts, edge_counts = node_edge_class_counts(train_g, cfg.model.num_classes)
    if verbose:
        print("\ntrain node class counts:", dict(zip(CLASS_NAMES, node_counts.tolist())))
        print("train edge class counts:", dict(zip(CLASS_NAMES, edge_counts.tolist())))

    model = build_model(cfg).to(device)
    criterion = build_loss(cfg, node_counts, edge_counts).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=cfg.train.learning_rate, weight_decay=cfg.train.weight_decay
    )
    scheduler = cosine_warmup(optimizer, cfg.train.warmup_epochs, cfg.train.epochs)
    use_amp = cfg.train.mixed_precision and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    if verbose:
        print(f"\nmodel: {model.parameter_count():,} trainable parameters")
        if model.memory is not None:
            print(f"memory: {json.dumps(model.memory.occupancy())}")

    ckpt_last = cfg.checkpoint_path / "last.pt"
    ckpt_best = cfg.checkpoint_path / "best.pt"
    start_epoch, best_metric, no_improve = 1, -1.0, 0
    history: List[dict] = []
    # The run's own copy of the best weights. Held here so the final
    # evaluation below never depends on a file existing -- see the module
    # header for the two runs that were lost proving it must not.
    best_state: Optional[dict] = None
    best_blob: Optional[dict] = None

    blob, _from = (load_checkpoint(ckpt_last, map_location=device)
                   if resume else (None, None))
    if blob is not None:
        if verbose and _from != ckpt_last:
            print(f"  resume source: {_from} (local mirror)")

        # --- is this checkpoint even resumable under the CURRENT config? ----
        # Resume exists so an OOM restart continues where it stopped. It must
        # not silently continue a run that was optimising something else.
        #
        # 2026-08-29: a checkpoint trained with edge_loss_weight=0.5 and
        # selection on node_macro_f1 was resumed under edge_loss_weight=2.0 and
        # selection on edge_macro_f1. The stored best_metric (0.2018) was a NODE
        # score, and it was then compared against EDGE scores (~0.3326), so
        # every epoch declared itself "*best" while nothing improved. Eight
        # epochs ran at a cosine LR near zero and the model never moved.
        prev = blob.get("config", {})
        prev_loss = prev.get("loss", {})
        prev_train = prev.get("train", {})
        changed = []
        for label, was, now in [
            ("edge_loss_weight", prev_loss.get("edge_loss_weight"),
             cfg.loss.edge_loss_weight),
            ("focal_gamma", prev_loss.get("focal_gamma"), cfg.loss.focal_gamma),
            ("learning_rate", prev_train.get("learning_rate"),
             cfg.train.learning_rate),
        ]:
            if was is not None and was != now:
                changed.append(f"{label}: was {was}, now {now}")

        # The taxonomy is handled separately, because "absent" is NOT "same".
        # Checkpoints written before taxonomies existed carry no field at all,
        # and the `was is not None` test above would skip them -- which is
        # exactly what happened on 2026-08-29 (run 10): a cicids6 checkpoint
        # was resumed under the grouped taxonomy without complaint, and the
        # head kept its old class meanings under new names.
        prev_tax = prev.get("data", {}).get("taxonomy")
        prev_fp = prev.get("_taxonomy_fingerprint")
        now_fp = taxonomy_fingerprint()
        if prev_tax is None and prev_fp is None:
            if cfg.data.taxonomy != "cicids6":
                changed.append(
                    f"taxonomy: checkpoint records NONE (pre-taxonomy build), "
                    f"now {cfg.data.taxonomy} -- cannot be assumed compatible")
        elif prev_fp is not None and prev_fp != now_fp:
            changed.append(
                f"taxonomy: label map changed (fingerprint {prev_fp} -> {now_fp})")
        elif prev_tax is not None and prev_tax != cfg.data.taxonomy:
            changed.append(f"taxonomy: was {prev_tax}, now {cfg.data.taxonomy}")

        if changed:
            raise RuntimeError(
                "Refusing to resume: the OBJECTIVE changed since this "
                "checkpoint was written.\n    "
                + "\n    ".join(changed)
                + "\n\nHalf-training under one loss and half under another is "
                "not a result you can report. Clear the checkpoints (the RESET "
                "cell, armed) and start from epoch 1, or set resume=False."
            )

        prev_metric = prev_train.get("early_stop_metric")
        metric_changed = (prev_metric is not None
                          and prev_metric != cfg.train.early_stop_metric)

        model.load_state_dict(blob["model"])
        optimizer.load_state_dict(blob["optimizer"])
        scheduler.load_state_dict(blob["scheduler"])
        start_epoch = blob["epoch"] + 1
        best_metric = blob.get("best_metric", -1.0)
        no_improve = blob.get("no_improve", 0)
        history = blob.get("history", [])
        if model.memory is not None and "memory_bookkeeping" in blob:
            model.memory.load_bookkeeping(blob["memory_bookkeeping"])

        if metric_changed:
            # The stored best is a score on a DIFFERENT metric. Comparing the
            # two is meaningless, so the running best restarts from scratch.
            best_metric, no_improve = -1.0, 0
            if verbose:
                print(f"  !! selection metric changed "
                      f"({prev_metric} -> {cfg.train.early_stop_metric}); "
                      f"stored best is on the old metric and has been discarded")

        if verbose:
            print(f"resumed from epoch {blob['epoch']} "
                  f"(best {cfg.train.early_stop_metric}="
                  f"{best_metric:.4f})" if best_metric >= 0 else
                  f"resumed from epoch {blob['epoch']} (best reset)")
            if start_epoch > cfg.train.epochs:
                print(f"  !! start_epoch {start_epoch} > epochs "
                      f"{cfg.train.epochs}: nothing will train. Raise epochs or "
                      f"reset the checkpoints.")

    accum = max(cfg.train.grad_accum_steps, 1)

    # Which validation metric selects the checkpoint.
    #
    # This used to be a hardcoded rewrite of the configured name onto a node
    # metric, which forced selection onto node_macro_f1 whatever the config
    # asked for -- see test_selection_metric_is_not_hardcoded_to_node. On
    # CICIDS2017 that is a lottery: validation holds 2-26 attack NODES per
    # class against 23,657 benign, so the metric swings on a handful of nodes
    # flipping. In the 2026-08-29 run it picked epoch 20 (edge macro F1 0.336)
    # over epoch 9 (0.431) -- it selected a measurably worse model.
    #
    # The edge head has 993-823,170 labels per class and is what feeds the SDN
    # layer, so it is the defensible selection signal.
    _ALIASES = {
        "val_macro_f1": "node_macro_f1",          # legacy name, kept working
        "val_edge_macro_f1": "edge_macro_f1",
    }
    metric_key = _ALIASES.get(
        cfg.train.early_stop_metric,
        cfg.train.early_stop_metric.replace("val_", ""),
    )
    if metric_key not in ("node_macro_f1", "edge_macro_f1") and verbose:
        print(f"  note: selecting on '{metric_key}' (not a standard key)")
    if verbose:
        print(f"checkpoint selection: {metric_key}")

    for epoch in range(start_epoch, cfg.train.epochs + 1):
        model.train()
        model.reset_memory()  # each epoch replays the capture from a cold start
        running, n_batches = 0.0, 0
        optimizer.zero_grad(set_to_none=True)
        t_epoch = time.time()

        lam = (
            recon_weight_schedule(
                epoch, cfg.train.epochs, cfg.model.recon_weight,
                cfg.model.recon_warmup_epochs,
            )
            if cfg.model.recon_enabled
            else 0.0
        )
        recon_running = 0.0
        skipped_windows: List[int] = []
        skipped_edges = np.zeros(cfg.model.num_classes, dtype=np.int64)
        amp_rescued = 0

        for step, data in enumerate(train_g):
            data = data.to(device)
            attempt_amp = use_amp
            for attempt in range(2):
                with torch.amp.autocast("cuda", enabled=attempt_amp):
                    if cfg.model.recon_enabled:
                        out = model.step_with_reconstruction(
                            data, now=int(getattr(data, "window_end", 0))
                        )
                    else:
                        out = model.step_with_memory(
                            data, now=int(getattr(data, "window_end", 0))
                        )
                    parts = criterion(out, data)
                    total = parts["total"]
                    r_val = 0.0
                    if cfg.model.recon_enabled and lam > 0:
                        r = (
                            cfg.model.recon_edge_weight * out["recon_edge"]
                            + cfg.model.recon_link_weight * out["recon_link"]
                            + cfg.model.recon_node_weight * out["recon_node"]
                        )
                        total = total + lam * r
                        r_val = float(r.detach())
                    loss = total / accum

                if torch.isfinite(loss):
                    break
                # fp16 range, not a broken graph: retry the SAME window in fp32
                # before giving up on it. Silently dropping the window costs the
                # optimiser every attack edge inside it -- which is exactly how
                # 100% of DDoS, PortScan and Botnet went untrained for five runs.
                if attempt == 0 and attempt_amp:
                    amp_rescued += 1
                    attempt_amp = False
                    continue
                break

            if not torch.isfinite(loss):
                skipped_windows.append(step)
                m = data.real_edge_mask
                skipped_edges += np.bincount(
                    data.edge_y[m].cpu().numpy(), minlength=cfg.model.num_classes
                )[: cfg.model.num_classes]
                continue

            recon_running += r_val
            scaler.scale(loss).backward()
            running += float(parts["total"].detach())
            n_batches += 1

            if (step + 1) % accum == 0 or step == len(train_g) - 1:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.train.gradient_clip)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)

        scheduler.step()
        train_loss = running / max(n_batches, 1)

        # --- a dropped window is a training-set hole: say so, loudly ---------
        # Reported EVERY epoch, and the per-class share is what matters: losing
        # 3% of BENIGN is noise, losing 100% of DDoS means the class was never
        # trained and any metric naming it is meaningless.
        lost_frac = skipped_edges / np.maximum(edge_counts, 1)
        if skipped_windows:
            worst = int(np.argmax(lost_frac))
            print(
                f"  !! epoch {epoch}: {len(skipped_windows)} window(s) dropped "
                f"({100*len(skipped_windows)/max(len(train_g),1):.1f}%), "
                f"worst class {CLASS_NAMES[worst]} lost {100*lost_frac[worst]:.1f}% "
                f"of its edges"
                + (f" | {amp_rescued} rescued in fp32" if amp_rescued else "")
            )
            starved = [
                f"{CLASS_NAMES[i]} {100*lost_frac[i]:.0f}%"
                for i in range(cfg.model.num_classes)
                if lost_frac[i] > cfg.train.max_class_edge_loss
            ]
            if starved:
                raise RuntimeError(
                    "Training aborted: these classes lost more than "
                    f"{100*cfg.train.max_class_edge_loss:.0f}% of their edges to "
                    f"non-finite windows -- {', '.join(starved)}. Any model trained "
                    "past this point would report scores for classes it never saw. "
                    "Set cfg.train.mixed_precision = False to confirm it is fp16 "
                    "range, then fix the encoder rather than raising this limit."
                )
        elif amp_rescued:
            print(f"  ({amp_rescued} window(s) recomputed in fp32; none lost)")

        model.reset_memory()
        val_metrics = evaluate_model(model, val_g, device)
        current = val_metrics.get(metric_key, val_metrics.get("edge_macro_f1", 0.0))

        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "recon_loss": recon_running / max(n_batches, 1),
            "recon_lambda": lam,
            "lr": optimizer.param_groups[0]["lr"],
            "seconds": time.time() - t_epoch,
            "windows_dropped": len(skipped_windows),
            "amp_rescued": amp_rescued,
            "worst_class_edge_loss": float(lost_frac.max()) if len(lost_frac) else 0.0,
            **val_metrics,
        }
        history.append(row)

        is_best = current > best_metric
        if is_best:
            best_metric, no_improve = current, 0
            best_blob = {
                "model": {k: v.detach().cpu().clone()
                          for k, v in model.state_dict().items()},
                "config": cfg.to_dict(),
                "_taxonomy_fingerprint": taxonomy_fingerprint(),
                "metrics": val_metrics,
                "epoch": epoch,
            }
            best_state = best_blob["model"]
            save_checkpoint(best_blob, ckpt_best,
                            verbose=verbose and epoch == start_epoch,
                            label="best.pt", mirror_only=True)
        else:
            no_improve += 1

        save_checkpoint(
            {
                "epoch": epoch,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
                "best_metric": best_metric,
                "no_improve": no_improve,
                "history": history,
                "config": cfg.to_dict(),
                "_taxonomy_fingerprint": taxonomy_fingerprint(),
                "memory_bookkeeping": (
                    model.memory.bookkeeping_state() if model.memory is not None else {}
                ),
            },
            ckpt_last,
            verbose=verbose and epoch == start_epoch,
            label="last.pt",
            mirror_only=True,
        )

        if verbose:
            per_class = " ".join(
                f"{c[:4]}={val_metrics.get(f'node_f1_{c}', 0):.2f}" for c in CLASS_NAMES
            )
            print(
                f"epoch {epoch:3d} | loss {train_loss:7.4f} | "
                f"macroF1 {val_metrics.get('node_macro_f1', 0):.4f} | "
                f"edgeF1 {val_metrics.get('edge_macro_f1', 0):.4f} | "
                f"PR-AUC {val_metrics.get('node_binary_pr_auc', 0):.4f} | "
                f"{per_class}{'  *best' if is_best else ''}"
            )

        # Write the log ATOMICALLY and to TWO places.
        #
        # 2026-09-13: training_log.csv existed before a run, and was gone after
        # it -- the curves cell then died with FileNotFoundError on a file the
        # state inspector had listed minutes earlier. `to_csv` truncates the
        # target before writing, and on Google Drive's FUSE mount a truncate
        # that does not complete can leave the path unresolvable. Writing to a
        # temp file and renaming means the visible path is never a half-written
        # file, and the local mirror means an unreliable mount can never cost
        # you the training history.
        _rows = pd.DataFrame(history)
        for _dir in (cfg.log_path, Path("/content/gs_logs")):
            try:
                _dir.mkdir(parents=True, exist_ok=True)
                _tmp = _dir / "training_log.csv.tmp"
                _rows.to_csv(_tmp, index=False)
                os.replace(_tmp, _dir / "training_log.csv")
            except Exception as exc:
                if verbose and epoch == start_epoch:
                    print(f"  note: could not write the log to {_dir} "
                          f"({type(exc).__name__}); history is still in the "
                          f"returned report and in last.pt")

        if no_improve >= cfg.train.early_stop_patience:
            if verbose:
                print(f"early stop at epoch {epoch}")
            break

    # ---------------- final evaluation ----------------
    # This line used to be `torch.load(ckpt_best, ...)` and on 2026-09-13 it
    # ended a 26-epoch run with FileNotFoundError on a best.pt that the state
    # inspector had listed at 76.2 MB minutes earlier. The weights were in
    # this process the whole time. Read them from here first; the files are
    # now a fallback, not the source of truth.
    if best_blob is not None:
        blob = best_blob
        if verbose:
            print(f"\nusing the in-memory best checkpoint (epoch {blob['epoch']})")
    else:
        blob, _src = load_checkpoint(ckpt_best, map_location=device)
        if blob is None:
            raise RuntimeError(
                "No best checkpoint, in memory or on disk.\n"
                "  in-memory: no epoch improved on the resumed best_metric, so "
                "nothing was recorded this run;\n"
                f"  on disk  : neither {_LOCAL_CKPT_DIR / ckpt_best.name} nor "
                f"{ckpt_best} could be opened.\n"
                "If you resumed a finished run, that is expected -- train from "
                "epoch 1, or lower cfg.train.early_stop_patience is NOT the fix."
            )
        if verbose:
            print(f"\nloaded best checkpoint from {_src} (epoch {blob['epoch']})")
    model.load_state_dict(blob["model"])
    model.to(device)
    model.reset_memory()

    # ---- per-class decision offsets, fitted on VALIDATION ------------------
    # A class can be well separated and still never win the argmax. Measured on
    # 2026-08-29: DoSHulk edge PR-AUC 0.7813 and SSHBrute 0.8563, both with F1
    # exactly 0.0000 because every one of their edges was labelled DDoS. Good
    # ranking, wrong boundary. This fixes the boundary and nothing else.
    #
    # Fitted on val, applied to test, stored in the checkpoint so the backend
    # applies the identical offsets. Never fitted on test.
    logit_bias = None
    if cfg.train.fit_logit_adjustment:
        model.reset_memory()
        vres = run_inference(model, val_g, device)
        if len(vres["edge_true"]):
            logit_bias = fit_logit_adjustment(
                vres["edge_true"].astype(int), vres["edge_prob"],
                cfg.model.num_classes,
                max_class_drop=cfg.train.max_class_f1_drop,
                min_holdout_per_class=cfg.train.min_holdout_per_class,
                seed=cfg.train.seed,
                verbose=verbose,
            )
            if not np.any(logit_bias):        # all zeros == discarded
                logit_bias = None
            if verbose:
                print("\nedge decision offsets fitted on VALIDATION "
                      "(BENIGN pinned at 0):")
                for c, b in zip(CLASS_NAMES, logit_bias):
                    edge = "   <== on the search boundary" if abs(b) >= 7.9 else ""
                    print(f"    {c:<10s}{b:+7.2f}{edge}")
                if np.any(np.abs(logit_bias) >= 7.9):
                    print("    a boundary offset means the optimum was not "
                          "found inside the search range; treat with suspicion")

    report = full_report(model, test_g, device)
    model.reset_memory()
    report["evasion_ablation"] = evasion_ablation(model, test_g, device, VOLUMETRIC_EDGE_IDX)

    # ---- open-set rejection, only meaningful when a family was held out ----
    if cfg.data.split_strategy == "attack_holdout" and cfg.data.holdout_attacks:
        from .config import CLASS_TO_IDX

        held = CLASS_TO_IDX.get(cfg.data.holdout_attacks[0])
        if held is not None:
            model.reset_memory()
            trL, trE, trY = collect_embeddings(model, train_g, device)
            model.reset_memory()
            teL, teE, teY = collect_embeddings(model, test_g, device)
            if (teY == held).sum() > 0 and len(trE):
                probs = torch.softmax(torch.from_numpy(teL), dim=-1).numpy()
                pred = probs.argmax(1)
                scorer = MahalanobisOOD(
                    projection=Projection(mode="pca", out_dim=32, seed=cfg.train.seed),
                    components_per_class=4,
                ).fit(trE, trY, cfg.model.num_classes)
                maha = scorer.score(teE)
                candidates = {
                    "closed_set_1_minus_p_benign": 1.0 - probs[:, 0],
                    "mahalanobis": maha,
                    "cascade": cascade_score(probs, maha),
                    "blended": blended_score(probs, maha),
                }
                report["open_set"] = {
                    name: open_set_metrics(teY, pred, s, held)
                    for name, s in candidates.items()
                }
                report["open_set"]["_head_assignment_of_unknown"] = {
                    CLASS_NAMES[i]: int((pred[teY == held] == i).sum())
                    for i in range(cfg.model.num_classes)
                }
                scorer.save(cfg.model_path / "ood_scorer.json")
                if verbose:
                    print(f"\n  OPEN-SET  (held out: {cfg.data.holdout_attacks[0]})")
                    print(f"    {'score':<28s} {'OSCR':>8s} {'AUROC':>8s} "
                          f"{'FPR@95':>8s} {'FPR@80':>8s}")
                    for name, mm in report["open_set"].items():
                        if not isinstance(mm, dict) or "oscr_auc" not in mm:
                            continue
                        print(f"    {name:<28s} {mm['oscr_auc']:8.4f} "
                              f"{mm.get('ood_auroc', float('nan')):8.4f} "
                              f"{mm['fpr_at_95tpr']:8.4f} {mm['fpr_at_80tpr']:8.4f}")
                    print(f"    head sends the unknown to: "
                          f"{report['open_set']['_head_assignment_of_unknown']}")

    # ---- report BOTH: raw argmax and adjusted, side by side ---------------
    # Never replace the raw number with the adjusted one. Showing both is what
    # makes it a reported post-processing step rather than a quiet thumb on the
    # scale, and the gap between them is itself the finding: a large gap means
    # the encoder was fine and the boundary was wrong.
    if logit_bias is not None:
        model.reset_memory()
        tres = run_inference(model, test_g, device)
        adj = adjusted_metrics(tres["edge_true"].astype(int), tres["edge_prob"],
                               logit_bias, "edge_", cfg.model.num_classes)
        report["logit_adjustment"] = {
            "bias": logit_bias.tolist(),
            "fitted_on": "validation",
            "classes": list(CLASS_NAMES),
            "adjusted_metrics": adj,
        }
        if verbose:
            raw = report["metrics"]
            print("\n  edge head: raw argmax vs validation-fitted offsets")
            print(f"    {'class':<12s}{'raw F1':>10s}{'adjusted':>11s}{'delta':>9s}")
            for c in CLASS_NAMES:
                a = raw.get(f"edge_f1_{c}", float("nan"))
                b = adj.get(f"edge_f1_{c}", float("nan"))
                print(f"    {c:<12s}{a:>10.4f}{b:>11.4f}{b - a:>+9.4f}")
            a, b = raw.get("edge_macro_f1", 0.0), adj.get("edge_macro_f1", 0.0)
            print(f"    {'MACRO':<12s}{a:>10.4f}{b:>11.4f}{b - a:>+9.4f}")
            print("    (ranking metrics are unchanged by construction -- an")
            print("     additive bias cannot reorder one class's own scores)")

    if logit_bias is not None:
        blob["logit_bias"] = logit_bias.tolist()
        # (persisted by the unconditional write below, so export + backend agree)

    # Final, unconditional write. The export cell loads best.pt by path, so a
    # run whose per-epoch writes all failed must still leave a readable file
    # somewhere -- and the caller must be told where, in plain words, rather
    # than discovering it as a FileNotFoundError two cells later.
    if not save_checkpoint(blob, ckpt_best, verbose=verbose, label="best.pt"):
        print("\n  WARNING: best.pt could not be written to local disk OR to "
              f"{ckpt_best.parent}.\n  The weights are in the returned report "
              "under report['best_state'] -- save them yourself before this "
              "kernel dies:\n      torch.save(report['best_state'], "
              "'/content/best_rescued.pt')")
    report["best_state"] = blob

    report["best_epoch"] = blob["epoch"]
    report["best_val_metric"] = best_metric
    report["history"] = history

    _report_json = {k: v for k, v in report.items() if k != "best_state"}
    for _dir in (cfg.log_path, Path("/content/gs_logs")):
        try:
            _dir.mkdir(parents=True, exist_ok=True)
            _tmp = _dir / "test_report.json.tmp"
            _tmp.write_text(json.dumps(_report_json, indent=2, default=float), encoding="utf-8")
            os.replace(_tmp, _dir / "test_report.json")
        except Exception:
            pass
    if verbose:
        m = report["metrics"]
        print("\n" + "=" * 66)
        print("  TEST RESULTS  (split protocol: " + cfg.data.split_strategy + ")")
        print("=" * 66)
        for k in sorted(m):
            print(f"  {k:<34s} {m[k]:.4f}")
        d = report["evasion_ablation"]["delta"]
        print("\n  volumetric-feature ablation (delta, closer to 0 is more robust):")
        for k, v in d.items():
            print(f"    {k:<32s} {v:+.4f}")
    return report


def main():
    import argparse

    p = argparse.ArgumentParser(description="Train GraphSentinel v2")
    p.add_argument("--base-dir", default=".")
    p.add_argument("--config", default=None)
    p.add_argument("--split", default=None, choices=["episode", "temporal", "day_holdout", "host_holdout", "attack_holdout"])
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--window", type=int, default=None, help="window_seconds")
    p.add_argument("--conv", default=None, choices=["gatv2", "sage_median", "sage_max"])
    p.add_argument("--no-memory", action="store_true")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--rebuild", action="store_true")
    a = p.parse_args()

    cfg = Config.load(a.config) if a.config else Config()
    cfg.base_dir = a.base_dir
    if a.split:
        cfg.data.split_strategy = a.split
    if a.epochs:
        cfg.train.epochs = a.epochs
    if a.window:
        cfg.graph.window_seconds = a.window
        cfg.graph.window_stride_seconds = a.window
    if a.conv:
        cfg.model.conv_type = a.conv
    if a.no_memory:
        cfg.model.use_memory = False

    cfg.ensure_dirs()
    cfg.save(cfg.log_path / "config.json")
    train(cfg, resume=not a.no_resume, force_rebuild=a.rebuild)


if __name__ == "__main__":
    main()

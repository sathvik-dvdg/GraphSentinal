"""The one place that decides whether this process may write under /content.

Colab's /content is a real local disk, and mirroring checkpoints, exports and
logs there is what saved runs from the Drive mount losing files. But the code
that does the mirroring also runs on laptops and in CI, where "/content" is
just a path at the filesystem root -- C:\\content on Windows.

THE BUG THIS REPLACES. train() mirrored its log and test report with
``Path("/content/gs_logs").mkdir(parents=True)`` unconditionally, so any
machine that ran training grew a /content tree outside the repository. The
checkpoint and export mirrors were guarded; the log mirror was not. It was
found by accident, when a stray C:\\content appeared on a Windows machine.

THE RULE.
    GRAPHSENTINEL_LOCAL_MIRROR=0   never mirror
    GRAPHSENTINEL_LOCAL_MIRROR=1   mirror, creating /content if need be
    unset                          mirror only if /content ALREADY exists
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

LOCAL_ROOT = Path("/content")
ENV_VAR = "GRAPHSENTINEL_LOCAL_MIRROR"


def local_scratch(name: str) -> Optional[Path]:
    """``/content/<name>``, created, or None when mirroring is not allowed here."""
    flag = os.environ.get(ENV_VAR, "").strip().lower()
    if flag in ("0", "off", "false", "no"):
        return None
    if flag not in ("1", "on", "true", "yes") and not LOCAL_ROOT.is_dir():
        return None
    try:
        d = LOCAL_ROOT / name
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError:
        return None

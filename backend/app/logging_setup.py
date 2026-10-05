"""The `graphsentinel.*` loggers print INFO by default.

The v2 path reports itself at INFO: the provenance gate admitting a poll, each
scored window, each rule admitted and each withholding with its reason. Nothing
configured a handler for those loggers, so under a plain `uvicorn app.main:...`
only WARNING and above reached the terminal and the loop's own output was
invisible unless the backend was started with `--log-config`. In a demo those
lines are the demonstration.

Idempotent, and it steps aside for anything already configured: a handler placed
on `graphsentinel` by `--log-config` (or by a test) is left alone.
"""
from __future__ import annotations

import logging
import sys

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_graphsentinel_logging() -> logging.Logger:
    logger = logging.getLogger("graphsentinel")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(FORMAT))
        logger.addHandler(handler)
        logger.propagate = False
    if logger.level == logging.NOTSET or logger.level > logging.INFO:
        logger.setLevel(logging.INFO)
    return logger

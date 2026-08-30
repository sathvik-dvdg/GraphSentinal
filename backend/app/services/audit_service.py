# [WSL2]
from __future__ import annotations

import json
import logging
from typing import Any
from sqlalchemy.orm import Session

from app.models.incident import AuditLog

logger = logging.getLogger("graphsentinel.audit")


def log_audit_event(
    db: Session,
    actor_identity: str,
    actor_role: str,
    action: str,
    target_resource: str,
    details: dict[str, Any] | str | None = None,
    status: str = "success",
    request_id: str | None = None,
) -> AuditLog:
    """R-04 (M14-F02) — Persist an immutable administrative audit event.
    Sanitizes details to ensure no secrets, passwords, or tokens are logged."""
    details_str: str | None = None
    if isinstance(details, dict):
        # Sanitize dict: strip sensitive keys
        sanitized = {
            k: v for k, v in details.items()
            if not any(secret_word in k.lower() for secret_word in ("pass", "token", "secret", "key", "auth"))
        }
        details_str = json.dumps(sanitized)
    elif isinstance(details, str):
        details_str = details

    entry = AuditLog(
        actor_identity=actor_identity or "unknown",
        actor_role=actor_role or "unknown",
        action=action,
        target_resource=target_resource,
        details=details_str,
        status=status,
        request_id=request_id,
    )
    db.add(entry)
    try:
        db.commit()
        db.refresh(entry)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist audit log event: %s", exc)
        raise
    return entry

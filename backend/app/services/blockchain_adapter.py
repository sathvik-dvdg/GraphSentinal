# [WSL2]
from __future__ import annotations

import concurrent.futures
import sys
from pathlib import Path
from typing import Any

from app.config import settings


class BlockchainAdapter:
    _instance: "BlockchainAdapter | None" = None

    @classmethod
    def get_instance(cls) -> "BlockchainAdapter":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.client = None
        self._connected = False
        self.error: str | None = None
        self._connect()

    def _connect(self) -> None:
        root = Path(__file__).resolve().parents[3]
        bridge = root / "blockchain" / "web3_bridge"
        if not bridge.exists():
            self.error = f"Bridge path not found: {bridge}"
            return
        sys.path.insert(0, str(bridge))
        try:
            from web3_client import BlockchainClient

            self.client = BlockchainClient()
            self._connected = True
            self.error = None
        except Exception as exc:
            self.error = str(exc)
            self._connected = False

    def health(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "error": self.error,
            "contract_address": settings.contract_address or None,
        }

    def store_incident(
        self,
        source_ip: str,
        attack_type: str,
        severity: int,
        is_blocked: bool,
        incident_id: int,
    ) -> dict[str, Any]:
        if not self._connected or self.client is None:
            return {"tx_hash": None, "status": "mock", "error": self.error or "blockchain offline"}

        def call_client():
            return self.client.log_incident(
                source_ip=source_ip,
                attack_type=attack_type,
                severity=min(max(int(severity), 1), 10),
                is_blocked=bool(is_blocked),
                sqlite_incident_id=int(incident_id),
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(call_client)
            try:
                result = future.result(timeout=settings.blockchain_tx_timeout_seconds)
            except concurrent.futures.TimeoutError:
                return {"tx_hash": None, "status": "pending", "error": "blockchain timeout"}
            except Exception as exc:
                return {"tx_hash": None, "status": "error", "error": str(exc)}

        if isinstance(result, dict):
            return result
        return {"tx_hash": str(result), "status": "confirmed"}


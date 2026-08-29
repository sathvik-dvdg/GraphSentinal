# [WSL2]
from __future__ import annotations

import concurrent.futures
import sys
from pathlib import Path
from typing import Any

from app.config import settings


class BlockchainAdapter:
    _instance: 'BlockchainAdapter | None' = None

    @classmethod
    def get_instance(cls) -> 'BlockchainAdapter':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.client = None
        self._connected = False
        self.error: str | None = None
        self._connect()

    def _connect(self) -> None:
        import os

        bridge_path = Path(settings.blockchain_bridge_path)
        if not bridge_path.is_absolute():
            backend_dir = Path(__file__).resolve().parent.parent.parent
            bridge_path = (backend_dir / bridge_path).resolve()

        if not bridge_path.exists():
            self.error = f'Bridge path not found: {bridge_path}'
            return
        sys.path.insert(0, str(bridge_path))

        if settings.contract_address:
            os.environ.setdefault('CONTRACT_ADDRESS', settings.contract_address)
        if settings.ganache_url:
            os.environ.setdefault('GANACHE_URL', settings.ganache_url)

        try:
            from web3_client import BlockchainClient

            self.client = BlockchainClient()
            self._connected = True
            self.error = None
        except Exception as exc:
            self.error = str(exc)
            self._connected = False

    def chain_id(self) -> int | None:
        if not self._connected or self.client is None:
            return None
        try:
            return self.client.get_chain_id()
        except Exception:
            return None

    def health(self) -> dict[str, Any]:
        return {
            'connected': self._connected,
            'error': self.error,
            'contract_address': settings.contract_address or None,
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
            return {'tx_hash': None, 'status': 'offline', 'error': self.error or 'blockchain offline'}

        def call_client():
            return self.client.log_incident(
                source_ip=source_ip,
                attack_type=attack_type,
                severity=min(max(int(severity), 1), 10),
                is_blocked=bool(is_blocked),
                sqlite_incident_id=int(incident_id),
            )

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(call_client)
        try:
            result = future.result(timeout=settings.blockchain_tx_timeout_seconds)
        except concurrent.futures.TimeoutError:
            future.cancel()
            return {'tx_hash': None, 'status': 'pending', 'error': 'blockchain timeout'}
        except Exception as exc:
            return {'tx_hash': None, 'status': 'error', 'error': str(exc)}
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if isinstance(result, dict):
            # N-03: enrich with chain context so the caller can persist it on
            # the incident row without an extra round-trip to the RPC node.
            if result.get('status') == 'confirmed':
                result.setdefault('chain_id', self.chain_id())
                result.setdefault('contract_address', settings.contract_address)
            return result
        # Legacy path: client returned a raw tx-hash string
        return {
            'tx_hash': str(result),
            'status': 'confirmed',
            'chain_id': self.chain_id(),
            'contract_address': settings.contract_address,
        }

    def reconcile_tx(
        self,
        tx_hash: str | None,
        expected_contract: str | None = None,
        expected_chain_id: int | None = None,
    ) -> str:
        """N-03 — Classify a stored blockchain_tx reference against the live chain.

        Returns one of:
          "confirmed"       — tx exists, receipt status=1, contract matches
          "wrong_contract"  — tx exists but targets a different contract address
          "missing"         — tx hash is genuinely absent from the current chain
          "unavailable"     — blockchain RPC is down / adapter is not connected
          "no_tx"           — incident has no blockchain_tx recorded
        """
        if not tx_hash:
            return 'no_tx'

        if not self._connected or self.client is None:
            return 'unavailable'

        try:
            w3 = self.client.w3
            # Prefix tx_hash if needed
            if not tx_hash.startswith('0x'):
                lookup_hash = '0x' + tx_hash
            else:
                lookup_hash = tx_hash

            # 1. Transaction existence
            try:
                tx = w3.eth.get_transaction(lookup_hash)
            except Exception:
                tx = None

            if tx is None:
                return 'missing'

            # 2. Check contract target
            if expected_contract:
                tx_to = (tx.get('to') or '').lower()
                exp_lower = expected_contract.lower()
                if tx_to != exp_lower:
                    return 'wrong_contract'

            # 3. Receipt / confirmed status
            try:
                receipt = w3.eth.get_transaction_receipt(lookup_hash)
            except Exception:
                receipt = None

            if receipt is None:
                return 'missing'

            if receipt.get('status') == 1:
                return 'confirmed'
            else:
                # Receipt exists but transaction reverted
                return 'missing'

        except Exception:
            # Any unexpected RPC error is treated as unavailable, not missing
            return 'unavailable'


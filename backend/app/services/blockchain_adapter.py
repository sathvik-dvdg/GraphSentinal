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

    def health(self) -> dict[str, Any]:
        return {
            'connected': self._connected,
            'error': self.error,
            'contract_address': settings.contract_address or None,
            'ganache_url': settings.ganache_url,
        }

    def update_config(self, ganache_url: str | None = None, contract_address: str | None = None) -> dict[str, Any]:
        import os
        import re
        from pathlib import Path
        from urllib.parse import urlparse

        # Sanitize against line/header injection
        if ganache_url:
            if "\n" in ganache_url or "\r" in ganache_url:
                raise ValueError("ganache_url cannot contain newlines")
            parsed = urlparse(ganache_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("ganache_url must be a valid HTTP or HTTPS URL")
            settings.ganache_url = ganache_url
            os.environ['GANACHE_URL'] = ganache_url

        if contract_address:
            if "\n" in contract_address or "\r" in contract_address:
                raise ValueError("contract_address cannot contain newlines")
            if not re.match(r"^0x[a-fA-F0-9]{40}$", contract_address):
                raise ValueError("contract_address must be a valid Ethereum address (0x...)")
            settings.contract_address = contract_address
            os.environ['CONTRACT_ADDRESS'] = contract_address

        self._connect()
        return self.health()

    def store_incident(
        self,
        source_ip: str,
        attack_type: str,
        severity: int,
        is_blocked: bool,
        incident_id: int,
    ) -> dict[str, Any]:
        if not self._connected or self.client is None:
            return {'tx_hash': None, 'status': 'mock', 'error': self.error or 'blockchain offline'}

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
            return result
        return {'tx_hash': str(result), 'status': 'confirmed'}

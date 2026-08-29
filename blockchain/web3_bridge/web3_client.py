# blockchain/web3_bridge/web3_client.py
import json
import os
from datetime import datetime, timezone
from web3 import Web3
from web3.exceptions import ContractLogicError

class BlockchainClient:
    """
    GraphSentinel — Forensic Blockchain Client (Dual-Mode Signer & Dynamic Gas)
    """
    def __init__(self):
        ganache_url = os.getenv("GANACHE_URL", "http://127.0.0.1:8545")
        self.w3 = Web3(Web3.HTTPProvider(ganache_url, request_kwargs={"timeout": 10}))

        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to Ganache at {ganache_url}")

        abi_path = os.path.join(os.path.dirname(__file__), "contract_abi.json")
        with open(abi_path) as f:
            self.abi = json.load(f)

        contract_address = os.getenv("CONTRACT_ADDRESS", "").strip()
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=self.abi
        )

        # N-05: Dual-Mode Signer Architecture (N01-SEC-01)
        # Mode A: External/Production private key
        # Mode B: Development unlocked node account
        self.private_key = (
            os.getenv("BLOCKCHAIN_PRIVATE_KEY", "").strip()
            or os.getenv("DEPLOYER_PRIVATE_KEY", "").strip()
            or os.getenv("PRIVATE_KEY", "").strip()
        )
        if self.private_key:
            self.signer_account = self.w3.eth.account.from_key(self.private_key)
            self.account = self.signer_account.address
            self.mode = "private_key"
        elif self.w3.eth.accounts:
            self.account = self.w3.eth.accounts[0]
            self.signer_account = None
            self.mode = "node_account"
        else:
            raise ValueError("No account available: neither BLOCKCHAIN_PRIVATE_KEY nor node accounts configured")

    def _estimate_and_get_gas(self, contract_fn, value: int = 0) -> int:
        """N-05: Dynamic gas estimation with configurable headroom (N02-SEC-02)."""
        account = getattr(self, "account", None)
        try:
            estimated_gas = contract_fn.estimate_gas({"from": account, "value": value})
            if isinstance(estimated_gas, (int, float)):
                gas_val = int(estimated_gas)
            else:
                try:
                    gas_val = int(estimated_gas)
                except (TypeError, ValueError):
                    gas_val = 150000
        except Exception as e:
            # Re-raise clean error so contract reverts are surfaced before broadcasting
            raise RuntimeError(f"Gas estimation failed: {e}") from e

        multiplier = float(os.getenv("BLOCKCHAIN_GAS_MULTIPLIER", "1.2"))
        max_gas = int(os.getenv("BLOCKCHAIN_MAX_GAS", "600000"))
        gas_limit = min(int(gas_val * multiplier), max_gas)
        return max(gas_limit, 21000)

    def _send_contract_tx(self, contract_fn, value: int = 0):
        """Builds, signs, and broadcasts transaction using the active signer mode."""
        gas_limit = self._estimate_and_get_gas(contract_fn, value=value)
        mode = getattr(self, "mode", "node_account")
        private_key = getattr(self, "private_key", "")
        account = getattr(self, "account", None)

        if mode == "private_key" and private_key:
            nonce = self.w3.eth.get_transaction_count(account, "pending")
            gas_price = self.w3.eth.gas_price
            chain_id = self.w3.eth.chain_id
            tx_dict = contract_fn.build_transaction({
                "from": account,
                "nonce": nonce,
                "gas": gas_limit,
                "gasPrice": gas_price,
                "chainId": chain_id,
                "value": value,
            })
            signed = self.w3.eth.account.sign_transaction(tx_dict, private_key=private_key)
            return self.w3.eth.send_raw_transaction(signed.raw_transaction)
        else:
            return contract_fn.transact({"from": account, "gas": gas_limit, "value": value})

    def _sanitize_error(self, err: Exception) -> str:
        """Ensure private keys are never exposed in returned error strings."""
        msg = str(err)
        private_key = getattr(self, "private_key", "")
        if private_key and private_key in msg:
            msg = msg.replace(private_key, "[REDACTED]")
        return msg

    def log_incident(self, source_ip: str, attack_type: str, severity: int, is_blocked: bool, sqlite_incident_id: int) -> dict:
        forensics_uri = f"local://incident/{sqlite_incident_id}"
        severity = max(1, min(int(severity), 10))

        # 1. Transaction Broadcast & Dynamic Gas
        try:
            fn_call = self.contract.functions.logIncident(
                source_ip, attack_type, severity, is_blocked, forensics_uri
            )
            tx_hash = self._send_contract_tx(fn_call)
            tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
            if not tx_hash_hex.startswith("0x"):
                tx_hash_hex = "0x" + tx_hash_hex
        except Exception as e:
            return {"tx_hash": None, "incident_id": None, "status": "error", "error": self._sanitize_error(e)}

        # 2. Receipt Waiting with N05-SEC-01 Timeout Protection
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
        except Exception as timeout_exc:
            # N-05 (N05-SEC-01): Transaction broadcast succeeded; receipt confirmation timed out.
            # Return broadcasted tx_hash with status='pending' to prevent mempool orphaning.
            return {
                "tx_hash": tx_hash_hex,
                "block_number": None,
                "incident_id": None,
                "status": "pending",
                "error": "Transaction broadcast but receipt confirmation timed out",
            }

        if receipt.status != 1:
            return {
                "tx_hash": receipt.transactionHash.hex(),
                "block_number": receipt.blockNumber,
                "incident_id": None,
                "status": "failed",
                "error": "Transaction reverted on-chain",
            }

        # N-04: Authoritative incident ID from the mined transaction's IncidentLogged event
        processed_logs = self.contract.events.IncidentLogged().process_receipt(receipt)
        if not processed_logs:
            return {
                "tx_hash": receipt.transactionHash.hex(),
                "block_number": receipt.blockNumber,
                "incident_id": None,
                "status": "error",
                "error": "IncidentLogged event not found in transaction receipt",
            }

        event_args = processed_logs[0]["args"]
        exact_on_chain_id = event_args.get("id")
        incident_hash = "0x" + event_args["incidentHash"].hex() if "incidentHash" in event_args and hasattr(event_args["incidentHash"], "hex") else None

        return {
            "tx_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "incident_id": exact_on_chain_id,
            "incident_hash": incident_hash,
            "status": "confirmed",
        }

    def release_node(self, ip: str, reason: str = "MANUAL_OVERRIDE") -> dict:
        """N-04 / N-05 — Invoke IncidentLogger.releaseNode(ip, reason) on-chain."""
        try:
            fn_call = self.contract.functions.releaseNode(ip, reason)
            tx_hash = self._send_contract_tx(fn_call)
            tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
            if not tx_hash_hex.startswith("0x"):
                tx_hash_hex = "0x" + tx_hash_hex
        except Exception as e:
            return {"tx_hash": None, "status": "error", "error": self._sanitize_error(e)}

        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
        except Exception:
            return {
                "tx_hash": tx_hash_hex,
                "block_number": None,
                "status": "pending",
                "error": "releaseNode broadcast but receipt confirmation timed out",
            }

        if receipt.status != 1:
            return {
                "tx_hash": receipt.transactionHash.hex(),
                "block_number": receipt.blockNumber,
                "status": "failed",
                "error": "releaseNode transaction reverted on-chain",
            }

        return {
            "tx_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "status": "confirmed",
        }

    def get_all_incidents(self) -> list:
        incidents = []
        try:
            event_filter = self.contract.events.IncidentLogged.create_filter(from_block=0)
            events = event_filter.get_all_entries()
            
            for event in events:
                tx_hash = event.transactionHash.hex()
                block_number = event.blockNumber
                
                try:
                    receipt = self.w3.eth.get_transaction_receipt(event.transactionHash)
                    gas_used = receipt.get("gasUsed", 0)
                except Exception:
                    gas_used = 0

                args = event.args
                incident_id = args.get("id")
                incident_hash = "0x" + args.get("incidentHash").hex()
                timestamp_sec = args.get("timestamp")
                
                try:
                    raw = self.contract.functions.getIncident(incident_id).call()
                    severity = raw[5]
                    is_blocked = raw[6]
                except Exception:
                    severity = 0
                    is_blocked = False

                incidents.append({
                    "id": incident_id,
                    "tx_hash": tx_hash,
                    "block_number": block_number,
                    "incident_hash": incident_hash,
                    "timestamp": datetime.fromtimestamp(timestamp_sec, tz=timezone.utc).isoformat(),
                    "source_ip": args.get("sourceIP"),
                    "attack_type": args.get("attackLabel"),
                    "severity": severity,
                    "is_blocked": is_blocked,
                    "gas_used": gas_used,
                })
        except Exception as e:
            # Fallback if filters are not supported
            count = self.contract.functions.getIncidentCount().call()
            for i in range(1, count + 1):
                try:
                    raw = self.contract.functions.getIncident(i).call()
                    incidents.append({
                        "id": raw[0],
                        "tx_hash": None,
                        "block_number": None,
                        "incident_hash": "0x" + raw[1].hex(),
                        "timestamp": datetime.fromtimestamp(raw[2], tz=timezone.utc).isoformat(),
                        "source_ip": raw[3],
                        "attack_type": raw[4],
                        "severity": raw[5],
                        "is_blocked": raw[6],
                        "gas_used": None,
                    })
                except Exception:
                    pass
        return incidents

    def get_chain_id(self) -> int:
        return self.w3.eth.chain_id

    def verify_incident(self, incident_id: int, source_ip: str, attack_type: str, severity: int, timestamp: int) -> bool:
        return self.contract.functions.verifyIncident(
            incident_id, source_ip, attack_type, severity, timestamp
        ).call()
# blockchain/web3_bridge/web3_client.py
import json
import os
from datetime import datetime, timezone
from web3 import Web3
from web3.exceptions import ContractLogicError

class BlockchainClient:
    """
    GraphSentinel — Local Ganache Forensics Client
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
        self.account = self.w3.eth.accounts[0]

    def log_incident(self, source_ip: str, attack_type: str, severity: int, is_blocked: bool, sqlite_incident_id: int) -> dict:
        forensics_uri = f"local://incident/{sqlite_incident_id}"
        severity = max(1, min(int(severity), 10))

        try:
            tx_hash = self.contract.functions.logIncident(
                source_ip, attack_type, severity, is_blocked, forensics_uri
            ).transact({"from": self.account, "gas": 1000000})

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)

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
        except Exception as e:
            return {"tx_hash": None, "incident_id": None, "status": "error", "error": str(e)}

    def release_node(self, ip: str, reason: str = "MANUAL_OVERRIDE") -> dict:
        """N-04 — Invoke IncidentLogger.releaseNode(ip, reason) on-chain."""
        try:
            tx_hash = self.contract.functions.releaseNode(
                ip, reason
            ).transact({"from": self.account, "gas": 1000000})

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)

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
        except Exception as e:
            return {"tx_hash": None, "status": "error", "error": str(e)}

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
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
            on_chain_id = self.contract.functions.getIncidentCount().call()

            return {
                "tx_hash": receipt.transactionHash.hex(),
                "block_number": receipt.blockNumber,
                "incident_id": on_chain_id,
                "status": "confirmed" if receipt.status == 1 else "failed",
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

    def verify_incident(self, incident_id: int, source_ip: str, attack_type: str, severity: int, timestamp: int) -> bool:
        return self.contract.functions.verifyIncident(
            incident_id, source_ip, attack_type, severity, timestamp
        ).call()
"""Fields the frontend handover (FE-13, FE-25) needs from the API.

Each was either never sent or dropped on the way out: /alerts sent a hash but
not whether it was confirmed, /settings did not report the gas cap (the page
printed a constant), and /forensics dropped the contract's forensics URI.
The routes declare response models, so a field added to the route but not to
the model is silently stripped -- these tests read the HTTP response itself.
"""
from app.api.v1.forensics import _normalize_chain_record
from app.config import settings
from app.database import SessionLocal
from app.models.incident import Incident


def test_alerts_carry_the_ledger_status(client, auth_headers):
    db = SessionLocal()
    try:
        row = Incident(
            source_ip="10.0.0.231", attack_type="DDoS", threat_score=0.95, severity=3,
            is_blocked=True, blockchain_tx="0x" + "ab" * 32, blockchain_status="pending",
        )
        db.add(row)
        db.commit()
        incident_id = row.id
    finally:
        db.close()

    resp = client.get("/api/v1/alerts?limit=200", headers=auth_headers)
    assert resp.status_code == 200
    alert = next(a for a in resp.json()["alerts"] if a["id"] == f"alert-{incident_id}")
    assert alert["blockchain_tx"].startswith("0xab")
    assert alert["blockchain_status"] == "pending"   # a hash is not "on-chain"


def test_settings_report_the_gas_cap(client, auth_headers):
    resp = client.get("/api/v1/settings", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["blockchain_max_gas"] == settings.blockchain_max_gas


def test_chain_records_keep_the_forensics_uri():
    record = _normalize_chain_record({"id": 7, "tx_hash": "0x1", "forensics_uri": "local://incident/42"})
    assert record["forensics_uri"] == "local://incident/42"
    assert record["status"] == "confirmed"

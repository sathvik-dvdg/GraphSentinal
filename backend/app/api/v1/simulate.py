from fastapi import APIRouter
from app.services.threat_analyzer import ThreatAnalyzer
from app.services.graph_state import graph_state

router = APIRouter()
analyzer = ThreatAnalyzer()

@router.post("/simulate")
async def run_simulation():
    # 1. Grab the REAL TIME live network flows
    live_flows = graph_state._flows
    
    if not live_flows:
        # Fallback if the network is completely silent
        mock_ip = "10.0.0.2"
        mock_flow = {
            "src_ip": mock_ip,
            "dst_ip": "10.0.0.1",
            "dst_port": 80,
            "packet_count": 50000,
            "byte_count": 2000000,
            "protocol": "TCP"
        }
    else:
        # 2. Take the first piece of REAL data
        mock_flow = dict(live_flows[0])
        mock_ip = str(mock_flow["src_ip"])
        
        # 3. Artificially spike the traffic on this real connection
        # to simulate a real-time DDoS attack!
        mock_flow["packet_count"] = int(mock_flow.get("packet_count", 0)) + 50000
        mock_flow["byte_count"] = int(mock_flow.get("byte_count", 0)) + 2000000

    prediction = {
        "ip_scores": {mock_ip: 0.95},
        "source_scores": {mock_ip: 0.95}
    }
    
    # 4. Process the spiked REAL data through the ML model and Blockchain
    alerts, healing = analyzer.evaluate(prediction, [mock_flow])
    
    return {"status": "ok", "alerts": alerts, "healing": healing}

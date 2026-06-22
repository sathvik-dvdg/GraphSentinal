
// [Windows] GraphSentinel — Susheep
// Mock data — ALL dummy data lives here ONLY
// Components receive data as props, never import this file directly

// TODO: REPLACE WITH REAL API CALL — GET /api/v1/graph
export const MOCK_GRAPH_DATA = {
  nodes: [
    { id: '10.0.0.1', label: 'h1', status: 'normal', threat_score: 0.03, connections: 12, bytes_total: 64000, attack_type: null, is_blocked: false },
    { id: '10.0.0.2', label: 'h2', status: 'malicious', threat_score: 0.94, connections: 487, bytes_total: 5120000, attack_type: 'DDoS', is_blocked: false },
    { id: '10.0.0.3', label: 'h3', status: 'normal', threat_score: 0.05, connections: 8, bytes_total: 32000, attack_type: null, is_blocked: false },
    { id: '10.0.0.4', label: 'h4', status: 'suspicious', threat_score: 0.62, connections: 145, bytes_total: 890000, attack_type: 'PortScan', is_blocked: false },
    { id: '10.0.0.5', label: 'h5', status: 'blocked', threat_score: 0.88, connections: 0, bytes_total: 1200000, attack_type: 'SSHBrute', is_blocked: true },
    { id: '10.0.0.6', label: 'h6', status: 'normal', threat_score: 0.02, connections: 5, bytes_total: 18000, attack_type: null, is_blocked: false },
    { id: '10.0.0.7', label: 'h7', status: 'suspicious', threat_score: 0.58, connections: 67, bytes_total: 450000, attack_type: 'Botnet', is_blocked: false },
    { id: '10.0.0.8', label: 'h8', status: 'malicious', threat_score: 0.91, connections: 312, bytes_total: 3800000, attack_type: 'SSHBrute', is_blocked: false },
    { id: '10.0.0.9', label: 'h9', status: 'normal', threat_score: 0.04, connections: 3, bytes_total: 9500, attack_type: null, is_blocked: false },
    { id: '10.0.0.10', label: 'h10', status: 'normal', threat_score: 0.06, connections: 15, bytes_total: 78000, attack_type: null, is_blocked: false },
  ],
  links: [
    { source: '10.0.0.2', target: '10.0.0.1', value: 0.94, attack_type: 'DDoS', packet_count: 15000 },
    { source: '10.0.0.2', target: '10.0.0.3', value: 0.87, attack_type: 'DDoS', packet_count: 8200 },
    { source: '10.0.0.4', target: '10.0.0.1', value: 0.62, attack_type: 'PortScan', packet_count: 2400 },
    { source: '10.0.0.4', target: '10.0.0.6', value: 0.55, attack_type: 'PortScan', packet_count: 1800 },
    { source: '10.0.0.8', target: '10.0.0.1', value: 0.91, attack_type: 'SSHBrute', packet_count: 4500 },
    { source: '10.0.0.8', target: '10.0.0.9', value: 0.78, attack_type: 'SSHBrute', packet_count: 2100 },
    { source: '10.0.0.7', target: '10.0.0.10', value: 0.58, attack_type: 'Botnet', packet_count: 900 },
    { source: '10.0.0.1', target: '10.0.0.3', value: 0.03, attack_type: null, packet_count: 120 },
    { source: '10.0.0.6', target: '10.0.0.9', value: 0.02, attack_type: null, packet_count: 45 },
    { source: '10.0.0.3', target: '10.0.0.10', value: 0.04, attack_type: null, packet_count: 88 },
  ],
  metadata: {
    total_nodes: 10,
    malicious_nodes: 2,
    blocked_nodes: 1,
    last_updated: new Date().toISOString(),
  },
}

// TODO: REPLACE WITH REAL API CALL — GET /api/v1/alerts
export const MOCK_ALERTS = [
  {
    id: 'alert-42',
    timestamp: new Date(Date.now() - 120000).toISOString(),
    source_ip: '10.0.0.2',
    attack_type: 'DDoS',
    severity: 'critical',
    threat_score: 0.94,
    description: 'DDoS detected from 10.0.0.2 (score: 0.94)',
    is_blocked: true,
    blockchain_tx: '0x4f3acd2b1a9e7f83c56d8e201b4a7c93d8e5f2a1',
  },
  {
    id: 'alert-41',
    timestamp: new Date(Date.now() - 300000).toISOString(),
    source_ip: '10.0.0.8',
    attack_type: 'SSHBrute',
    severity: 'critical',
    threat_score: 0.91,
    description: 'SSHBrute detected from 10.0.0.8 (score: 0.91)',
    is_blocked: false,
    blockchain_tx: '0x9e1df3b8c72a1e5d9f4b2c8e7a3d1f9b5e2c4a8d',
  },
  {
    id: 'alert-38',
    timestamp: new Date(Date.now() - 600000).toISOString(),
    source_ip: '10.0.0.4',
    attack_type: 'PortScan',
    severity: 'warning',
    threat_score: 0.62,
    description: 'PortScan detected from 10.0.0.4 (score: 0.62)',
    is_blocked: false,
    blockchain_tx: null,
  },
  {
    id: 'alert-35',
    timestamp: new Date(Date.now() - 900000).toISOString(),
    source_ip: '10.0.0.7',
    attack_type: 'Botnet',
    severity: 'warning',
    threat_score: 0.58,
    description: 'Botnet detected from 10.0.0.7 (score: 0.58)',
    is_blocked: false,
    blockchain_tx: null,
  },
]

// TODO: REPLACE WITH REAL API CALL — GET /api/v1/blocked
export const MOCK_BLOCKED = {
  blocked_ips: [
    {
      ip: '10.0.0.5',
      blocked_at: new Date(Date.now() - 180000).toISOString(),
      reason: 'GNN_DETECTED',
      attack_type: 'SSHBrute',
      threat_score: 0.88,
      blockchain_tx: '0x9e1df3b8c72a1e5d9f4b2c8e7a3d1f9b5e2c4a8d',
      enforcement_status: 'simulated',
    },
  ],
  count: 1,
}

// TODO: REPLACE WITH REAL API CALL — GET /api/v1/forensics
export const MOCK_BLOCKCHAIN_TXS = [
  {
    id: 1,
    incident_hash: '0xb8f2a1c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9',
    timestamp: new Date(Date.now() - 120000).toISOString(),
    source_ip: '10.0.0.2',
    attack_type: 'DDoS',
    severity: 9,
    is_blocked: true,
    forensics_uri: 'local://incident/42',
    tx_hash: '0x4f3acd2b1a9e7f83c56d8e201b4a7c93d8e5f2a1',
    block_number: 142,
    gas_used: 68432,
    status: 'confirmed',
  },
  {
    id: 2,
    incident_hash: '0xa1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0',
    timestamp: new Date(Date.now() - 300000).toISOString(),
    source_ip: '10.0.0.8',
    attack_type: 'SSHBrute',
    severity: 9,
    is_blocked: false,
    forensics_uri: 'local://incident/41',
    tx_hash: '0x9e1df3b8c72a1e5d9f4b2c8e7a3d1f9b5e2c4a8d',
    block_number: 141,
    gas_used: 72108,
    status: 'confirmed',
  },
]

// TODO: REPLACE WITH REAL DATA
export const MOCK_STATS = {
  total_nodes: 10,
  active_threats: 4,
  blocked_ips: 1,
  system_health: 82,
  total_packets: 35175,
  total_bytes: 11661500,
  last_updated: new Date().toISOString(),
}

// TODO: REPLACE WITH REAL WEBSOCKET EVENT
export const MOCK_HEALING_EVENTS = [
  {
    id: 'heal-a1b2c3d4e5',
    timestamp: new Date(Date.now() - 180000).toISOString(),
    ip: '10.0.0.5',
    action: 'ISOLATED',
    attack_type: 'SSHBrute',
    trigger_score: 0.88,
    edges_severed: 4,
    duration_ms: 245,
    network_stability_before: 76,
    network_stability_after: 94,
  },
]

// TODO: REPLACE WITH REAL API CALL — GET /api/v1/timeline
export const MOCK_TIMELINE = Array.from({ length: 20 }, (_, i) => {
  const date = new Date(Date.now() - (19 - i) * 5 * 60000)
  const hour = date.getHours().toString().padStart(2, '0')
  const min = date.getMinutes().toString().padStart(2, '0')
  return {
    time: `${hour}:${min}`,
    threats: i > 12 ? Math.floor(Math.random() * 4) : Math.floor(Math.random() * 2),
    blocked: i > 14 ? Math.floor(Math.random() * 2) : 0,
  }
})

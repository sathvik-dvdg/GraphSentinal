// Copy and facts for the landing page. Everything here comes from README.md
// or the previous landing page; nothing is invented.

// Keep FRAME_COUNT in sync with scripts/export-sequence/export.mjs.
export const FRAME_COUNT = 120
export const frameUrl = (set, index) =>
  `/sequence/${set}/${String(index + 1).padStart(4, '0')}.webp`
export const stillUrl = (chapter) => `/sequence/stills/chapter-${chapter}.webp`

// Scroll distance of the pinned stage, in viewport heights.
export const INTRO_VH = 240
export const CHAPTER_VH = 130

export const PREMISE =
  'A graph neural network detects the attack, the network isolates the node, and a local chain keeps the record.'

export const CTA_LABEL = 'Open dashboard'

export const CHAPTERS = [
  {
    verb: 'Observe',
    body: 'Ten Mininet hosts sit behind one software-defined switch. Every five seconds the network emits its flows and the backend rebuilds them into a graph.',
    data: [
      ['topology', '10 hosts, 1 switch'],
      ['flow window', '5 s'],
    ],
    alt: 'Ten host nodes around a central switch, with traffic moving along every link and one node in crimson.',
  },
  {
    verb: 'Detect',
    body: 'A three-layer GraphSAGE network, trained on CICIDS2017, scores every node on each pass. It knows DDoS, PortScan, SSH brute force, Botnet and DoS Hulk.',
    data: [
      ['node', '10.0.0.2'],
      ['threat score', null],
      ['threshold', '0.75'],
    ],
    alt: 'A score bar above every node. The crimson node is ringed and its bar towers over the rest.',
  },
  {
    verb: 'Heal',
    body: 'When a score passes 0.75, the node is cut off with Open vSwitch drop rules. No admin touches anything. The rest of the network keeps talking.',
    data: [
      ['action', 'OVS drop rules'],
      ['admin input', 'none'],
    ],
    alt: 'The crimson node sits inside a cage with its link to the switch severed. The other nine links still carry traffic.',
  },
  {
    verb: 'Record',
    body: 'Each incident is fingerprinted with keccak256 and written to a local Ganache chain. The record still stands if the SQLite log is edited afterwards.',
    data: [
      ['fingerprint', 'keccak256'],
      ['ledger', 'Ganache, chain ID 1337'],
    ],
    alt: 'A row of five linked blocks in front of the network. The newest block is crimson.',
  },
  {
    verb: 'See',
    body: 'A React 3D dashboard shows the graph, the alerts and the ledger as they change, pushed over WebSocket. Sign in to watch the loop run.',
    data: [['transport', 'WebSocket']],
    alt: 'The whole network seen from above: nine connected nodes, one isolated node and the chain of blocks.',
    cta: true,
  },
]

export const ATTACKS = [
  { name: 'DDoS', signal: 'Extreme connection_rate', dataset: 'Friday-Afternoon-DDos.csv', weight: 760 },
  { name: 'PortScan', signal: 'High port_entropy', dataset: 'Friday-Afternoon-PortScan.csv', weight: 600 },
  { name: 'SSH Brute Force', signal: 'High syn_ratio + port 22', dataset: 'Tuesday.csv', weight: 460 },
  { name: 'Botnet', signal: 'byte_asymmetry + C2 ports', dataset: 'Friday-Morning.csv', weight: 340 },
  { name: 'DoS Hulk', signal: 'HTTP flood + port 80', dataset: 'Wednesday.csv', weight: 240 },
]

export const HEADLINE_METRIC = { value: '97.7%', label: 'GNN detection accuracy' }

export const METRICS = [
  { value: '10', label: 'Virtual nodes' },
  { value: '5', label: 'Attack types' },
  { value: '< 5s', label: 'Response time' },
  { value: '0.75', label: 'Isolation threshold', threat: true },
]

export const TEAM = [
  { name: 'Sairaj', role: 'Backend', tech: 'FastAPI, Mininet, SQLite' },
  { name: 'Susheep', role: 'Frontend', tech: 'React, Three.js, Cytoscape' },
  { name: 'Skanda', role: 'Blockchain', tech: 'Solidity, Hardhat, Ganache' },
  { name: 'Sathvik', role: 'ML / GNN', tech: 'PyTorch, PyG, Colab' },
]

export const NAV_LINKS = [
  { href: '#pipeline', label: 'Pipeline' },
  { href: '#threats', label: 'Threats' },
  { href: '#team', label: 'Team' },
]

// System facts for the footer. Wording follows README.md ("Local machine only,
// no cloud, no deployment"; Ganache chain ID 1337; THREAT_THRESHOLD=0.75) and
// the Heal chapter above.
export const SYSTEM_FACTS = [
  { label: 'Deployment', value: 'Runs locally, no cloud' },
  { label: 'Ledger', value: 'Ganache, chain ID 1337' },
  { label: 'Isolation', value: 'A score over 0.75 isolates a node' },
]

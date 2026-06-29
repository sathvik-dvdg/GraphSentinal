// [Windows] GraphSentinel — Susheep
// pyramidConfig.js — static org hierarchy for PyramidHierarchy component

export const ORG_HIERARCHY = {
  id: 'root',
  label: 'Root Node',
  sublabel: 'System Server',
  level: 0,
  ip: '10.0.0.1',
  status: 'normal',
  children: [
    {
      id: 'admin',
      label: 'Admin Node',
      sublabel: 'IT / Security Ops',
      level: 1,
      ip: '10.0.0.2',
      status: 'normal',
      children: [
        {
          id: 'finance',
          label: 'Finance Dept',
          sublabel: '8 nodes',
          level: 2,
          ip: '10.0.1.0/24',
          status: 'normal',
          children: [
            {
              id: 'pc-04',
              label: 'PC-04',
              sublabel: '10.0.0.4',
              level: 3,
              ip: '10.0.0.4',
              status: 'normal',
              children: [],
            },
            {
              id: 'pc-07',
              label: 'PC-07',
              sublabel: '10.0.0.7',
              level: 3,
              ip: '10.0.0.7',
              status: 'infected',
              children: [],
            },
          ],
        },
        {
          id: 'dev',
          label: 'Dev Team',
          sublabel: '22 nodes',
          level: 2,
          ip: '10.0.2.0/24',
          status: 'normal',
          children: [
            {
              id: 'pc-11',
              label: 'PC-11',
              sublabel: '10.0.0.11',
              level: 3,
              ip: '10.0.0.11',
              status: 'normal',
              children: [],
            },
          ],
        },
      ],
    },
    {
      id: 'db',
      label: 'DB Node',
      sublabel: 'Database Cluster',
      level: 1,
      ip: '10.0.0.3',
      status: 'normal',
      children: [],
    },
    {
      id: 'core-services',
      label: 'Core Services',
      sublabel: 'Internal APIs',
      level: 1,
      ip: '10.0.0.5',
      status: 'normal',
      children: [],
    },
  ],
}

// Level badge labels
export const LEVEL_LABELS = {
  0: 'L0 · Root',
  1: 'L1 · Admin',
  2: 'L2 · Dept',
  3: 'L3 · Endpoint',
  4: 'L4 · Device',
}

// Node status styling map
export const STATUS_COLORS = {
  normal:    { border: 'rgba(255,255,255,0.12)', bg: 'transparent',          text: 'rgba(255,255,255,0.75)', badgeBg: 'transparent' },
  infected:  { border: '#E8922A',                bg: 'rgba(232,146,42,0.10)', text: '#EF9F27',               badgeBg: '#E8922A' },
  attacking: { border: '#E03C3C',                bg: 'rgba(224,60,60,0.10)',  text: '#F0997B',               badgeBg: '#E03C3C' },
  isolated:  { border: '#A32D2D',                bg: 'rgba(163,45,45,0.15)', text: '#E03C3C',               badgeBg: '#A32D2D' },
  blocked:   { border: '#A32D2D',                bg: 'rgba(163,45,45,0.10)', text: '#E03C3C',               badgeBg: '#A32D2D' },
}

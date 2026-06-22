/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // ── New Design System Tokens ──────────────────────────────
        // Base surfaces
        'gs-base':    '#0A0A0A',   // App background
        'gs-surface': '#141414',   // Panel surface
        'gs-surface-raised': '#1E1E1E', // Raised panel
        'gs-border':  '#2A2A2A',   // Default 1px border
        'gs-border-subtle': '#1F1F1F', // Hairline separator

        // Text
        'gs-text':     '#EAEAEA',  // Primary text
        'gs-muted':    '#8B8B8B',  // Labels, timestamps
        'gs-faint':    '#4D4D4D',  // Disabled, placeholder

        // Accent
        'gs-accent':      '#EAEAEA',
        'gs-accent-dim':  '#2A2A2A',
        'gs-accent-soft': 'rgba(234,234,234,0.12)',

        // Semantic: Threat
        'gs-threat':      '#FF453A',
        'gs-threat-dim':  '#7A1A1A',
        'gs-threat-soft': 'rgba(255,69,58,0.12)',

        // Semantic: Warning
        'gs-warn':        '#F5A623',
        'gs-warn-dim':    '#7A4A10',
        'gs-warn-soft':   'rgba(245,166,35,0.12)',

        // Semantic: Heal/Safe/Blocked
        'gs-heal':        '#5E5CE6', // Indigo for isolated/blocked
        'gs-heal-dim':    '#3D1E80',
        'gs-heal-soft':   'rgba(94,92,230,0.12)',

        // Semantic: Normal
        'gs-normal':      '#8B8B8B',
        'gs-normal-soft': 'rgba(139,139,139,0.12)',

        // Semantic: Chain
        'gs-chain':       '#8B5CF6',
        'gs-chain-dim':   '#3D1E80',
        'gs-chain-soft':  'rgba(139,92,246,0.12)',

        // ── Legacy tokens — kept for backward compat ──────────────
        background: '#0F1117',
        'on-background': '#E8EDF5',
        surface: '#171B26',
        'surface-dim': '#0F1117',
        'surface-bright': '#1E2436',
        'surface-container-lowest': '#0C0F18',
        'surface-container-low': '#131724',
        'surface-container': '#171B26',
        'surface-container-high': '#1E2436',
        'surface-container-highest': '#252D40',
        'on-surface': '#E8EDF5',
        'on-surface-variant': '#8A95B0',
        'inverse-surface': '#E8EDF5',
        'inverse-on-surface': '#171B26',
        outline: '#3D4560',
        'outline-variant': '#262D3F',
        'surface-tint': '#4F6EF7',
        primary: '#C5D0FF',
        'on-primary': '#0F1840',
        'primary-container': '#4F6EF7',
        'on-primary-container': '#E8EDF5',
        'inverse-primary': '#2D3D8A',
        secondary: '#8A95B0',
        'on-secondary': '#1E2436',
        'secondary-container': '#262D3F',
        'on-secondary-container': '#C5D0FF',
        tertiary: '#C5C8D8',
        'on-tertiary': '#1E2030',
        'tertiary-container': '#2D3050',
        'on-tertiary-container': '#A8ACCC',
        error: '#E03C3C',
        'on-error': '#5A0A0A',
        'error-container': '#7A1A1A',
        'on-error-container': '#FFB4B4',
        'primary-fixed': '#E8922A',
        'primary-fixed-dim': '#7A4A10',

        // Kept legacy gs-* for any untouched components
        'gs-bg':     '#0F1117',
        'gs-card':   '#171B26',
        'gs-mid':    '#131724',
        'gs-alert':  '#E03C3C',
        'gs-info':   '#4F6EF7',
      },
      fontFamily: {
        // New design system
        heading: ['"Plus Jakarta Sans"', 'Inter', 'sans-serif'],
        body:    ['Inter', 'sans-serif'],
        mono:    ['"DM Mono"', '"JetBrains Mono"', 'Courier New', 'monospace'],
        // Legacy aliases
        geist:    ['Inter', 'sans-serif'],
        inter:    ['Inter', 'sans-serif'],
        orbitron: ['"Plus Jakarta Sans"', 'Inter', 'sans-serif'], // Orbitron removed, redirected
      },
      boxShadow: {
        // Functional only — no decorative glow
        'threat': '0 0 16px rgba(224,60,60,0.25)',
        'heal':   '0 0 16px rgba(46,204,138,0.25)',
        'accent': '0 0 16px rgba(79,110,247,0.25)',
        'panel':  '0 4px 24px rgba(0,0,0,0.4)',
        'modal':  '0 24px 64px rgba(0,0,0,0.6)',
        // Legacy
        'glow-cyan':    '0 0 16px rgba(79,110,247,0.25)',
        'glow-emerald': '0 0 16px rgba(46,204,138,0.25)',
        'glow-rose':    '0 0 16px rgba(224,60,60,0.25)',
        'glow-amber':   '0 0 16px rgba(232,146,42,0.25)',
        'glow-primary': '0 0 16px rgba(79,110,247,0.25)',
        'deep':         '0 25px 50px rgba(0,0,0,0.7)',
      },
      backgroundImage: {
        // Minimal mesh — only used in dashboard graph canvas area
        'gs-mesh': 'linear-gradient(rgba(79,110,247,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(79,110,247,0.025) 1px, transparent 1px)',
        // Legacy
        'void-radial': 'radial-gradient(ellipse at 50% 0%, rgba(79,110,247,0.04) 0%, transparent 70%)',
        'cyber-mesh':  'linear-gradient(rgba(79,110,247,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(79,110,247,0.03) 1px, transparent 1px)',
        'digital-fortress-grid': 'linear-gradient(rgba(79,110,247,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(79,110,247,0.02) 1px, transparent 1px)',
      },
      backgroundSize: {
        'mesh-48': '48px 48px',
        'grid-20': '20px 20px',
      },
      animation: {
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'spin-slow':  'spin 3s linear infinite',
      },
      borderRadius: {
        'soft': '0.375rem',
        'panel': '0.75rem',
      },
    },
  },
  plugins: [],
}

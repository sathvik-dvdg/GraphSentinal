/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Digital Fortress Tokens
        background: '#051424',
        'on-background': '#d4e4fa',
        surface: '#051424',
        'surface-dim': '#051424',
        'surface-bright': '#2c3a4c',
        'surface-container-lowest': '#010f1f',
        'surface-container-low': '#0d1c2d',
        'surface-container': '#122131',
        'surface-container-high': '#1c2b3c',
        'surface-container-highest': '#273647',
        'on-surface': '#d4e4fa',
        'on-surface-variant': '#b9cacb',
        'inverse-surface': '#d4e4fa',
        'inverse-on-surface': '#233143',
        outline: '#849495',
        'outline-variant': '#3a494b',
        'surface-tint': '#00dbe7',
        primary: '#e1fdff',
        'on-primary': '#00363a',
        'primary-container': '#00f2ff',
        'on-primary-container': '#006a71',
        'inverse-primary': '#00696f',
        secondary: '#bcc7de',
        'on-secondary': '#263143',
        'secondary-container': '#3e495d',
        'on-secondary-container': '#aeb9d0',
        tertiary: '#f7f6ff',
        'on-tertiary': '#2c303d',
        'tertiary-container': '#d7daec',
        'on-tertiary-container': '#5b5f6e',
        error: '#ffb4ab',
        'on-error': '#690005',
        'error-container': '#93000a',
        'on-error-container': '#ffdad6',

        // Functional overrides mentioned in design
        'magenta-warn': '#FF00E5',
        'lime-safe': '#ADFF00',

        // Legacy tokens — kept for backward compat with all existing components
        'gs-bg':     '#020817',
        'gs-card':   '#0f172a',
        'gs-mid':    '#080f1e',
        'gs-accent': '#34d399',
        'gs-alert':  '#f43f5e',
        'gs-warn':   '#fbbf24',
        'gs-info':   '#06b6d4',
        'gs-chain':  '#a855f7',
        'gs-border': '#1e293b',
      },
      fontFamily: {
        geist: ['Geist', 'sans-serif'],
        inter: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'Courier New', 'monospace'],
        orbitron: ['Orbitron', 'JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'glow-cyan':    '0 0 20px rgba(6,182,212,0.35)',
        'glow-emerald': '0 0 20px rgba(52,211,153,0.35)',
        'glow-rose':    '0 0 20px rgba(244,63,94,0.35)',
        'glow-amber':   '0 0 20px rgba(251,191,36,0.35)',
        'glow-primary': '0 0 20px rgba(0,242,255,0.35)', // New neon glow
        'panel':        '0 0 30px rgba(0,0,0,0.5)',
        'deep':         '0 25px 50px rgba(0,0,0,0.8)',
      },
      backgroundImage: {
        'void-radial': 'radial-gradient(ellipse at 50% 0%, rgba(6,182,212,0.06) 0%, transparent 70%)',
        'cyber-mesh':  'linear-gradient(rgba(6,182,212,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,0.04) 1px, transparent 1px)',
        'digital-fortress-grid': 'linear-gradient(rgba(0,242,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(0,242,255,0.02) 1px, transparent 1px)',
      },
      backgroundSize: {
        'mesh-48': '48px 48px',
        'grid-20': '20px 20px',
      },
      animation: {
        'neon-pulse': 'neon-border-pulse 2.4s ease-in-out infinite',
        'spin-slow':  'spin-slow 2s linear infinite',
      },
      borderRadius: {
        'soft': '0.25rem',
      }
    },
  },
  plugins: [],
}

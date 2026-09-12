/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // ── Clean White Design System Tokens ──────────────────────
        // Base surfaces
        'gs-base':    '#F4F6F8',   // App background
        'gs-surface': '#FFFFFF',   // Panel surface
        'gs-surface-raised': '#F0F2F5', // Raised panel
        'gs-border':  '#E2E5EA',   // Default 1px border
        'gs-border-subtle': '#ECEEF1', // Hairline separator

        // Text
        'gs-text':     '#1B1F27',  // Primary text
        'gs-muted':    '#5A616E',  // Labels, timestamps
        'gs-faint':    '#9AA1AD',  // Disabled, placeholder

        // Accent (now a dark ink so it reads on white)
        'gs-accent':      '#1B1F27',
        'gs-accent-dim':  '#E2E5EA',
        'gs-accent-soft': 'rgba(27,31,39,0.06)',

        // Semantic: Threat
        'gs-threat':      '#D92D2D',
        'gs-threat-dim':  '#F6C6C6',
        'gs-threat-soft': 'rgba(217,45,45,0.10)',

        // Semantic: Warning
        'gs-warn':        '#B7791F',
        'gs-warn-dim':    '#EFD9B4',
        'gs-warn-soft':   'rgba(183,121,31,0.12)',

        // Semantic: Heal/Safe/Blocked
        'gs-heal':        '#5E5CE6', // Indigo for isolated/blocked
        'gs-heal-dim':    '#C7C6F5',
        'gs-heal-soft':   'rgba(94,92,230,0.10)',

        // Semantic: Normal
        'gs-normal':      '#5A616E',
        'gs-normal-soft': 'rgba(90,97,110,0.10)',

        // Semantic: Chain
        'gs-chain':       '#7C3AED',
        'gs-chain-dim':   '#D9C7F5',
        'gs-chain-soft':  'rgba(124,58,237,0.10)',

        // ── Legacy tokens — remapped to the light palette ─────────
        background: '#F4F6F8',
        'on-background': '#1B1F27',
        surface: '#FFFFFF',
        'surface-dim': '#F4F6F8',
        'surface-bright': '#FFFFFF',
        'surface-container-lowest': '#F4F6F8',
        'surface-container-low': '#F7F8FA',
        'surface-container': '#FFFFFF',
        'surface-container-high': '#F0F2F5',
        'surface-container-highest': '#E7EAF0',
        'on-surface': '#1B1F27',
        'on-surface-variant': '#5A616E',
        'inverse-surface': '#1B1F27',
        'inverse-on-surface': '#FFFFFF',
        outline: '#9AA1AD',
        'outline-variant': '#E2E5EA',
        'surface-tint': '#3B56D9',
        primary: '#3B56D9',
        'on-primary': '#FFFFFF',
        'primary-container': '#3B56D9',
        'on-primary-container': '#FFFFFF',
        'inverse-primary': '#C5D0FF',
        secondary: '#5A616E',
        'on-secondary': '#FFFFFF',
        'secondary-container': '#EEF1F5',
        'on-secondary-container': '#1B1F27',
        tertiary: '#5A616E',
        'on-tertiary': '#FFFFFF',
        'tertiary-container': '#EEF1F5',
        'on-tertiary-container': '#1B1F27',
        error: '#D92D2D',
        'on-error': '#FFFFFF',
        'error-container': '#F6C6C6',
        'on-error-container': '#5A0A0A',
        'primary-fixed': '#B7791F',
        'primary-fixed-dim': '#EFD9B4',

        // Kept legacy gs-* for any untouched components
        'gs-bg':     '#F4F6F8',
        'gs-card':   '#FFFFFF',
        'gs-mid':    '#F0F2F5',
        'gs-alert':  '#D92D2D',
        'gs-info':   '#3B56D9',
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
        // Soft, functional shadows for the white theme
        'threat': '0 4px 16px rgba(217,45,45,0.12)',
        'heal':   '0 4px 16px rgba(94,92,230,0.12)',
        'accent': '0 4px 16px rgba(59,86,217,0.12)',
        'panel':  '0 1px 2px rgba(17,20,26,0.04), 0 8px 24px rgba(17,20,26,0.06)',
        'modal':  '0 24px 64px rgba(17,20,26,0.14)',
        // Legacy aliases
        'glow-cyan':    '0 4px 16px rgba(59,86,217,0.12)',
        'glow-emerald': '0 4px 16px rgba(18,166,114,0.12)',
        'glow-rose':    '0 4px 16px rgba(217,45,45,0.12)',
        'glow-amber':   '0 4px 16px rgba(183,121,31,0.12)',
        'glow-primary': '0 4px 16px rgba(59,86,217,0.12)',
        'deep':         '0 25px 50px rgba(17,20,26,0.16)',
      },
      backgroundImage: {
        // Minimal mesh — only used in dashboard graph canvas area
        'gs-mesh': 'linear-gradient(rgba(59,86,217,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(59,86,217,0.05) 1px, transparent 1px)',
        // Legacy
        'void-radial': 'radial-gradient(ellipse at 50% 0%, rgba(59,86,217,0.05) 0%, transparent 70%)',
        'cyber-mesh':  'linear-gradient(rgba(59,86,217,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(59,86,217,0.06) 1px, transparent 1px)',
        'digital-fortress-grid': 'linear-gradient(rgba(59,86,217,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(59,86,217,0.05) 1px, transparent 1px)',
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

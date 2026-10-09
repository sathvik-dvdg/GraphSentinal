// The palette lives in src/constants/colors.js. Components that cannot use a
// class (canvas, three.js, Recharts, inline styles with an alpha suffix) import
// it directly; the `gs-*` utilities added from it below are the same values.
import { GS } from './src/constants/colors.js'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // ── Landing-page design tokens (bone, ink, crimson) ───────────
        // Base surfaces
        'gs-base':    '#ebe7df',   // App background
        'gs-surface': '#f6f3ed',   // Panel surface
        'gs-surface-raised': '#e3ded4', // Raised panel
        'gs-border':  '#d3cec3',   // Default 1px border
        'gs-border-subtle': '#dcd7cc', // Hairline separator

        // Text
        'gs-text':     '#2b2a28',  // Primary text
        'gs-muted':    '#55524d',  // Labels, timestamps
        'gs-faint':    '#7d786f',  // Disabled, placeholder

        // Accent (now a dark ink so it reads on white)
        'gs-accent':      '#2b2a28',
        'gs-accent-dim':  '#d3cec3',
        'gs-accent-soft': 'rgba(27,31,39,0.06)',

        // Semantic: Threat
        'gs-threat':      '#b4132e',
        'gs-threat-dim':  '#e3b4bb',
        'gs-threat-soft': 'rgba(180,19,46,0.10)',

        // Semantic: Warning
        'gs-warn':        '#855808',
        'gs-warn-dim':    '#dfc9a0',
        'gs-warn-soft':   'rgba(133,88,8,0.12)',

        // Semantic: Heal/Safe/Blocked
        'gs-heal':        '#4b5578', // Indigo for isolated/blocked
        'gs-heal-dim':    '#c3c8dc',
        'gs-heal-soft':   'rgba(75,85,120,0.10)',

        // Semantic: Normal
        'gs-normal':      '#55524d',
        'gs-normal-soft': 'rgba(90,97,110,0.10)',

        // Semantic: Chain
        'gs-chain':       '#6b4a82',
        'gs-chain-dim':   '#d4c5de',
        'gs-chain-soft':  'rgba(124,58,237,0.10)',

        // ── In-use colours that had no token (2026-10-05) ─────────
        // These are what the pages actually draw with. `gs-danger` sits
        // beside `gs-threat` and `gs-subtle` beside `gs-muted`: two palettes,
        // not yet merged (see src/constants/colors.js).
        'gs-danger':         GS.danger,
        'gs-success':        GS.success,
        'gs-primary':        GS.primary,
        'gs-subtle':         GS.textSubtle,
        'gs-surface-header': GS.surfaceHeader,
        'gs-border-strong':  GS.borderStrong,

        // ── Legacy tokens — remapped to the landing palette ───────
        background: '#ebe7df',
        'on-background': '#2b2a28',
        surface: '#f6f3ed',
        'surface-dim': '#ebe7df',
        'surface-bright': '#f6f3ed',
        'surface-container-lowest': '#ebe7df',
        'surface-container-low': '#f1eee7',
        'surface-container': '#f6f3ed',
        'surface-container-high': '#e3ded4',
        'surface-container-highest': '#d9d4c9',
        'on-surface': '#2b2a28',
        'on-surface-variant': '#55524d',
        'inverse-surface': '#2b2a28',
        'inverse-on-surface': '#f6f3ed',
        outline: '#7d786f',
        'outline-variant': '#d3cec3',
        'surface-tint': '#2b2a28',
        primary: '#2b2a28',
        'on-primary': '#f6f3ed',
        'primary-container': '#2b2a28',
        'on-primary-container': '#f6f3ed',
        'inverse-primary': '#d3cec3',
        secondary: '#55524d',
        'on-secondary': '#f6f3ed',
        'secondary-container': '#e3ded4',
        'on-secondary-container': '#2b2a28',
        tertiary: '#55524d',
        'on-tertiary': '#f6f3ed',
        'tertiary-container': '#e3ded4',
        'on-tertiary-container': '#2b2a28',
        error: '#b4132e',
        'on-error': '#f6f3ed',
        'error-container': '#e3b4bb',
        'on-error-container': '#4a0a14',
        'primary-fixed': '#855808',
        'primary-fixed-dim': '#dfc9a0',

        // Kept legacy gs-* for any untouched components
        'gs-bg':     '#ebe7df',
        'gs-card':   '#f6f3ed',
        'gs-mid':    '#e3ded4',
        'gs-alert':  '#b4132e',
        'gs-info':   '#2b2a28',
      },
      fontFamily: {
        // New design system
        // The landing page's three faces (loaded in styles/globals.css)
        heading: ['Newsreader', '"Iowan Old Style"', 'Georgia', 'serif'],
        body:    ['"Hanken Grotesk"', 'system-ui', '"Segoe UI"', 'sans-serif'],
        mono:    ['"JetBrains Mono"', 'ui-monospace', '"Cascadia Mono"', 'Consolas', 'monospace'],
        // Legacy aliases
        geist:    ['"Hanken Grotesk"', 'system-ui', 'sans-serif'],
        inter:    ['"Hanken Grotesk"', 'system-ui', 'sans-serif'],
        orbitron: ['Newsreader', 'Georgia', 'serif'], // Orbitron removed, redirected
      },
      boxShadow: {
        // Soft, functional shadows for the bone ground
        'threat': '0 4px 16px rgba(180,19,46,0.12)',
        'heal':   '0 4px 16px rgba(75,85,120,0.12)',
        'accent': '0 4px 16px rgba(43,42,40,0.12)',
        'panel':  '0 1px 2px rgba(43,42,40,0.04), 0 8px 24px rgba(43,42,40,0.06)',
        'modal':  '0 24px 64px rgba(43,42,40,0.14)',
        // Legacy aliases
        'glow-cyan':    '0 4px 16px rgba(43,42,40,0.12)',
        'glow-emerald': '0 4px 16px rgba(52,99,72,0.12)',
        'glow-rose':    '0 4px 16px rgba(180,19,46,0.12)',
        'glow-amber':   '0 4px 16px rgba(133,88,8,0.12)',
        'glow-primary': '0 4px 16px rgba(43,42,40,0.12)',
        'deep':         '0 25px 50px rgba(43,42,40,0.16)',
      },
      backgroundImage: {
        // Minimal mesh — only used in dashboard graph canvas area
        'gs-mesh': 'linear-gradient(rgba(43,42,40,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(43,42,40,0.05) 1px, transparent 1px)',
        // Legacy
        'void-radial': 'radial-gradient(ellipse at 50% 0%, rgba(43,42,40,0.05) 0%, transparent 70%)',
        'cyber-mesh':  'linear-gradient(rgba(43,42,40,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(43,42,40,0.06) 1px, transparent 1px)',
        'digital-fortress-grid': 'linear-gradient(rgba(43,42,40,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(43,42,40,0.05) 1px, transparent 1px)',
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

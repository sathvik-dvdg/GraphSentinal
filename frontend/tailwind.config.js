/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        'gs-bg': '#0a0e1a',
        'gs-card': '#111827',
        'gs-mid': '#0d1424',
        'gs-accent': '#00ff88',
        'gs-alert': '#ff4444',
        'gs-warn': '#ffaa00',
        'gs-info': '#0066ff',
        'gs-chain': '#9945ff',
        'gs-border': '#1f2937',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Courier New', 'monospace'],
      },
    },
  },
  plugins: [],
}

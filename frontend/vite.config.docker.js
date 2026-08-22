// frontend/vite.config.docker.js
// ── Docker-only Vite config ───────────────────────────────────────────────────
// This file is used ONLY by the Docker Compose setup (via --config flag).
// The original vite.config.js is UNTOUCHED and remains the local dev entry point.
//
// The only difference from vite.config.js: proxy targets use the Docker
// Compose service name "backend" (internal DNS) instead of "localhost".
// ─────────────────────────────────────────────────────────────────────────────
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',   // required for Docker — listen on all interfaces
    watch: {
      usePolling: true, // required for Windows/WSL file event propagation in Docker
    },
    proxy: {
      '/api': {
        target: 'http://backend:8000',   // "backend" = Compose service name
        changeOrigin: true,
        secure: false,
      },
      '/health': {
        target: 'http://backend:8000',
        changeOrigin: true,
        secure: false,
      },
      '/socket.io': {
        target: 'http://backend:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})

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

// Node's HTTP server defaults keepAliveTimeout to 5s. The browser pools
// keep-alive connections for much longer than that and will try to reuse
// one that Node already silently closed once it's been idle past 5s —
// every REST poll (useGraphData.js, 10s interval) racing that mismatch
// shows up as a client-side `net::ERR_ABORTED` on whichever pooled
// connections happened to be stale, even though the backend itself never
// saw the request and responded fine to everything else. Raising both
// timeouts past any realistic idle gap between polls fixes the race at
// its source instead of just tolerating it with a longer axios timeout.
function keepAliveFix() {
  return {
    name: 'keep-alive-timeout-fix',
    configureServer(server) {
      server.httpServer?.once('listening', () => {
        server.httpServer.keepAliveTimeout = 65000
        server.httpServer.headersTimeout = 66000
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), keepAliveFix()],
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

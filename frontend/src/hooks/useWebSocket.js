// [Windows] GraphSentinel — Susheep
// WebSocket hook — socket.io-client@4 ↔ python-socketio@5
// § 2 known soft spot: reconnect does NOT re-emit graph_update
//   → on reconnect, trigger onReconnect() so caller can REST-fetch fresh state
import { useEffect, useRef, useState } from 'react'
import { io } from 'socket.io-client'

// Same-origin by default — rides the Vite (or Docker) proxy exactly like REST
// calls already do (see vite.config.js / vite.config.docker.js). Only set
// VITE_BACKEND_URL to point elsewhere for an unusual cross-origin deployment
// (Error.md #20 — REST and WS previously could silently target different
// backends).
const WS_URL = import.meta.env.VITE_BACKEND_URL || undefined

// Prop names are stable — do not rename (§5 integration constraint)
export function useWebSocket({
  onGraphUpdate,
  onAlert,
  onHealingTriggered,
  onConnect,
  onDisconnect,
  onReconnect, // Optional: called after reconnect so caller can re-fetch via REST
}) {
  const socketRef = useRef(null)
  const [isConnected, setIsConnected] = useState(false)

  // Error.md #21: the socket effect intentionally runs once (see empty deps
  // below) so callback identity changes never force a reconnect. But that
  // means the handlers below must never close over onGraphUpdate/onAlert/etc
  // directly — they'd freeze at whatever those props were on first render.
  // Refs updated every render keep the handlers reading current logic
  // (e.g. connectionMode-dependent behavior in SimulationProvider) while the
  // socket connection itself stays stable.
  const callbacksRef = useRef({})
  callbacksRef.current = { onGraphUpdate, onAlert, onHealingTriggered, onConnect, onDisconnect, onReconnect }

  useEffect(() => {
    const socket = io(WS_URL, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 5,
      reconnectionDelay: 2000,
      timeout: 5000,
    })

    socket.on('connect', () => {
      const wasConnected = socketRef.current?._wasConnected
      setIsConnected(true)
      console.log('[WS] Connected to GraphSentinel backend ✓')
      callbacksRef.current.onConnect?.()

      // § 2 soft spot: reconnect does not re-emit graph_update
      // Trigger a REST refresh so the UI doesn't show stale state after a reconnect
      if (wasConnected) {
        console.log('[WS] Reconnect detected — triggering REST refresh')
        callbacksRef.current.onReconnect?.()
      }
      if (socketRef.current) socketRef.current._wasConnected = true
    })

    socket.on('graph_update', (data) => {
      callbacksRef.current.onGraphUpdate?.(data)
    })

    socket.on('alert', (data) => {
      callbacksRef.current.onAlert?.(data)
    })

    socket.on('healing_triggered', (data) => {
      callbacksRef.current.onHealingTriggered?.(data)
    })

    socket.on('disconnect', () => {
      setIsConnected(false)
      console.warn('[WS] Disconnected from backend — falling back to REST polling')
      callbacksRef.current.onDisconnect?.()
    })

    socket.on('connect_error', () => {
      console.info('[WS] Backend not reachable — falling back to REST polling')
    })

    socketRef.current = socket
    return () => {
      socket.disconnect()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  // Intentionally empty — see callbacksRef comment above for why this is safe

  return { isConnected }
}

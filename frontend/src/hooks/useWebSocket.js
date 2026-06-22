// [Windows] GraphSentinel — Susheep
// WebSocket hook — socket.io-client@4 ↔ python-socketio@5
// § 2 known soft spot: reconnect does NOT re-emit graph_update
//   → on reconnect, trigger onReconnect() so caller can REST-fetch fresh state
import { useEffect, useRef, useState } from 'react'
import { io } from 'socket.io-client'

const WS_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

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
      if (onConnect) onConnect()

      // § 2 soft spot: reconnect does not re-emit graph_update
      // Trigger a REST refresh so the UI doesn't show stale state after a reconnect
      if (wasConnected && onReconnect) {
        console.log('[WS] Reconnect detected — triggering REST refresh')
        onReconnect()
      }
      if (socketRef.current) socketRef.current._wasConnected = true
    })

    socket.on('graph_update', (data) => {
      if (onGraphUpdate) onGraphUpdate(data)
    })

    socket.on('alert', (data) => {
      if (onAlert) onAlert(data)
    })

    socket.on('healing_triggered', (data) => {
      if (onHealingTriggered) onHealingTriggered(data)
    })

    socket.on('disconnect', () => {
      setIsConnected(false)
      console.warn('[WS] Disconnected — mock data stays active')
      if (onDisconnect) onDisconnect()
    })

    socket.on('connect_error', () => {
      console.info('[WS] Backend not reachable — running in simulation mode')
    })

    socketRef.current = socket
    return () => {
      socket.disconnect()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  // Callbacks are stable refs — intentionally not in deps to avoid re-connecting

  return { isConnected }
}

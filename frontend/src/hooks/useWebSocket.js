// [Windows] GraphSentinel — Susheep
// WebSocket hook — socket.io-client@4 ↔ python-socketio@5
import { useEffect, useRef, useState } from 'react'
import { io } from 'socket.io-client'

const WS_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

export function useWebSocket({ onGraphUpdate, onAlert, onHealingTriggered, onConnect, onDisconnect }) {
  const socketRef = useRef(null)
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    const socket = io(WS_URL, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 3,
      reconnectionDelay: 2000,
      timeout: 5000,
    })

    socket.on('connect', () => {
      setIsConnected(true)
      console.log('[WS] Connected to GraphSentinel backend ✓')
      if (onConnect) onConnect()
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
    return () => socket.disconnect()
  }, [])

  return { isConnected }
}

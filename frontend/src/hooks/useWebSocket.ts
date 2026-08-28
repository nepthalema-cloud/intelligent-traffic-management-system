/**
 * useWebSocket — authenticated WebSocket client with auto-reconnect.
 *
 * Connects to ws://host/ws/{path}/?token=<access_token>
 * The JWT token is passed as a query parameter — the server validates it
 * before accepting the connection.
 *
 * On disconnect: exponential backoff reconnect (1s, 2s, 4s … max 30s).
 * On token expiry (close code 4001): refreshes token and reconnects.
 */

import { useEffect, useRef, useCallback, useState } from 'react'
import { tokenStorage } from '@/lib/apiClient'

const DEFAULT_WS_PORT = import.meta.env.VITE_WS_PORT ?? '8000'
const FALLBACK_WS_BASE = typeof window !== 'undefined'
  ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:${DEFAULT_WS_PORT}`
  : `ws://localhost:${DEFAULT_WS_PORT}`
const WS_BASE = (import.meta.env.VITE_WS_URL?.trim() || FALLBACK_WS_BASE).replace(/\/$/, '')
const MAX_BACKOFF = 30_000

type MessageHandler = (type: string, payload: unknown) => void

interface UseWebSocketOptions {
  path: string          // e.g. 'dashboard' → ws://host/ws/dashboard/
  onMessage: MessageHandler
  enabled?: boolean
}

export function useWebSocket({ path, onMessage, enabled = true }: UseWebSocketOptions) {
  const wsRef          = useRef<WebSocket | null>(null)
  const backoffRef     = useRef(1000)
  const timerRef       = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const onMessageRef   = useRef(onMessage)
  const [connected, setConnected] = useState(false)

  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])

  const connect = useCallback(() => {
    if (!enabled) return
    const token = tokenStorage.getAccess()
    if (!token) return

    const url = `${WS_BASE}/ws/${path}/?token=${encodeURIComponent(token)}`
    const ws  = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      backoffRef.current = 1000  // reset backoff on successful connect
    }

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as { type: string; payload: unknown }
        onMessageRef.current(msg.type, msg.payload)
      } catch { /* ignore malformed message */ }
    }

    ws.onclose = (ev) => {
      setConnected(false)
      wsRef.current = null

      if (ev.code === 1000) return  // clean close — don't reconnect

      const delay = ev.code === 4001
        ? 500   // token expired — reconnect quickly after token refresh
        : Math.min(backoffRef.current, MAX_BACKOFF)

      if (ev.code !== 4001) {
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF)
      }

      timerRef.current = setTimeout(connect, delay)
    }

    ws.onerror = () => {
      // onclose fires after onerror — reconnect handled there
      setConnected(false)
    }
  }, [path, enabled])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(timerRef.current)
      wsRef.current?.close(1000)
    }
  }, [connect])

  return { connected }
}

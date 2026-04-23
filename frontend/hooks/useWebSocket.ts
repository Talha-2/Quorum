'use client'

import { useEffect, useRef, useCallback, useState } from 'react'

type MessageHandler = (data: any) => void

interface WebSocketConfig {
  url: string
  reconnectAttempts?: number
  reconnectDelay?: number
}

export function useWebSocket(config: WebSocketConfig) {
  const ws = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const reconnectCount = useRef(0)
  const handlers = useRef<Map<string, Set<MessageHandler>>>(new Map())

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    try {
      ws.current = new WebSocket(config.url)

      ws.current.onopen = () => {
        setConnected(true)
        setError(null)
        reconnectCount.current = 0
      }

      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          const { type, data } = message

          const typeHandlers = handlers.current.get(type)
          if (typeHandlers) {
            typeHandlers.forEach(handler => handler(data))
          }

          // Also call wildcard handlers
          const wildcardHandlers = handlers.current.get('*')
          if (wildcardHandlers) {
            wildcardHandlers.forEach(handler => handler(message))
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.current.onerror = (event) => {
        const errorMsg = 'WebSocket connection error'
        setError(errorMsg)
        setConnected(false)
      }

      ws.current.onclose = () => {
        setConnected(false)

        // Attempt to reconnect
        const attempts = config.reconnectAttempts || 5
        const delay = config.reconnectDelay || 3000

        if (reconnectCount.current < attempts) {
          reconnectCount.current++
          setTimeout(connect, delay * reconnectCount.current)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed')
      setConnected(false)
    }
  }, [config])

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close()
      ws.current = null
    }
    setConnected(false)
  }, [])

  const send = useCallback((type: string, data?: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type, data }))
    } else {
      console.warn('WebSocket is not connected')
    }
  }, [])

  const on = useCallback((type: string, handler: MessageHandler) => {
    if (!handlers.current.has(type)) {
      handlers.current.set(type, new Set())
    }
    handlers.current.get(type)!.add(handler)

    return () => {
      handlers.current.get(type)?.delete(handler)
    }
  }, [])

  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    connected,
    error,
    send,
    on,
    disconnect,
    reconnect: connect,
  }
}

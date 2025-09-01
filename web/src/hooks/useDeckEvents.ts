'use client'

import { useState, useEffect, useCallback } from 'react'
import { DeckEvent, apiClient } from '@/lib/api'
import { DeckWebSocket } from '@/lib/websocket'

export function useDeckEvents(deckId: string | null) {
  const [events, setEvents] = useState<DeckEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleNewEvent = useCallback((event: DeckEvent) => {
    console.log('🎯 Processing new deck event:', event)

    setEvents(prev => {
      // Avoid duplicates
      if (prev.some(e => e.id === event.id)) {
        console.log('⚠️ Duplicate event ignored:', event.id)
        return prev
      }

      const newEvents = [...prev, event].sort((a, b) => a.version - b.version)
      console.log(`📈 Events updated: ${prev.length} -> ${newEvents.length}`)

      return newEvents
    })
  }, [])

  useEffect(() => {
    if (!deckId) return

    let ws: DeckWebSocket | null = null

    // Fetch existing events first
    const fetchEvents = async () => {
      console.log(`📋 Fetching existing events for deck: ${deckId}`)

      try {
        const existingEvents = await apiClient.getDeckEvents(deckId)
        console.log(`📊 Found ${existingEvents.length} existing events:`, existingEvents)

        setEvents(existingEvents)

        // Connect to WebSocket for real-time updates
        const lastVersion = existingEvents.length > 0
          ? Math.max(...existingEvents.map(e => e.version))
          : 0

        console.log(`🔌 Setting up WebSocket with last version: ${lastVersion}`)

        ws = new DeckWebSocket(
          deckId,
          lastVersion,
          handleNewEvent,
          (error) => {
            console.error('🚨 WebSocket connection error:', error)
            setError('WebSocket connection error')
            setIsConnected(false)
          },
          () => {
            console.log('🔌 WebSocket connection closed')
            setIsConnected(false)
          }
        )

        ws.connect()
        setIsConnected(true)
        setError(null)
        console.log('✅ Deck events hook initialized successfully')
      } catch (err) {
        console.error('❌ Failed to fetch deck events:', err)
        setError(err instanceof Error ? err.message : 'Failed to fetch events')
      }
    }

    fetchEvents()

    return () => {
      if (ws) {
        ws.disconnect()
      }
    }
  }, [deckId, handleNewEvent])

  return {
    events,
    isConnected,
    error,
  }
}

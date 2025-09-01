'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useDeckEvents } from '@/hooks/useDeckEvents'
import { Deck, DeckEvent } from '@/lib/api'

interface DeckProgressProps {
  deck: Deck
}

const statusMessages = {
  PENDING: 'Preparing to create your presentation...',
  PLANNING: 'Planning the structure and content...',
  GENERATING: 'Generating slides with AI...',
  COMPLETED: 'Your presentation is ready!',
  FAILED: 'Something went wrong. Please try again.',
  CANCELLED: 'Presentation creation was cancelled.',
}

const statusProgress = {
  PENDING: 10,
  PLANNING: 30,
  GENERATING: 70,
  COMPLETED: 100,
  FAILED: 0,
  CANCELLED: 0,
}

export function DeckProgress({ deck }: DeckProgressProps) {
  const { events, isConnected } = useDeckEvents(deck.id)
  const [currentStatus, setCurrentStatus] = useState(deck.status)
  const [recentEvents, setRecentEvents] = useState<DeckEvent[]>([])

  useEffect(() => {
    if (events.length > 0) {
      console.log(`📊 Processing ${events.length} events for deck progress`)
      setRecentEvents(events.slice(-5).reverse())

      // Update status based on latest events
      const latestEvent = events[events.length - 1]
      console.log('🎯 Latest event for status update:', latestEvent)

      let newStatus = currentStatus
      if (latestEvent.event_type === 'DeckCompleted') {
        newStatus = 'COMPLETED'
      } else if (latestEvent.event_type === 'DeckFailed') {
        newStatus = 'FAILED'
      } else if (latestEvent.event_type === 'PlanUpdated') {
        newStatus = 'PLANNING'
      } else if (latestEvent.event_type.startsWith('Slide')) {
        newStatus = 'GENERATING'
      }

      if (newStatus !== currentStatus) {
        console.log(`📈 Status updated: ${currentStatus} -> ${newStatus}`)
        setCurrentStatus(newStatus)
      }
    }
  }, [events, currentStatus])

  const getEventMessage = (event: DeckEvent): string => {
    switch (event.event_type) {
      case 'DeckStarted':
        return 'Started creating presentation'
      case 'PlanUpdated':
        return `Created outline with ${event.event_data.slide_count || 'several'} slides`
      case 'SlideAdded':
        return `Added slide: ${event.event_data.title || 'New slide'}`
      case 'SlideUpdated':
        return `Updated slide: ${event.event_data.title || 'Slide'}`
      case 'DeckCompleted':
        return 'Presentation completed successfully!'
      case 'DeckFailed':
        return `Error: ${event.event_data.error || 'Unknown error'}`
      case 'Heartbeat':
        return 'Processing...'
      default:
        return event.event_type
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>{deck.title || 'Creating Presentation'}</span>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-green-500' : 'bg-red-500'
              }`} />
              <span className="text-sm text-muted-foreground">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span>{statusMessages[currentStatus]}</span>
              <span>{statusProgress[currentStatus]}%</span>
            </div>
            <Progress value={statusProgress[currentStatus]} />
          </div>

          {deck.description && (
            <p className="text-sm text-muted-foreground">{deck.description}</p>
          )}
        </CardContent>
      </Card>

      {recentEvents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {recentEvents.map((event) => (
                <div
                  key={event.id}
                  className="flex items-start gap-3 text-sm"
                >
                  <div className="w-2 h-2 rounded-full bg-blue-500 mt-2 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="text-foreground">{getEventMessage(event)}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(event.created_at).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

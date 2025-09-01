'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DeckProgress } from '@/components/DeckProgress'
import { Deck, apiClient } from '@/lib/api'
import { ArrowLeft, Download, Eye } from 'lucide-react'

export default function DeckPage() {
  const params = useParams()
  const router = useRouter()
  const [deck, setDeck] = useState<Deck | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const deckId = Array.isArray(params.id) ? params.id[0] : params.id

  useEffect(() => {
    if (!deckId) return

    const fetchDeck = async () => {
      try {
        const deckData = await apiClient.getDeck(deckId)
        setDeck(deckData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch deck')
      } finally {
        setLoading(false)
      }
    }

    fetchDeck()
  }, [deckId])

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-gray-600">Loading presentation...</p>
        </div>
      </div>
    )
  }

  if (error || !deck) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center text-red-600">Error</CardTitle>
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <p className="text-gray-600">
              {error || 'Presentation not found'}
            </p>
            <Button onClick={() => router.push('/')} variant="outline">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Go Back
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const isCompleted = deck.status === 'COMPLETED'

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <div className="flex items-center justify-between mb-6">
          <Button
            onClick={() => router.push('/')}
            variant="ghost"
            size="sm"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Button>

          {isCompleted && (
            <div className="flex gap-2">
              <Button variant="outline" size="sm">
                <Eye className="w-4 h-4 mr-2" />
                Preview
              </Button>
              <Button size="sm">
                <Download className="w-4 h-4 mr-2" />
                Download
              </Button>
            </div>
          )}
        </div>

        <DeckProgress deck={deck} />

        {isCompleted && deck.slides && deck.slides.length > 0 && (
          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Slides Preview</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {deck.slides.map((slide, index) => (
                  <div
                    key={slide.id}
                    className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
                  >
                    <div className="text-sm font-medium mb-2">
                      Slide {index + 1}
                    </div>
                    <div className="text-sm text-muted-foreground mb-2">
                      {slide.title}
                    </div>
                    <div
                      className="text-xs text-muted-foreground h-20 overflow-hidden"
                      dangerouslySetInnerHTML={{ __html: slide.content }}
                    />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

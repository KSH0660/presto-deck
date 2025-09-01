'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { apiClient } from '@/lib/api'
import { useDeckStore } from '@/store/deckStore'

export function DeckCreationForm() {
  const [prompt, setPrompt] = useState('')
  const router = useRouter()
  const { setCurrentDeck, setCreating, setError, isCreating } = useDeckStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt.trim()) return

    console.log('🚀 Starting deck creation process...')
    console.log('📝 User prompt:', prompt.trim())

    setCreating(true)
    setError(null)

    try {
      console.log('🔄 Calling API to create deck...')
      const deck = await apiClient.createDeck({ prompt: prompt.trim() })

      console.log('✅ Deck created successfully:', deck)
      console.log(`📊 Deck ID: ${deck.id}, Status: ${deck.status}`)

      setCurrentDeck(deck)

      console.log(`🔗 Navigating to deck page: /deck/${deck.id}`)
      router.push(`/deck/${deck.id}`)
    } catch (error) {
      console.error('❌ Deck creation failed:', error)
      setError(error instanceof Error ? error.message : 'Failed to create deck')
    } finally {
      setCreating(false)
      console.log('🏁 Deck creation process completed')
    }
  }

  return (
    <Card className="w-full max-w-2xl">
      <CardHeader className="text-center">
        <CardTitle className="text-3xl font-bold">Create Your Presentation</CardTitle>
        <CardDescription className="text-lg">
          Describe what you want and our AI will create a professional presentation for you
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label
              htmlFor="prompt"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Describe your presentation
            </label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g., Create a presentation about machine learning for beginners with 8 slides covering basics, algorithms, and applications..."
              className="w-full px-4 py-3 border border-input rounded-lg focus:ring-2 focus:ring-ring focus:border-transparent resize-none bg-background"
              rows={4}
              required
              disabled={isCreating}
            />
          </div>

          <Button
            type="submit"
            disabled={!prompt.trim() || isCreating}
            className="w-full"
            size="lg"
          >
            {isCreating ? 'Creating Presentation...' : 'Generate Presentation'}
          </Button>

          <div className="text-center text-sm text-muted-foreground">
            <p>✨ Powered by AI • 🚀 Fast • 💼 Professional Quality</p>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

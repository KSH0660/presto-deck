'use client'

import { create } from 'zustand'
import { Deck } from '@/lib/api'

interface DeckStore {
  currentDeck: Deck | null
  decks: Deck[]
  isCreating: boolean
  error: string | null

  setCurrentDeck: (deck: Deck | null) => void
  setDecks: (decks: Deck[]) => void
  addDeck: (deck: Deck) => void
  updateDeck: (deckId: string, updates: Partial<Deck>) => void
  setCreating: (isCreating: boolean) => void
  setError: (error: string | null) => void
}

export const useDeckStore = create<DeckStore>((set, get) => ({
  currentDeck: null,
  decks: [],
  isCreating: false,
  error: null,

  setCurrentDeck: (deck) => set({ currentDeck: deck }),

  setDecks: (decks) => set({ decks }),

  addDeck: (deck) => set((state) => ({
    decks: [deck, ...state.decks]
  })),

  updateDeck: (deckId, updates) => set((state) => ({
    decks: state.decks.map(deck =>
      deck.id === deckId ? { ...deck, ...updates } : deck
    ),
    currentDeck: state.currentDeck?.id === deckId
      ? { ...state.currentDeck, ...updates }
      : state.currentDeck
  })),

  setCreating: (isCreating) => set({ isCreating }),

  setError: (error) => set({ error })
}))

import { DeckCreationForm } from '@/components/DeckCreationForm'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full flex flex-col items-center space-y-8">
        <div className="text-center">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            Presto Deck
          </h1>
          <p className="text-xl text-gray-600">
            AI-powered presentation generation in seconds
          </p>
        </div>

        <DeckCreationForm />
      </div>
    </main>
  )
}

# Presto Deck - Frontend

AI-powered presentation generation web application built with Next.js 15.

## Tech Stack

- **Next.js 15** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **shadcn/ui** - UI components
- **Zustand** - State management
- **TanStack Query** - Server state management (ready to use)
- **WebSocket** - Real-time communication
- **Lucide React** - Icons

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

1. Install dependencies:
```bash
npm install
```

2. Copy environment variables:
```bash
cp .env.local.example .env.local
```

3. Update `.env.local` with your backend API URLs:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Development

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser.

### Build

```bash
npm run build
npm start
```

## Features

- ✅ **Deck Creation**: Create presentations with AI prompts
- ✅ **Real-time Progress**: WebSocket-based live updates
- ✅ **Responsive Design**: Works on desktop and mobile
- ✅ **Type Safety**: Full TypeScript support
- ✅ **Modern UI**: Clean design with shadcn/ui components

## Project Structure

```
src/
├── app/                 # Next.js App Router pages
│   ├── page.tsx        # Home page (deck creation)
│   └── deck/[id]/      # Deck progress page
├── components/         # React components
│   ├── ui/            # shadcn/ui base components
│   ├── DeckCreationForm.tsx
│   └── DeckProgress.tsx
├── hooks/             # Custom React hooks
├── lib/               # Utilities
│   ├── api.ts        # Backend API client
│   ├── websocket.ts  # WebSocket client
│   └── utils.ts      # Helper functions
└── store/            # Zustand stores
    └── deckStore.ts  # Deck state management
```

## API Integration

The frontend connects to the FastAPI backend:

- **REST API**: Create decks, fetch data
- **WebSocket**: Real-time event updates
- **Event Sourcing**: Progress tracking with events

## Environment Variables

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Authentication (future)
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-secret-key
```

## Commands

```bash
# Development
npm run dev          # Start dev server
npm run build        # Build for production
npm start            # Start production server
npm run lint         # Run ESLint
```

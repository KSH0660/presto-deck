# 🎯 Presto Deck - AI-Powered Presentation Generator

A simple POC for generating AI-powered presentations with real-time streaming updates.

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- **Redis** (required for WebSocket, background jobs, event streaming)
- PostgreSQL (optional, uses SQLite by default)

### Setup & Run

```bash
# Clone and setup
git clone <repository-url>
cd presto-deck-v1/backend

# Start Redis (required)
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Install dependencies
make setup

# Configure environment
cp .env.example .env
# Edit .env with your settings:
# - Set OPENAI_API_KEY for OpenAI
# - Or set OPENAI_BASE_URL for custom LLM servers (Ollama, LocalAI, etc.)

# Start development server
make dev
```

Or use docker-compose for all dependencies:

```bash
# Start Redis and PostgreSQL
docker-compose up -d

# Then follow the same setup steps above
```

The API will be available at `http://localhost:8000`

### Using Custom LLM Servers

For OpenAI-compatible servers like Ollama or LocalAI, set the base URL in your `.env`:

```bash
# For Ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama2

# For LocalAI
OPENAI_BASE_URL=http://localhost:8080/v1
```

## 🛠️ Available Commands

```bash
make help     # Show all available commands
make setup    # Install dependencies
make dev      # Start development server
make test     # Run tests
make clean    # Clean up cache files
make db-init  # Initialize database
make lint     # Check code quality
make format   # Format code
```

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/            # FastAPI routes
│   ├── application/    # Business logic
│   ├── domain_core/    # Core entities
│   ├── data/          # Repositories
│   └── infra/         # External integrations
├── tests/             # Test files
└── main.py           # Entry point
```

## 🔧 Technology Stack

- **FastAPI** - Web framework
- **SQLAlchemy** - Database ORM
- **LangChain** - LLM integration
- **PostgreSQL/SQLite** - Database
- **Redis** - Background jobs (optional)
- **pytest** - Testing

## 📖 API Usage

### Create a Presentation

```bash
curl -X POST http://localhost:8000/api/v1/decks/ \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer your-jwt-token" \
    -d '{
      "prompt": "Create a presentation about machine learning basics for beginners",
      "style_preferences": {
        "theme": "modern",
        "color_scheme": "blue"
      }
    }'
```

```bash
  curl -X GET "http://localhost:8000/api/v1/decks/1cf5c133-8cb2-40da-8b85-5376f6f722f6/status" \
       -H "Authorization: Bearer your-jwt-token"  | jq .

  curl -X GET "http://localhost:8000/api/v1/decks/1cf5c133-8cb2-40da-8b85-5376f6f722f6/slides" \
       -H "Authorization: Bearer your-jwt-token"  | jq .
```





### WebSocket for Real-time Updates

Connect to `ws://localhost:8000/api/v1/ws/decks/{deck_id}` to receive real-time updates as the presentation is generated.

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test file
uv run pytest tests/unit/test_example.py -v
```

## 📝 Environment Variables

Key environment variables in `.env`:

```bash
# LLM Configuration
OPENAI_API_KEY=your-key-here                    # For OpenAI
OPENAI_BASE_URL=http://localhost:11434/v1       # For custom servers
OPENAI_MODEL=gpt-4                              # Model name

# Database
DATABASE_URL=postgresql://user:pass@localhost/db # Optional, uses SQLite by default

# Redis (optional)
REDIS_URL=redis://localhost:6379
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `make test`
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

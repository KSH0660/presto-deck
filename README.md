# 🎯 Presto Deck - AI-Powered Presentation Generator

A simple POC for generating AI-powered presentations with real-time streaming updates.

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- PostgreSQL (optional, uses SQLite by default)
- Redis (optional, for background jobs)

### Setup & Run

```bash
# Clone and setup
git clone <repository-url>
cd presto-deck-v1/backend

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
curl -X POST "http://localhost:8000/api/v1/decks" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a presentation about AI in healthcare"}'
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

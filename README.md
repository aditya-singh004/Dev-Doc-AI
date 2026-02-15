# AI-Powered Developer Documentation Chatbot

An intelligent chatbot that integrates with Slack to answer technical queries instantly using a Retrieval-Augmented Generation (RAG) approach.

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│  Slack User │────▶│   Slack     │────▶│  n8n Workflow   │────▶│  FastAPI    │
│             │     │  Webhook    │     │  (Automation)   │     │  Backend    │
└─────────────┘     └─────────────┘     └─────────────────┘     └──────┬──────┘
                                                                       │
                                                                       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│   Slack     │◀────│  n8n        │◀────│  LLM Response   │◀────│  LlamaIndex │
│  Response   │     │  Formatter  │     │  Generation     │     │  RAG Engine │
└─────────────┘     └─────────────┘     └─────────────────┘     └─────────────┘
```

## ✨ Features

- **Slack Integration**: Real-time message handling via webhooks
- **RAG Pipeline**: Semantic search over documentation using LlamaIndex
- **Multi-LLM Support**: OpenAI GPT or Google Gemini
- **Conversation Memory**: Context-aware responses per user
- **n8n Workflow**: Visual workflow automation
- **Docker Ready**: Easy deployment with Docker Compose
- **Modular Design**: Clean, maintainable codebase

## 📁 Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry
│   ├── config.py            # Configuration settings
│   ├── models.py            # Pydantic models
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # API endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── rag_service.py   # LlamaIndex RAG
│   │   ├── llm_service.py   # LLM integration
│   │   └── memory_service.py # Conversation memory
│   └── utils/
│       ├── __init__.py
│       ├── logger.py        # Logging setup
│       └── text_cleaner.py  # Message preprocessing
├── scripts/
│   └── ingest_docs.py       # Documentation ingestion
├── n8n/
│   └── workflow.json        # n8n workflow export
├── docs/
│   ├── SLACK_SETUP.md       # Slack configuration guide
│   └── [your documentation] # Add your docs here
├── storage/
│   └── index/               # Vector store index
├── logs/                    # Application logs
├── .env.example             # Environment template
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container definition
├── docker-compose.yml       # Multi-container setup
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (optional)
- OpenAI API key or Google API key
- Slack workspace with admin access

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd doc-chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# Required: OPENAI_API_KEY or GOOGLE_API_KEY
```

### 3. Add Documentation

Place your documentation files in the `docs/` directory:
- Supported formats: PDF, Markdown, HTML, TXT, RST, JSON

### 4. Ingest Documentation

```bash
# Create vector index from documentation
python scripts/ingest_docs.py --docs-path ./docs --storage-path ./storage/index
```

### 5. Run the Server

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6. Test the API

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Query documentation
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I authenticate?", "user_id": "test-user"}'
```

## 🐳 Docker Deployment

### Using Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f chatbot

# Stop services
docker-compose down
```

### Services

- **chatbot**: FastAPI backend (port 8000)
- **n8n**: Workflow automation (port 5678)

## 🔧 n8n Workflow Setup

1. Access n8n at `http://localhost:5678`
2. Import workflow from `n8n/workflow.json`
3. Configure Slack OAuth2 credentials
4. Update webhook URL in Slack app settings
5. Activate the workflow

## 💬 Slack Integration

See [docs/SLACK_SETUP.md](docs/SLACK_SETUP.md) for detailed instructions.

Quick steps:
1. Create Slack app at api.slack.com
2. Add bot permissions
3. Enable event subscriptions
4. Point webhook to n8n
5. Install app to workspace

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/api/v1/health` | GET | Health check |
| `/api/v1/query` | POST | Query documentation |
| `/api/v1/slack/events` | POST | Slack webhook handler |
| `/api/v1/memory/{user_id}` | DELETE | Clear user memory |
| `/api/v1/stats` | GET | Service statistics |

### Query Request

```json
{
  "query": "How do I authenticate with the API?",
  "user_id": "U12345678",
  "channel_id": "C12345678",
  "include_sources": true
}
```

### Query Response

```json
{
  "answer": "To authenticate with the API, you need to...",
  "sources": [
    {
      "content": "Authentication requires an API key...",
      "source": "auth.md",
      "score": 0.95
    }
  ],
  "query": "How do I authenticate with the API?",
  "timestamp": "2024-01-15T10:30:00Z",
  "processing_time_ms": 1250.5
}
```

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | openai | LLM provider (openai/gemini) |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `GOOGLE_API_KEY` | - | Google API key |
| `CHUNK_SIZE` | 512 | Document chunk size |
| `TOP_K_RESULTS` | 5 | Number of retrieved docs |
| `ENABLE_MEMORY` | true | Enable conversation memory |
| `MAX_CONVERSATION_HISTORY` | 10 | Max messages to remember |

See [.env.example](.env.example) for all options.

## 🔒 Security Considerations

- Store API keys in environment variables
- Use HTTPS in production
- Verify Slack request signatures
- Implement rate limiting
- Restrict CORS origins in production

## 📊 Monitoring

- Health endpoint: `/api/v1/health`
- Stats endpoint: `/api/v1/stats`
- Logs: `./logs/app.log`
- Docker health checks included

## 🧪 Development

```bash
# Run tests
pytest

# Format code
black app/ scripts/
isort app/ scripts/

# Type checking
mypy app/
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Run tests
5. Submit pull request

## 📝 License

MIT License - see LICENSE file for details.

## 🆘 Troubleshooting

### Index Not Loading

```bash
# Re-run ingestion
python scripts/ingest_docs.py
```

### LLM Errors

- Verify API keys are set
- Check rate limits
- Review logs for details

### Slack Not Responding

- Verify n8n workflow is active
- Check webhook URL configuration
- Review n8n execution logs

### Memory Issues

- Reduce `CHUNK_SIZE`
- Lower `TOP_K_RESULTS`
- Use smaller embedding model

# AI-Powered Developer Documentation Chatbot

An intelligent chatbot that integrates with Slack and a web UI to answer technical queries using **RAG** and an optional **autonomous agent** (OpenAI tool loop: documentation search, allowlisted HTTP, approval-gated Slack post, working memory, persisted traces).

## Live Demo

- Chat UI: https://dev-doc-ai-1.onrender.com/chat
- API Docs: https://dev-doc-ai-1.onrender.com/docs
- Health Check: https://dev-doc-ai-1.onrender.com/api/v1/health

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

- **Slack Integration**: Real-time message handling via webhooks (n8n → FastAPI)
- **Web Chat UI**: `/chat` with **Quick** (`/query`) and **Agent** (`/agent/run`) modes
- **RAG Pipeline**: Semantic search over documentation using LlamaIndex
- **Autonomous Agent**: Tool calling, separate working memory, rate limits, JSON trace files
- **Multi-LLM Support**: OpenAI GPT or Google Gemini for `/query`; agent path uses OpenAI
- **Conversation Memory**: Context-aware `/query` and agent transcript per `user_id`
- **n8n Workflow**: Routes to **agent** or **quick** API via `DDA_USE_AGENT`
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
│   │   ├── rag_service.py        # LlamaIndex RAG
│   │   ├── llm_service.py        # LLM integration
│   │   ├── memory_service.py     # Conversation memory
│   │   ├── agent_service.py      # Autonomous agent (OpenAI tools)
│   │   ├── agent_working_memory.py
│   │   └── agent_trace.py        # Persisted run traces (JSON)
│   └── utils/
│       ├── __init__.py
│       ├── logger.py             # Logging setup
│       ├── text_cleaner.py       # Message preprocessing
│       └── agent_rate_limit.py   # /agent/run rate limit
├── scripts/
│   └── ingest_docs.py       # Documentation ingestion
├── n8n/
│   └── workflow.json        # n8n workflow export
├── docs/
│   ├── SLACK_SETUP.md       # Slack configuration guide
│   └── [your documentation] # Add your docs here
├── storage/
│   └── index/               # Vector store index
├── frontend/
│   └── index.html           # Chat UI (Quick + Agent)
├── logs/                    # Application logs (and agent_traces/ when enabled)
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

# Query documentation (single RAG + LLM)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I authenticate?", "user_id": "test-user"}'

# Autonomous agent (requires OPENAI_API_KEY; optional agent_session_id, approval for Slack tool)
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{"query": "Summarize auth and Slack setup from docs", "user_id": "test-user", "agent_session_id": "cli-1", "include_sources": true}'
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

- **chatbot**: FastAPI backend (port 8000); chat UI at `http://localhost:8000/chat`
- **n8n**: Workflow automation (port 5678). Set `DDA_USE_AGENT=true` (default in Compose) to call `/api/v1/agent/run`, or `false` for `/api/v1/query`. Optional: `DDA_AGENT_APPROVAL_SECRET` / `DDA_AGENT_ALLOW_SENSITIVE` for the Slack post tool (must align with `AGENT_APPROVAL_SECRET` on the chatbot).

## Render Deployment

This repo includes a Render blueprint in `render.yaml` for one-click setup.

### Option 1: Blueprint (recommended)

1. Push this repo to GitHub.
2. In Render, click **New +** -> **Blueprint**.
3. Select your repo.
4. Set `OPENAI_API_KEY` in Render environment variables.
5. Deploy.

### Option 2: Manual Web Service

- **Runtime**: Python 3.11
- **Build Command**: `pip install -r requirements-render.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/api/v1/health`

Required environment variables:

- `OPENAI_API_KEY` (required for embeddings and for `/agent/run`)
- `LLM_PROVIDER=openai`
- `AUTO_INGEST_ON_STARTUP=true`
- `DOCS_DIRECTORY=./docs`
- `INDEX_STORAGE_PATH=/tmp/storage/index`

Optional agent-related variables are listed in [.env.example](.env.example) (`AGENT_*`, `SLACK_POST_CHANNEL_ALLOWLIST`, etc.).

Notes:

- `storage/` is gitignored, so index is auto-created at startup from `docs/`.
- `/tmp` on Render is ephemeral. Re-deploys may trigger re-ingestion.
- Keep docs in `docs/` so auto-ingestion can build the index.
## n8n Workflow Setup

1. Access n8n at `http://localhost:5678`
2. Import workflow from `n8n/workflow.json`
3. Configure Slack OAuth2 credentials
4. Update webhook URL in Slack app settings
5. Activate the workflow

The workflow includes **Route Backend API**: it posts to **`/api/v1/agent/run`** when the n8n container has `DDA_USE_AGENT=true` or `1`, otherwise **`/api/v1/query`**. Agent calls use `agent_session_id` `slack:<slack_user_id>` for working memory. Increase the HTTP node timeout if agent runs are slow (default 120s in the export).

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
| `/chat` | GET | Web chat UI (Quick + Agent) |
| `/api/v1/query` | POST | Query documentation (RAG + LLM) |
| `/api/v1/agent/run` | POST | Autonomous agent (tools, traces) |
| `/api/v1/agent/working-memory` | DELETE | Clear agent working memory (`user_id` or `agent_session_id` query param) |
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

### Agent run request (excerpt)

```json
{
  "query": "What do the docs say about Docker?",
  "user_id": "U123",
  "agent_session_id": "slack:U123",
  "include_sources": true,
  "allow_sensitive_tools": false,
  "approval_secret": null
}
```

### Agent run response (excerpt)

```json
{
  "answer": "...",
  "sources": [],
  "trace_id": "uuid",
  "iterations": 3,
  "tool_calls": 2,
  "processing_time_ms": 8500
}
```

Traces are also written as JSON under `AGENT_TRACE_DIR` when `AGENT_TRACE_PERSIST=true`.

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
| `AGENT_MAX_ITERATIONS` | 10 | Agent LLM rounds (cap) |
| `AGENT_MAX_TOOL_CALLS` | 20 | Budget for search/http/Slack tools per run |
| `AGENT_APPROVAL_SECRET` | (unset) | Required on requests that allow `slack_post_message` |
| `AGENT_TRACE_PERSIST` | true | Write JSON traces to `AGENT_TRACE_DIR` |
| `AGENT_RATE_LIMIT_PER_MINUTE` | 30 | Per-user/IP limit on `/agent/run` |

See [.env.example](.env.example) for all options (including `AGENT_HTTP_ALLOWLIST_HOSTS`, `SLACK_POST_CHANNEL_ALLOWLIST`, and n8n `DDA_*` variables).

## 🔒 Security Considerations

- Store API keys in environment variables (`OPENAI_API_KEY`, `AGENT_APPROVAL_SECRET`, Slack tokens)
- Use HTTPS in production
- Verify Slack request signatures
- `/agent/run` has in-process rate limiting; tune `AGENT_RATE_LIMIT_PER_MINUTE`
- Restrict CORS origins in production (`app/main.py`)
- Treat `DDA_AGENT_APPROVAL_SECRET` in n8n like a secret; must match `AGENT_APPROVAL_SECRET` if you enable sensitive tools from Slack

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


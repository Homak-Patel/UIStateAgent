# SoftLight_UIStateAgent

Production-grade, real-time UI state capture agent for a multi-agent AI system.

## 🚀 Quick Start

### One Command Setup

```bash
docker compose -f docker/docker-compose.yml up --build
```

Or use the convenience script:

```bash
./start.sh
```

This will:
- Install all dependencies automatically
- Build and start all services
- Backend API: http://localhost:8000
- Frontend UI: http://localhost:3000
- MCP Server: http://localhost:8001

## 📋 Prerequisites

1. **Docker & Docker Compose** installed
2. **`.env` file** configured with API keys:
   - `OPENAI_API_KEY` (required)
   - `UPSTASH_REDIS_URL`, `UPSTASH_REDIS_TOKEN`, `UPSTASH_REST_URL`, `UPSTASH_REST_TOKEN` (optional)

## 🛑 Stop Services

```bash
docker compose -f docker/docker-compose.yml down
```

## 📝 View Logs

```bash
docker compose -f docker/docker-compose.yml logs -f
```

## 🧹 Clean Up

```bash
docker compose -f docker/docker-compose.yml down -v
```

## Architecture

- **Backend**: FastAPI (async server)
- **Frontend**: Next.js (App Router)
- **Agents**: CrewAI modular sub-agents
- **Orchestration**: LangGraph DAG flows
- **Browser Automation**: Playwright
- **Context Sync**: MCP Server
- **Memory**: Upstash (optional)

## Structure

```
/frontend             → Next.js UI  
/backend              → FastAPI API server  
/agents               → Modular CrewAI agents  
/graph                → LangGraph DAG flows  
/utils                → Logging, Upstash sync, helpers  
/mcp                  → Multi-Context Prompting server  
/data/screenshots     → {app}/{task}/{step}.png  
/data/logs            → Full run logs per workflow  
/docker               → Dockerfiles and docker-compose setup  
```

## Development

See `QUICKSTART.md` for detailed setup instructions.

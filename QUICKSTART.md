# Agent B - Quick Start Guide

## 🚀 One Command Setup

```bash
docker compose -f docker/docker-compose.yml up --build
```

Or use the convenience script:

```bash
./start.sh
```

## ✅ What This Does

- Installs all Python dependencies
- Installs Playwright browsers
- Installs Node.js dependencies
- Starts all services:
  - Backend API: http://localhost:8000
  - Frontend UI: http://localhost:3000
  - MCP Server: http://localhost:8001

## 📋 Prerequisites

1. Docker and Docker Compose installed
2. `.env` file configured with API keys

## 🔧 Environment Setup

Make sure your `.env` file has:
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


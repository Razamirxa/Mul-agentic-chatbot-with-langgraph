# 🎓 MUL AI Assistant — Agentic Chatbot for Minhaj University Lahore

An intelligent, multi-agent chatbot built with **LangGraph**, **FastAPI**, and **Google Gemini** that answers questions about Minhaj University Lahore (MUL) by searching the official website in real-time.

## ✨ Features

- 🧠 **Multi-agent graph** — Router → Web Search → Generator pipeline using LangGraph
- 🔍 **Real-time web search** — Searches `mul.edu.pk` via Tavily API for up-to-date info
- 💬 **Session memory** — Remembers conversation context within a session
- ⚡ **Response cache** — Instant answers for repeated questions (15-min TTL)
- 📡 **SSE streaming** — Live status updates as the agent processes your query
- 🛡️ **Rate limiting** — 20 requests/minute per IP to prevent abuse
- 🔒 **Security hardened** — CORS restricted, input validated, errors sanitized

## 🏗️ Architecture

```
User Query
    │
    ▼
route_query ──┬── mul_related ──→ web_search ──→ generate ──→ Response
              ├── conversational ──────────────→ generate ──→ Response
              └── off_topic ──────────────────→ guardrail ──→ Polite Refusal
```

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/Razamirxa/Mul-agentic-chatbot-with-langgraph.git
cd Mul-agentic-chatbot-with-langgraph
```

### 2. Set up environment variables
```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

### 3. Install dependencies
```bash
pip install uv
uv sync
```

### 4. Run the server
```bash
uv run uvicorn app:app --reload --port 8000
```

### 5. Open the chatbot
Visit [http://localhost:8000](http://localhost:8000) in your browser.

## 🔑 Required API Keys

| Key | Where to Get |
|-----|-------------|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `TAVILY_API_KEY` | [Tavily](https://app.tavily.com) |
| `LANGCHAIN_API_KEY` | [LangSmith](https://smith.langchain.com) (optional, for tracing) |

## 📁 Project Structure

```
├── app.py                  # FastAPI backend (endpoints, rate limiting, CORS)
├── agent/
│   ├── graph.py            # LangGraph state machine definition
│   ├── nodes.py            # Agent node functions (router, search, generator)
│   ├── state.py            # AgentState TypedDict
│   ├── prompts.py          # System prompts for each node
│   └── cache.py            # In-memory LRU cache with TTL
├── static/
│   ├── index.html          # Chat UI
│   ├── style.css           # Styling
│   └── script.js           # Frontend logic (SSE streaming)
├── .env.example            # Template for environment variables
└── pyproject.toml          # Dependencies
```

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Send message, get response |
| `POST` | `/api/chat/stream` | SSE stream with live status updates |
| `GET` | `/api/cache/stats` | Cache hit/miss statistics |
| `POST` | `/api/cache/clear` | Clear stale cache |
| `GET` | `/api/health` | Health check |

## 🛡️ Security

- API keys stored in `.env` (never committed to Git)
- Rate limiting: 20 requests/minute per IP
- CORS restricted to `mul.edu.pk` and localhost
- Input validation: max 1000 characters
- XSS protection in markdown renderer

## 📊 Tech Stack

- **Backend:** FastAPI + Uvicorn
- **AI Framework:** LangGraph + LangChain
- **LLM:** Google Gemini 2.5 Flash
- **Search:** Tavily API (restricted to mul.edu.pk)
- **Frontend:** Vanilla HTML/CSS/JS with SSE streaming
- **Monitoring:** LangSmith tracing

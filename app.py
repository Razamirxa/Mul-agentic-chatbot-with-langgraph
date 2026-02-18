"""FastAPI backend for the MUL Chatbot.

Endpoints:
    POST /api/chat         — Send a message, get a response
    POST /api/chat/stream  — SSE stream with live status updates
    GET  /api/health       — Health check
    GET  /api/cache/stats  — Cache statistics
    POST /api/cache/clear  — Clear stale cache
    GET  /                 — Serve the frontend

Security:
    - Rate limiting: 20 requests/minute per IP (slowapi)
    - Input validation: max 1000 chars, non-empty
    - CORS: restricted to localhost in dev (update for production)
    - Error messages: sanitized, no internal details exposed
"""

import os
import uuid
import json
from dotenv import load_dotenv

# Load environment variables BEFORE importing agent modules
load_dotenv(override=True)

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from langchain_core.messages import HumanMessage
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from agent.graph import graph
from agent.cache import cache


# ── Rate Limiter ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Node status labels for streaming ─────────────
NODE_STATUS = {
    "route_query": {"icon": "🧠", "text": "Understanding your question..."},
    "web_search":  {"icon": "🔍", "text": "Searching mul.edu.pk..."},
    "generate":    {"icon": "✍️",  "text": "Generating response..."},
    "guardrail":   {"icon": "🛡️", "text": "Preparing response..."},
}

# ── Allowed origins (update for production domain) ─
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://www.mul.edu.pk",
    "https://mul.edu.pk",
]


# ── FastAPI App ──────────────────────────────────
app = FastAPI(
    title="MUL Chatbot API",
    description="Agentic AI Chatbot for Minhaj University Lahore",
    version="1.0.0",
    # Disable docs in production (set via env var)
    docs_url="/docs" if os.getenv("ENV", "development") != "production" else None,
    redoc_url=None,
)

# Rate limit error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware — restricted origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ── Request / Response Models ────────────────────
class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        if len(v) > 1000:
            raise ValueError("Message too long (max 1000 characters)")
        return v


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    cached: bool = False


# ── Streaming Endpoint ───────────────────────────
@app.post("/api/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(request: Request, body: ChatRequest):
    """Stream status updates and final response via SSE.

    Rate limited: 20 requests per minute per IP.
    If the response is cached, returns it instantly with a cache-hit status.
    """
    thread_id = body.thread_id or str(uuid.uuid4())

    # ── Check cache first ────────────────────────
    cached_response = cache.get(body.message)
    if cached_response:
        def cached_generator():
            status_data = json.dumps({
                "type": "status",
                "icon": "⚡",
                "text": "Retrieved from cache...",
                "node": "cache",
            })
            yield f"data: {status_data}\n\n"

            data = json.dumps({
                "type": "response",
                "response": cached_response,
                "thread_id": thread_id,
                "cached": True,
            })
            yield f"data: {data}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(
            cached_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── No cache hit — run the graph ─────────────
    def event_generator():
        try:
            config = {"configurable": {"thread_id": thread_id}}
            final_response = None

            for event in graph.stream(
                {"messages": [HumanMessage(content=body.message)]},
                config=config,
                stream_mode="updates",
            ):
                for node_name in event:
                    status = NODE_STATUS.get(node_name)
                    if status:
                        data = json.dumps({
                            "type": "status",
                            "icon": status["icon"],
                            "text": status["text"],
                            "node": node_name,
                        })
                        yield f"data: {data}\n\n"

                    node_output = event[node_name]
                    if "response" in node_output and node_output["response"]:
                        final_response = node_output["response"]
                        data = json.dumps({
                            "type": "response",
                            "response": final_response,
                            "thread_id": thread_id,
                        })
                        yield f"data: {data}\n\n"

            if final_response:
                cache.put(body.message, final_response)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            # Log internally, never expose to client
            print(f"[ERROR] Stream error for thread {thread_id}: {e}")
            error_data = json.dumps({
                "type": "error",
                "response": "I'm sorry, something went wrong. Please try again.",
                "thread_id": thread_id,
            })
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Fallback non-streaming endpoint ─────────────
@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest):
    """Process a user message and return the response.

    Rate limited: 20 requests per minute per IP.
    """
    thread_id = body.thread_id or str(uuid.uuid4())

    cached_response = cache.get(body.message)
    if cached_response:
        return ChatResponse(response=cached_response, thread_id=thread_id, cached=True)

    try:
        config = {"configurable": {"thread_id": thread_id}}
        result = graph.invoke(
            {"messages": [HumanMessage(content=body.message)]},
            config=config,
        )

        response_text = result.get(
            "response",
            "I'm sorry, I couldn't process your request. Please try again."
        )
        cache.put(body.message, response_text)
        return ChatResponse(response=response_text, thread_id=thread_id)

    except Exception as e:
        print(f"[ERROR] Chat error for thread {thread_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your message. Please try again.",
        )


# ── Cache Endpoints ──────────────────────────────
@app.get("/api/cache/stats")
async def cache_stats():
    """Return cache statistics for monitoring."""
    return JSONResponse(content=cache.stats())


@app.post("/api/cache/clear")
async def cache_clear():
    """Clear all cached entries (use when MUL website data is updated)."""
    cache.clear()
    return JSONResponse(content={
        "status": "cleared",
        "message": "Cache cleared. Next requests will fetch fresh data.",
    })


# ── Health Check ─────────────────────────────────
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(content={"status": "healthy", "service": "MUL Chatbot"})


# ── Serve Frontend Static Files ──────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_frontend():
    """Serve the main chat UI."""
    return FileResponse("static/index.html")

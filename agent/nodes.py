"""Graph node functions for the MUL chatbot agent.

Each function takes the AgentState and returns a partial state update.
Nodes: route_query, web_search, generate, guardrail
"""

import os
from datetime import datetime
from tavily import TavilyClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import AgentState
from agent.prompts import ROUTER_PROMPT, GENERATOR_PROMPT, GUARDRAIL_RESPONSE


# ── Lazy-initialized clients ────────────────────
_llm = None
_tavily_client = None


def get_llm():
    """Get or create the Gemini LLM instance (lazy init)."""
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.3,
        )
    return _llm


def get_tavily():
    """Get or create the Tavily client instance (lazy init)."""
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    return _tavily_client


# ── Node: Route Query ─────────────────────────
def route_query(state: AgentState) -> dict:
    """Classify the user query as 'mul_related' or 'off_topic' using the LLM.
    
    Includes conversation history so follow-up questions are recognized properly.
    """
    # Extract the latest user message
    messages = state.get("messages", [])
    query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break

    if not query:
        return {"query": "", "route": "off_topic"}

    # Build chat history for context (last 6 messages before the current one)
    chat_history_parts = []
    history_messages = messages[:-1]  # exclude current message
    recent = history_messages[-6:] if len(history_messages) > 6 else history_messages
    for msg in recent:
        if isinstance(msg, HumanMessage):
            chat_history_parts.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            # Truncate long AI responses for the router
            content = msg.content[:150] + "..." if len(msg.content) > 150 else msg.content
            chat_history_parts.append(f"Assistant: {content}")
    chat_history = "\n".join(chat_history_parts) if chat_history_parts else "No previous conversation."

    # Ask LLM to classify with conversation context
    prompt = ROUTER_PROMPT.format(query=query, chat_history=chat_history)
    response = get_llm().invoke([HumanMessage(content=prompt)])
    route = response.content.strip().lower()

    # Normalize the response
    if "mul_related" in route:
        route = "mul_related"
    elif "conversational" in route:
        route = "conversational"
    else:
        route = "off_topic"

    return {"query": query, "route": route, "search_results": ""}


# ── Node: Web Search ──────────────────────────
def web_search(state: AgentState) -> dict:
    """Search the MUL official website using Tavily API.
    
    Restricted to mul.edu.pk domain only — no external results.
    """
    query = state.get("query", "")

    current_year = datetime.now().year

    # distinct logic for program/fee queries vs general queries
    programs_keywords = ["fee", "tuition", "program", "course", "degree", "bs", "ms", "mphil", "phd", "admission", "details", "structure"]
    is_program_query = any(k in query.lower() for k in programs_keywords)

    try:
        if is_program_query:
            # Target program pages specifically — NO year bias (static pages)
            search_query = f"site:mul.edu.pk/en/program/ {query}"
        else:
            # General queries — include current year for recency bias
            search_query = f"Minhaj University Lahore {query} {current_year}"

        results = get_tavily().search(
            query=search_query,
            search_depth="advanced",
            include_domains=["mul.edu.pk"],
            max_results=7,
        )

        # Format search results — include publication date if available
        formatted_results = []
        for i, result in enumerate(results.get("results", []), 1):
            title = result.get("title", "No title")
            content = result.get("content", "No content")
            url = result.get("url", "")
            published = result.get("published_date", "")
            date_str = f"Published: {published}\n" if published else ""
            formatted_results.append(
                f"**Source {i}: {title}**\n"
                f"URL: {url}\n"
                f"{date_str}"
                f"Content: {content}\n"
            )

        search_text = "\n---\n".join(formatted_results) if formatted_results else "No results found from mul.edu.pk"

    except Exception as e:
        print(f"Tavily search error: {e}")
        search_text = "Search temporarily unavailable. Please visit https://mul.edu.pk directly for the latest information."

    return {"search_results": search_text}


# ── Node: Generate Response ───────────────────
def generate(state: AgentState) -> dict:
    """Generate the final response using search results and conversation history."""
    query = state.get("query", "")
    route = state.get("route", "mul_related")
    search_results = state.get("search_results", "")
    messages = state.get("messages", [])

    # If conversational/memory-based, allow answering without search results
    if route == "conversational":
        search_results = "No external search performed. Answer based on Conversation History."

    # Build chat history string from previous messages (last 10 messages)
    chat_history_parts = []
    recent_messages = messages[-10:] if len(messages) > 10 else messages
    for msg in recent_messages:
        if isinstance(msg, HumanMessage):
            chat_history_parts.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            chat_history_parts.append(f"Assistant: {msg.content}")
    chat_history = "\n".join(chat_history_parts) if chat_history_parts else "No previous conversation."

    # Generate response
    prompt = GENERATOR_PROMPT.format(
        search_results=search_results,
        chat_history=chat_history,
        query=query,
    )
    response = get_llm().invoke([HumanMessage(content=prompt)])

    return {
        "response": response.content,
        "messages": [AIMessage(content=response.content)],
    }


# ── Node: Guardrail ───────────────────────────
def guardrail(state: AgentState) -> dict:
    """Return a polite refusal for off-topic queries."""
    return {
        "response": GUARDRAIL_RESPONSE,
        "messages": [AIMessage(content=GUARDRAIL_RESPONSE)],
    }

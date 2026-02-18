"""Agent state definition for the MUL chatbot LangGraph."""

from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State schema for the MUL chatbot agent graph.
    
    Attributes:
        messages: Conversation history with add_messages reducer for automatic merging.
        query: The current user query extracted from the latest message.
        route: Classification result - 'mul_related' or 'off_topic'.
        search_results: Raw search results from Tavily web search.
        response: The final generated response text.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    query: str
    route: str
    search_results: str
    response: str

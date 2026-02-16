from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Callable
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

def merge_dict(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to merge files dictionary"""
    if not left: left = {}
    if not right: right = {}
    return {**left, **right}


class AgentState(TypedDict):
    """Core state for the strict DeepAgents implementation."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: str
    todos: List[Dict[str, Any]]
    profile: Dict[str, Any]
    files: Annotated[Dict[str, str], merge_dict]


class AgentConfig(TypedDict):
    """Dependency injection for database operations."""
    fetch_user_context: Callable[[str], Dict[str, Any]]

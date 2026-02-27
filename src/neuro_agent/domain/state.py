from typing import TypedDict, Annotated, Sequence, List, Dict, Any, NotRequired, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

def file_reducer(left, right):
    if left is None: return right
    if right is None: return left
    return {**left, **right}

def log_reducer(left, right):
    if left is None: return right or []
    if right is None: return left
    return left + right

class Todo(TypedDict):
    content: str
    status: Literal["pending", "in_progress", "completed"]

class ExecutionEntry(TypedDict):
    timestamp: str
    node: str
    tool_name: str
    todo_ref: int
    status: Literal["success", "error", "skipped"]

class AgentState(TypedDict):
    """
    Strict Domain State.
    Holds conversation history and context loaded from Blackboard.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: str
    todos: list[Todo]  # Overwrite semantics (matches deep_agents pattern)
    profile: Dict[str, Any]
    files: Annotated[NotRequired[dict[str, str]], file_reducer]
    execution_log: Annotated[NotRequired[list[ExecutionEntry]], log_reducer]

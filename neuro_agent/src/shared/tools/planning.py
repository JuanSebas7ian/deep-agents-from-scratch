from datetime import datetime
from typing import List, Annotated, Optional
from langchain_core.tools import tool
from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from langchain_core.messages import ToolMessage
from neuro_agent.src.shared.state import AgentState

from langchain_core.tools import tool, InjectedToolCallId
# ...
@tool
def write_todos(
    todos: List[dict], 
    state: Annotated[Optional[dict], InjectedState] = None,
    tool_call_id: Annotated[Optional[str], InjectedToolCallId] = None
) -> Command:
    """
    Update the TODO list. 
    IMPORTANT: This overwrites the entire list. To add/update, the model must include ALL desired items in the 'todos' argument.
    Each todo should be a dict: {"content": "...", "status": "pending"|"in_progress"|"completed"}
    """
    if state is None or tool_call_id is None:
        return Command(update={"messages": [ToolMessage("Error: Missing injected arguments", tool_call_id="")]})
    
    return Command(
        update={
            "todos": todos,
            "messages": [
                ToolMessage(f"Updated TODO list (Total items: {len(todos)}).", tool_call_id=tool_call_id)
            ]
        }
    )

@tool
def read_todos(state: Annotated[Optional[dict], InjectedState] = None) -> str:
    """Read the current TODO list."""
    if state is None:
        return "Error: State not injected"
    todos = state.get("todos", [])
    if not todos:
        return "No TODOs found."
    
    formatted_todos = []
    for todo in todos:
        content = todo.get("content", str(todo))
        status = todo.get("status", "pending")
        icon = "✅" if status == "completed" else "⏳"
        formatted_todos.append(f"{icon} {content}")
        
    return "\n".join(formatted_todos)

@tool
def think_tool(reflection: str) -> str:
    """Record a strategic reflection."""
    return f"Reflection recorded: {reflection}"

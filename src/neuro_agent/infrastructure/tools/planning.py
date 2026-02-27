"""TODO management tools for neuro_agent.

Mirrors deep_agents_from_scratch/todo_tools.py.
"""

from typing import List, Annotated, Optional

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from neuro_agent.domain.state import AgentState, Todo
from neuro_agent.infrastructure.prompts import WRITE_TODOS_DESCRIPTION


@tool(description=WRITE_TODOS_DESCRIPTION, parse_docstring=True)
def write_todos(
    todos: List[Todo],
    state: Annotated[Optional[dict], InjectedState] = None,
    tool_call_id: Annotated[Optional[str], InjectedToolCallId] = None,
) -> Command:
    """Update the TODO list (overwrites the entire list).

    Args:
        todos: List of Todo items with content and status fields
        state: Injected agent state
        tool_call_id: Injected tool call identifier

    Returns:
        Command updating state with new TODO list
    """
    if state is None or tool_call_id is None:
        return Command(update={"messages": [ToolMessage("Error: Missing injected arguments", tool_call_id="")]})

    return Command(
        update={
            "todos": todos,
            "messages": [
                ToolMessage(f"Updated TODO list (Total items: {len(todos)}).", tool_call_id=tool_call_id)
            ],
        }
    )


@tool(parse_docstring=True)
def read_todos(
    state: Annotated[Optional[dict], InjectedState] = None,
    tool_call_id: Annotated[Optional[str], InjectedToolCallId] = None,
) -> str:
    """Read the current TODO list.

    Args:
        state: Injected agent state
        tool_call_id: Injected tool call identifier

    Returns:
        Formatted TODO list string
    """
    if state is None:
        return "Error: State not injected"
    todos = state.get("todos", [])
    if not todos:
        return "No TODOs found."

    formatted_todos = []
    for i, todo in enumerate(todos, 1):
        content = todo.get("content", str(todo))
        status = todo.get("status", "pending")
        status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}
        icon = status_emoji.get(status, "❓")
        formatted_todos.append(f"{i}. {icon} {content} ({status})")

    return "\n".join(formatted_todos)


@tool
def think_tool(reflection: str) -> str:
    """Record a strategic reflection or thought process.

    Use this between searches to analyze findings, assess gaps,
    and plan next steps.

    Args:
        reflection: Your detailed reflection or thought process
    """
    return f"Reflection recorded: {reflection}"

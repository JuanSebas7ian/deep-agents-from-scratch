import os
from typing import Annotated, Optional
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from neuro_agent.src.shared.state import AgentState

@tool
def ls(state: Annotated[Optional[dict], InjectedState] = None) -> list[str]:
    """List all files in the virtual filesystem."""
    if state is None:
        return []
    return list(state.get("files", {}).keys())

@tool
def read_file(
    file_path: str,
    state: Annotated[Optional[dict], InjectedState] = None,
    offset: int = 0,
    limit: int = 2000,
) -> str:
    """Read file content from virtual filesystem with optional offset and limit."""
    if state is None:
        return "Error: State not injected"
    files = state.get("files", {})
    if file_path not in files:
        return f"Error: File '{file_path}' not found"

    content = files[file_path]
    if not content:
        return "System reminder: File exists but has empty contents"

    lines = content.splitlines()
    start_idx = offset
    end_idx = min(start_idx + limit, len(lines))

    if start_idx >= len(lines):
        return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"

    result_lines = []
    for i in range(start_idx, end_idx):
        line_content = lines[i][:2000]
        result_lines.append(f"{i + 1:6d}\t{line_content}")

    return "\n".join(result_lines)

@tool
def write_file(
    file_path: str,
    content: str,
    state: Annotated[Optional[dict], InjectedState] = None,
    tool_call_id: Annotated[Optional[str], InjectedToolCallId] = None,
) -> Command:
    """Write content to a file in the virtual filesystem."""
    if state is None or tool_call_id is None:
        return Command(update={"messages": [ToolMessage("Error: Missing injected arguments", tool_call_id="")]})
    
    files = state.get("files", {}).copy() # Use copy to ensure update triggers
    files[file_path] = content
    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(f"Updated file {file_path}", tool_call_id=tool_call_id)
            ],
        }
    )

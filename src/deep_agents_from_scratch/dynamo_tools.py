"""DynamoDB-backed artifact tools for persistent TODOs and Files.

These tools replace the in-memory virtual filesystem and TODO list
with DynamoDB persistence, enabling long-term state across sessions.

DynamoDB Table Schema (DeepAgents_Artifact):
    thread_id (String, PK): Session/thread identifier
    artifact_id (String, SK): Artifact key, prefixed by type:
        - FILE#<path>   — Virtual file content
        - TODO#LIST     — Complete TODO list as JSON

Requires AWS credentials configured (via .env or IAM role).
"""

import json
import time
from typing import Annotated, Literal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from deep_agents_from_scratch.state import DeepAgentState, Todo


# ─── DynamoDB Client ─── #

_dynamo_resource = None
_artifacts_table = None


def _get_artifacts_table(
    table_name: str = "DeepAgents_Artifact",
    region_name: str = "us-east-1",
):
    """Get or create a singleton DynamoDB table reference."""
    global _dynamo_resource, _artifacts_table
    if _artifacts_table is None:
        _dynamo_resource = boto3.resource("dynamodb", region_name=region_name)
        _artifacts_table = _dynamo_resource.Table(table_name)
    return _artifacts_table


def _get_thread_id(state: dict) -> str:
    """Extract thread_id from the agent state's configurable."""
    # thread_id is typically injected via config
    return state.get("thread_id", "default_thread")


# ─── TODO Tools (DynamoDB) ─── #

@tool(parse_docstring=True)
def dynamo_write_todos(
    todos: list[Todo],
    thread_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Write the TODO list to persistent DynamoDB storage.

    This persists your task list across sessions and agent restarts.
    Always send the FULL updated list — this replaces the entire TODO list.

    Args:
        todos: Complete list of Todo items with content and status
        thread_id: Thread/session identifier for persistence
        tool_call_id: Tool call identifier for message response

    Returns:
        Command updating agent state and persisting to DynamoDB
    """
    table = _get_artifacts_table()

    # Persist to DynamoDB
    table.put_item(
        Item={
            "thread_id": thread_id,
            "artifact_id": "TODO#LIST",
            "content": json.dumps(todos),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )

    return Command(
        update={
            "todos": todos,
            "messages": [
                ToolMessage(
                    f"✅ TODO list saved to DynamoDB ({len(todos)} items)",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


@tool(parse_docstring=True)
def dynamo_read_todos(
    thread_id: str,
    state: Annotated[DeepAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    """Read the TODO list from persistent DynamoDB storage.

    Retrieves the persisted TODO list for this thread/session.
    Falls back to in-memory state if DynamoDB read fails.

    Args:
        thread_id: Thread/session identifier
        state: Agent state (fallback if DynamoDB unavailable)
        tool_call_id: Tool call identifier

    Returns:
        Formatted TODO list string
    """
    table = _get_artifacts_table()

    try:
        response = table.get_item(
            Key={"thread_id": thread_id, "artifact_id": "TODO#LIST"}
        )
        if "Item" in response:
            todos = json.loads(response["Item"]["content"])
        else:
            todos = state.get("todos", [])
    except ClientError:
        # Fallback to in-memory state
        todos = state.get("todos", [])

    if not todos:
        return "No todos currently in the list."

    result = "Current TODO List:\n"
    for i, todo in enumerate(todos, 1):
        status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}
        emoji = status_emoji.get(todo["status"], "❓")
        result += f"{i}. {emoji} {todo['content']} ({todo['status']})\n"

    return result.strip()


# ─── File Tools (DynamoDB) ─── #

@tool(parse_docstring=True)
def dynamo_write_file(
    file_path: str,
    content: str,
    thread_id: str,
    state: Annotated[DeepAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Write a file to both in-memory state AND persistent DynamoDB storage.

    Files are stored with the key FILE#<path> in DynamoDB, enabling
    persistence across sessions while maintaining fast in-memory access.

    Args:
        file_path: Path for the file (e.g., "findings_mcp.md")
        content: File content to write
        thread_id: Thread/session identifier
        state: Agent state containing virtual filesystem
        tool_call_id: Tool call identifier

    Returns:
        Command updating both in-memory state and DynamoDB
    """
    table = _get_artifacts_table()

    # Persist to DynamoDB
    table.put_item(
        Item={
            "thread_id": thread_id,
            "artifact_id": f"FILE#{file_path}",
            "content": content,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )

    # Also update in-memory state
    files = state.get("files", {})
    files[file_path] = content

    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(
                    f"✅ File '{file_path}' saved to DynamoDB + memory",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


@tool(parse_docstring=True)
def dynamo_read_file(
    file_path: str,
    thread_id: str,
    state: Annotated[DeepAgentState, InjectedState],
    offset: int = 0,
    limit: int = 2000,
) -> str:
    """Read a file from DynamoDB (with in-memory fallback).

    First checks in-memory state, then falls back to DynamoDB for
    files from previous sessions.

    Args:
        file_path: Path to the file to read
        thread_id: Thread/session identifier
        state: Agent state containing virtual filesystem
        offset: Line number to start reading from
        limit: Maximum lines to read

    Returns:
        File content with line numbers, or error message
    """
    # Check in-memory first (faster)
    files = state.get("files", {})
    content = files.get(file_path)

    # Fallback to DynamoDB
    if content is None:
        table = _get_artifacts_table()
        try:
            response = table.get_item(
                Key={"thread_id": thread_id, "artifact_id": f"FILE#{file_path}"}
            )
            if "Item" in response:
                content = response["Item"]["content"]
            else:
                return f"Error: File '{file_path}' not found in memory or DynamoDB"
        except ClientError as e:
            return f"Error reading from DynamoDB: {e}"

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


@tool(parse_docstring=True)
def dynamo_ls(
    thread_id: str,
    state: Annotated[DeepAgentState, InjectedState],
) -> list[str]:
    """List all files from both in-memory state AND DynamoDB.

    Combines files currently in memory with files persisted in DynamoDB
    from previous sessions.

    Args:
        thread_id: Thread/session identifier
        state: Agent state containing virtual filesystem

    Returns:
        Combined list of file paths from memory and DynamoDB
    """
    # In-memory files
    memory_files = set(state.get("files", {}).keys())

    # DynamoDB files
    dynamo_files = set()
    table = _get_artifacts_table()
    try:
        response = table.query(
            KeyConditionExpression=(
                Key("thread_id").eq(thread_id)
                & Key("artifact_id").begins_with("FILE#")
            )
        )
        for item in response.get("Items", []):
            # Remove FILE# prefix
            path = item["artifact_id"][5:]  # len("FILE#") = 5
            dynamo_files.add(path)
    except ClientError:
        pass

    # Merge and sort
    all_files = sorted(memory_files | dynamo_files)
    if not all_files:
        return ["(no files)"]

    return all_files

"""DynamoDB-backed artifact tools for persistent TODOs and Files.

Mirrors deep_agents_from_scratch/dynamo_tools.py.

These tools replace the in-memory virtual filesystem and TODO list
with DynamoDB persistence, enabling long-term state across sessions.

DynamoDB Table Schema (DeepAgents_Artifact):
    PK: THREAD#{thread_id}
    SK: TODO              (for the TODO list)
        FILE#{path}       (for individual files)
    data: JSON content
"""

import json
from typing import Annotated

import boto3
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from neuro_agent.domain.state import AgentState, Todo


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
        import os
        _dynamo_resource = boto3.resource(
            "dynamodb",
            region_name=os.getenv("AWS_REGION", region_name),
        )
        _artifacts_table = _dynamo_resource.Table(
            os.getenv("DYNAMO_TABLE_ARTIFACTS", table_name)
        )
    return _artifacts_table


def _get_thread_id(state: dict):
    """Extract thread_id from the agent state's configurable."""
    return state.get("configurable", {}).get("thread_id", "default")


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
        todos: List of Todo items with content and status
        thread_id: Thread/session identifier
        tool_call_id: Tool call identifier for message response

    Returns:
        Command updating agent state and persisting to DynamoDB
    """
    try:
        table = _get_artifacts_table()
        table.put_item(Item={
            "PK": f"THREAD#{thread_id}",
            "SK": "TODO",
            "data": json.dumps([dict(t) for t in todos]),
        })
    except Exception as e:
        print(f"⚠️ DynamoDB write failed: {e}")

    return Command(
        update={
            "todos": todos,
            "messages": [
                ToolMessage(f"Updated todo list to {todos}", tool_call_id=tool_call_id)
            ],
        }
    )


@tool(parse_docstring=True)
def dynamo_read_todos(
    thread_id: str,
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    """Read the TODO list from persistent DynamoDB storage.

    Retrieves the persisted TODO list for this thread/session.
    Falls back to in-memory state if DynamoDB read fails.

    Args:
        thread_id: Thread/session identifier
        state: Agent state containing the current TODO list
        tool_call_id: Tool call identifier

    Returns:
        Formatted TODO list string
    """
    # Try DynamoDB first
    try:
        table = _get_artifacts_table()
        response = table.get_item(Key={
            "PK": f"THREAD#{thread_id}",
            "SK": "TODO",
        })
        if "Item" in response:
            todos = json.loads(response["Item"]["data"])
            if todos:
                result = "Current TODO List (from DynamoDB):\n"
                for i, todo in enumerate(todos, 1):
                    status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}
                    emoji = status_emoji.get(todo["status"], "❓")
                    result += f"{i}. {emoji} {todo['content']} ({todo['status']})\n"
                return result.strip()
    except Exception as e:
        print(f"⚠️ DynamoDB read failed, using in-memory: {e}")

    # Fallback to in-memory
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
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Write a file to both in-memory state AND persistent DynamoDB storage.

    Files are stored with the key FILE#<path> in DynamoDB, enabling
    persistence across sessions while maintaining fast in-memory access.

    Args:
        file_path: Path where the file should be created/updated
        content: Content to write to the file
        thread_id: Thread/session identifier
        state: Agent state containing virtual filesystem
        tool_call_id: Tool call identifier

    Returns:
        Command updating both in-memory state and DynamoDB
    """
    # Persist to DynamoDB
    try:
        table = _get_artifacts_table()
        table.put_item(Item={
            "PK": f"THREAD#{thread_id}",
            "SK": f"FILE#{file_path}",
            "data": content,
        })
    except Exception as e:
        print(f"⚠️ DynamoDB write failed: {e}")

    # Update in-memory state
    files = state.get("files", {}) or {}
    files[file_path] = content
    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(f"Updated file {file_path}", tool_call_id=tool_call_id)
            ],
        }
    )


@tool(parse_docstring=True)
def dynamo_read_file(
    file_path: str,
    thread_id: str,
    state: Annotated[AgentState, InjectedState],
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
    # Check in-memory first
    files = state.get("files", {}) or {}
    content = files.get(file_path)

    # Fallback to DynamoDB
    if content is None:
        try:
            table = _get_artifacts_table()
            response = table.get_item(Key={
                "PK": f"THREAD#{thread_id}",
                "SK": f"FILE#{file_path}",
            })
            if "Item" in response:
                content = response["Item"]["data"]
        except Exception as e:
            print(f"⚠️ DynamoDB read failed: {e}")

    if content is None:
        return f"Error: File '{file_path}' not found"

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
    state: Annotated[AgentState, InjectedState],
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
    files = state.get("files", {}) or {}
    all_paths = set(files.keys())

    # DynamoDB files
    try:
        table = _get_artifacts_table()
        from boto3.dynamodb.conditions import Key
        response = table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"THREAD#{thread_id}")
                & Key("SK").begins_with("FILE#")
            )
        )
        for item in response.get("Items", []):
            path = item["SK"].replace("FILE#", "", 1)
            all_paths.add(path)
    except Exception as e:
        print(f"⚠️ DynamoDB query failed: {e}")

    return sorted(all_paths) if all_paths else ["(no files)"]

"""Enhanced file system tools for deep agents.

This module adds edit_file, glob_files, and grep_files to the basic
virtual filesystem (ls, read_file, write_file), inspired by the
deepagents library's FilesystemMiddleware.
"""

import fnmatch
import re
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from deep_agents_from_scratch.state import DeepAgentState


EDIT_FILE_DESCRIPTION = """Edit a file by replacing an exact string match with new content.

This tool performs a find-and-replace operation on an existing file in the virtual filesystem.
You MUST read the file first before editing to know the exact content to replace.

Parameters:
- file_path (required): Path to the file to edit
- old_string (required): The exact string to find and replace. Must match exactly (including whitespace/indentation).
- new_string (required): The replacement string
- replace_all (optional, default=False): If True, replace ALL occurrences. If False, only replace the first one.

Important:
- The old_string must be UNIQUE in the file (unless replace_all=True), or the edit will fail.
- Always read the file first to get the exact content.
- Prefer editing over rewriting entire files."""

GLOB_DESCRIPTION = """Find files matching a glob pattern in the virtual filesystem.

Supports standard glob patterns:
- `*` matches any characters (except /)
- `**` matches any path segments
- `?` matches a single character

Examples:
- `*.py` — Find all Python files
- `findings_*.md` — Find all findings files
- `**/README*` — Find README files in any subdirectory

Parameters:
- pattern (required): Glob pattern to match against file paths

Returns a list of matching file paths."""

GREP_DESCRIPTION = """Search for a text pattern across files in the virtual filesystem.

Parameters:
- pattern (required): Text pattern to search for (literal string, not regex)
- file_glob (optional): Glob pattern to filter which files to search (e.g., "*.md")
- case_sensitive (optional, default=True): Whether the search is case-sensitive

Returns matching lines with file paths and line numbers."""


@tool(description=EDIT_FILE_DESCRIPTION, parse_docstring=True)
def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    state: Annotated[DeepAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    *,
    replace_all: bool = False,
) -> Command | str:
    """Edit a file by replacing an exact string.

    Args:
        file_path: Path to the file to edit
        old_string: Exact string to find
        new_string: Replacement string
        state: Agent state containing virtual filesystem
        tool_call_id: Tool call identifier
        replace_all: Whether to replace all occurrences

    Returns:
        Command with updated file or error message
    """
    files = state.get("files", {})
    if file_path not in files:
        return f"Error: File '{file_path}' not found"

    content = files[file_path]

    if old_string not in content:
        return f"Error: Could not find the specified text in '{file_path}'. Make sure you read the file first and use the exact text."

    # Count occurrences
    count = content.count(old_string)

    if count > 1 and not replace_all:
        return (
            f"Error: Found {count} occurrences of the text in '{file_path}'. "
            "Set replace_all=True to replace all, or provide more context to make the match unique."
        )

    if replace_all:
        new_content = content.replace(old_string, new_string)
        replaced = count
    else:
        new_content = content.replace(old_string, new_string, 1)
        replaced = 1

    files[file_path] = new_content
    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(
                    f"Successfully replaced {replaced} occurrence(s) in '{file_path}'",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


@tool(description=GLOB_DESCRIPTION, parse_docstring=True)
def glob_files(
    pattern: str,
    state: Annotated[DeepAgentState, InjectedState],
) -> list[str]:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern to match
        state: Agent state containing virtual filesystem

    Returns:
        List of matching file paths
    """
    files = state.get("files", {})
    matches = [path for path in files.keys() if fnmatch.fnmatch(path, pattern)]
    if not matches:
        return [f"No files matching pattern '{pattern}'"]
    return sorted(matches)


@tool(description=GREP_DESCRIPTION, parse_docstring=True)
def grep_files(
    pattern: str,
    state: Annotated[DeepAgentState, InjectedState],
    file_glob: str | None = None,
    case_sensitive: bool = True,
) -> str:
    """Search for text across files in the virtual filesystem.

    Args:
        pattern: Text to search for
        state: Agent state containing virtual filesystem
        file_glob: Optional glob to filter files
        case_sensitive: Whether search is case-sensitive

    Returns:
        Formatted search results with file paths and line numbers
    """
    files = state.get("files", {})
    results = []

    # Filter files by glob if specified
    search_files = files.items()
    if file_glob:
        search_files = [
            (path, content) for path, content in files.items()
            if fnmatch.fnmatch(path, file_glob)
        ]

    flags = 0 if case_sensitive else re.IGNORECASE

    for file_path, content in search_files:
        if not isinstance(content, str):
            continue
        lines = content.splitlines()
        for line_num, line in enumerate(lines, 1):
            if re.search(re.escape(pattern), line, flags):
                results.append(f"{file_path}:{line_num}: {line.strip()}")

    if not results:
        return f"No matches found for '{pattern}'"

    # Limit output
    if len(results) > 50:
        return "\n".join(results[:50]) + f"\n... and {len(results) - 50} more matches"
    return "\n".join(results)

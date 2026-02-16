"""Tools for NeuroAgent (Strict Architecture).

This module consolidates all tools required to replicate Notebook 4 functionality
within the NeuroAgent architecture (Search, Files, Todos, Thinking).
"""
import os
from datetime import datetime
import httpx
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolArg, InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from markdownify import markdownify
from tavily import TavilyClient
from typing_extensions import Annotated, Literal

# --- AWS Bedrock Integration (Retained for future use/compatibility) ---
from langchain_aws import ChatBedrockConverse

# IMPORTANTE: Usamos el estado de NeuroAgent
from neuro_agent.src.state import AgentState 

tavily_client = TavilyClient()

# --- Shared Utilities ---
def get_today_str() -> str:
    """Get current date in a human-readable format."""
    return datetime.now().strftime("%a %b %-d, %Y")

# --- FILE TOOLS ---
@tool
def ls(state: Annotated[dict, InjectedState]) -> str:
    """List all files in the agent's context."""
    files = state.get("files", {})
    if not files:
        return "No files in context."
    return "\n".join(files.keys())

@tool
def read_file(filename: str, state: Annotated[dict, InjectedState]) -> str:
    """Read the content of a file from the agent's context."""
    files = state.get("files", {})
    if filename not in files:
        return f"File '{filename}' not found."
    return files[filename]

@tool
def write_file(
    filename: str, 
    content: str, 
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Write content to a virtual file in the agent's context. 
    Use this to save research notes, drafts, or full tool outputs.
    """
    files = state.get("files", {})
    if files is None: files = {}
    files[filename] = content
    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(f"File '{filename}' saved.", tool_call_id=tool_call_id)
            ]
        }
    )

# --- TODO TOOLS ---
@tool
def read_todos(state: Annotated[dict, InjectedState]) -> str:
    """Read the current TODO list."""
    todos = state.get("todos", [])
    if not todos:
        return "No TODOs found."
    
    # Format clearly like Nb4
    output = []
    for i, todo in enumerate(todos):
        status = "[x]" if todo.get("completed") else "[ ]"
        output.append(f"{i+1}. {status} {todo['task']}")
    return "\n".join(output)

@tool
def write_todos(
    todos: list[str], 
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Overwrite the TODO list with a new list of tasks."""
    # Convert list of strings to list of dicts for safety/extensibility
    new_todos = [{"task": t, "completed": False} for t in todos]
    
    return Command(
        update={
            "todos": new_todos,
            "messages": [
                ToolMessage(f"Updated TODO list with {len(new_todos)} items.", tool_call_id=tool_call_id)
            ]
        }
    )

# --- THINKING TOOL ---
@tool
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making."""
    return f"Reflection recorded: {reflection}"

# --- SEARCH & WEB TOOLS (AGNOSTIC) ---

@tool
def tavily_search(
    query: str,
    max_results: int = 3,
    topic: Literal["general", "news", "finance"] = "general",
) -> str:
    """
    Perform a web search using Tavily. 
    Returns a list of results with Title, URL, and a short content snippet.
    Does NOT save files. Use 'scrape_webpage' and 'write_file' for that.
    """
    try:
        results = tavily_client.search(
            query,
            max_results=max_results,
            topic=topic,
            include_raw_content=False # We only want snippets for the initial search
        )
        
        output = []
        output.append(f"Search Results for '{query}' ({get_today_str()}):")
        
        for result in results.get('results', []):
            title = result.get('title', 'No Title')
            url = result.get('url', '#')
            content = result.get('content', '')[:300].replace('\n', ' ') # Snippet only
            output.append(f"- [{title}]({url}): {content}...")
            
        output.append("\nTip: Use 'scrape_webpage(url)' to read the full content of a promising result.")
        return "\n".join(output)
        
    except Exception as e:
        return f"Search Error: {str(e)}"

@tool
def scrape_webpage(url: str) -> str:
    """
    Fetch and convert a webpage to Markdown. 
    Use this to read the full content of a URL found via search.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()
            
            # Basic markdown conversion
            markdown_content = markdownify(response.text)
            
            # Truncate if too huge (safety mechanism)
            if len(markdown_content) > 50000:
                markdown_content = markdown_content[:50000] + "\n\n[Content Truncated]"
                
            return f"URL: {url}\n\n{markdown_content}"
            
    except Exception as e:
        return f"Scrape Error for {url}: {str(e)}"

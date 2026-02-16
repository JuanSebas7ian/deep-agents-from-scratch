"""Tools for NeuroAgent (Strict Architecture).

This module consolidates all tools required to replicate Notebook 4 functionality
within the NeuroAgent architecture (Search, Files, Todos, Thinking).
"""
import os
from datetime import datetime
import uuid, base64

import httpx
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import InjectedToolArg, InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from markdownify import markdownify
from pydantic import BaseModel, Field
from tavily import TavilyClient
from typing_extensions import Annotated, Literal

# --- AWS Bedrock Integration ---
from langchain_aws import ChatBedrockConverse
import langchain_aws.chat_models.bedrock_converse as bc

# Configuración de Modelos (Igual que NB4)
llm_nova_lite = ChatBedrockConverse(model="us.amazon.nova-lite-v1:0", region_name="us-east-1", temperature=0.0)
summarization_model = llm_nova_lite

# IMPORTANTE: Usamos el estado de NeuroAgent
from neuro_agent.src.state import AgentState 

tavily_client = TavilyClient()

# --- Shared Utilities ---
def get_today_str() -> str:
    """Get current date in a human-readable format."""
    return datetime.now().strftime("%a %b %-d, %Y")

# --- FILE TOOLS ---
@tool
def ls(state: Annotated[AgentState, InjectedState]) -> str:
    """List all files in the agent's context."""
    files = state.get("files", {})
    if not files:
        return "No files in context."
    return "\n".join(files.keys())

@tool
def read_file(filename: str, state: Annotated[AgentState, InjectedState]) -> str:
    """Read the content of a file from the agent's context."""
    files = state.get("files", {})
    if filename not in files:
        return f"File '{filename}' not found."
    return files[filename]

@tool
def write_file(filename: str, content: str, state: Annotated[AgentState, InjectedState]) -> Command:
    """Write content to a file in the agent's context."""
    files = state.get("files", {})
    files[filename] = content
    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(f"File '{filename}' written successfully.", tool_call_id=tool_call_id) # Need tool_call_id
            ]
        }
    )
# Fix for write_file tool_call_id
@tool
def write_file(
    filename: str, 
    content: str, 
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Write content to a file in the agent's context."""
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
def read_todos(state: Annotated[AgentState, InjectedState]) -> str:
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
    state: Annotated[AgentState, InjectedState],
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

# --- SEARCH TOOLS ---
SUMMARIZE_WEB_SEARCH = """
You are a research assistant. Summarize the following webpage content.
Date: {date}
Content:
{webpage_content}
"""

class Summary(BaseModel):
    """Schema for webpage content summarization."""
    filename: str = Field(description="Name of the file to store.")
    summary: str = Field(description="Key learnings from the webpage.")

def run_tavily_search(
    search_query: str, 
    max_results: int = 1, 
    topic: Literal["general", "news", "finance"] = "general", 
    include_raw_content: bool = True, 
) -> dict:
    """Perform search using Tavily API for a single query."""
    result = tavily_client.search(
        search_query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic
    )
    return result

def summarize_webpage_content(webpage_content: str) -> Summary:
    """Summarize webpage content using the configured summarization model."""
    try:
        structured_model = summarization_model.with_structured_output(Summary)
        summary_and_filename = structured_model.invoke([
            HumanMessage(content=SUMMARIZE_WEB_SEARCH.format(
                webpage_content=webpage_content[:20000], 
                date=get_today_str()
            ))
        ])
        return summary_and_filename
    except Exception:
        return Summary(
            filename="search_result.md",
            summary=webpage_content[:1000] + "..." if len(webpage_content) > 1000 else webpage_content
        )


def process_search_results(results: dict) -> list[dict]:
    """Process search results by summarizing content where available."""
    processed_results = []
    HTTPX_CLIENT = httpx.Client(timeout=30.0)

    for result in results.get('results', []):
        url = result['url']
        try:
            if not result.get('raw_content'):
                response = HTTPX_CLIENT.get(url)
                if response.status_code == 200:
                    raw_content = markdownify(response.text)
                else:
                    raw_content = result.get('content', '')
            else:
                 raw_content = result.get('raw_content', '')
            
            summary_obj = summarize_webpage_content(raw_content)

        except (httpx.TimeoutException, httpx.RequestError, Exception):
            raw_content = result.get('content', '')
            summary_obj = Summary(
                filename="error.md",
                summary="Error processing content."
            )

        uid = base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode("ascii")[:8]
        name, ext = os.path.splitext(summary_obj.filename)
        summary_obj.filename = f"{name}_{uid}{ext}"

        processed_results.append({
            'url': result['url'],
            'title': result['title'],
            'summary': summary_obj.summary,
            'filename': summary_obj.filename,
            'raw_content': raw_content,
        })

    return processed_results


@tool
def tavily_search(
    query: str,
    state: Annotated[AgentState, InjectedState], 
    tool_call_id: Annotated[str, InjectedToolCallId],
    max_results: Annotated[int, InjectedToolArg] = 1,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
) -> Command:
    """Search web and save detailed results to files while returning minimal context."""
    search_results = run_tavily_search(
        query,
        max_results=max_results,
        topic=topic,
        include_raw_content=True,
    ) 

    processed_results = process_search_results(search_results)
    
    files = state.get("files", {})
    if files is None: files = {}
    
    saved_files = []
    summaries = []
    
    for i, result in enumerate(processed_results):
        filename = result['filename']
        
        file_content = f"# Search Result: {result['title']}\n\n**URL:** {result['url']}\n**Query:** {query}\n**Date:** {get_today_str()}\n\n## Summary\n{result['summary']}\n\n## Raw Content\n{result.get('raw_content', 'No raw content available')}\n"

        
        files[filename] = file_content
        saved_files.append(filename)
        summaries.append(f"- {filename}: {result['summary']}...")
    
    summary_text = f"🔍 Found {len(processed_results)} result(s) for '{query}':\n\n" + chr(10).join(summaries) + f"\n\nFiles: {', '.join(saved_files)}\n💡 Use read_file() to access full details when needed."


    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(summary_text, tool_call_id=tool_call_id)
            ],
        }
    )

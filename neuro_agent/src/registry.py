from typing import Dict, Any
from .adapters.lambda_invoker import invoke_executor_lambda
from .tools import (
    tavily_search, 
    ls, 
    read_file, 
    write_file, 
    read_todos, 
    write_todos, 
    think_tool
)


"""
Subagent Registry (Hexagonal Architecture):
Centralized configuration. The Supervisor doesn't know these run in Lambdas.
It just knows to build a tool from the schema and run the 'runner' function.
"""

SUBAGENTS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "delegate_to_executor": {
        "description": "Call this to delegate DB operations. Break down complex tasks before calling this.",
        "schema": {
            "type": "object",
            "properties": {
                "explicit_instructions": {
                    "type": "string",
                    "description": "Exact, atomic instructions for the subagent. Example: 'Write these 3 tasks to DB...'"
                }
            },
            "required": ["explicit_instructions"]
        },
        "runner": invoke_executor_lambda # Map to the network adapter!
    },
    "tavily_search": {
        "description": "Perform a web search using Tavily to gather information on current events, technical topics, or general knowledge.",
        "schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query."
                }
            },
            "required": ["query"]
        },
        "runner": lambda query: tavily_search.invoke({"query": query}) # Local tool runner
    },
    "ls": {
        "description": "List all files in the agent's context.",
        "schema": {"type": "object", "properties": {}}, # No params
        "runner": lambda: ls.invoke({})
    },
    "read_file": {
        "description": "Read the content of a file from the agent's context.",
        "schema": {
            "type": "object", 
            "properties": {"filename": {"type": "string"}},
            "required": ["filename"]
        },
        "runner": lambda filename: read_file.invoke({"filename": filename})
    },
    "write_file": {
        "description": "Write content to a file in the agent's context.",
        "schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["filename", "content"]
        },
        "runner": lambda filename, content: write_file.invoke({"filename": filename, "content": content})
    },
    "read_todos": {
        "description": "Read the current TODO list.",
        "schema": {"type": "object", "properties": {}},
        "runner": lambda: read_todos.invoke({})
    },
    "write_todos": {
        "description": "Overwrite the TODO list with a new list of tasks.",
        "schema": {
            "type": "object",
            "properties": {
                "todos": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["todos"]
        },
        "runner": lambda todos: write_todos.invoke({"todos": todos})
    },
    "think_tool": {
        "description": "Strategic reflection tool.",
        "schema": {
            "type": "object",
            "properties": {
                "reflection": {"type": "string"}
            },
            "required": ["reflection"]
        },
        "runner": lambda reflection: think_tool.invoke({"reflection": reflection})
    }
}

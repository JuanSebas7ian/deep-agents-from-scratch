"""Neuro Agent Tools Package.

Exports all tools for use in agent construction.
"""

# Core tools (deep_agents mirror)
from .web import tavily_search, scrape_webpage, read_page
from .database import save_task, get_context
from .delegation import delegate_task
from .planning import write_todos, read_todos, think_tool
from .filesystem import ls, read_file, write_file
from .time import get_today_str

# DynamoDB artifact tools (deep_agents mirror)
from .dynamo_artifacts import (
    dynamo_write_todos,
    dynamo_read_todos,
    dynamo_write_file,
    dynamo_read_file,
    dynamo_ls,
)

# Enhanced filesystem (deep_agents mirror)
from .enhanced_filesystem import edit_file, glob_files, grep_files

# Neurodivergent activity tools (neuro_agent extension)
from .neuro_tools import (
    schedule_activity,
    get_daily_schedule,
    complete_activity,
    energy_check,
    suggest_next,
    daily_summary,
)

__all__ = [
    # Web & Research
    "tavily_search",
    "scrape_webpage",
    "read_page",
    # Database
    "save_task",
    "get_context",
    # Delegation
    "delegate_task",
    # Planning / TODOs
    "write_todos",
    "read_todos",
    "think_tool",
    # Filesystem
    "ls",
    "read_file",
    "write_file",
    # DynamoDB Artifacts
    "dynamo_write_todos",
    "dynamo_read_todos",
    "dynamo_write_file",
    "dynamo_read_file",
    "dynamo_ls",
    # Enhanced Filesystem
    "edit_file",
    "glob_files",
    "grep_files",
    # Neuro Tools
    "schedule_activity",
    "get_daily_schedule",
    "complete_activity",
    "energy_check",
    "suggest_next",
    "daily_summary",
    # Utility
    "get_today_str",
]

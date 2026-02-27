import os
from neuro_agent.domain.registry import ToolRegistry
from neuro_agent.infrastructure.tools import (
    tavily_search, read_page, delegate_task,
    write_todos, read_todos, think_tool,
    ls, read_file, write_file,
    dynamo_write_todos, dynamo_read_todos,
    dynamo_write_file, dynamo_read_file, dynamo_ls,
    edit_file, glob_files, grep_files,
    schedule_activity, get_daily_schedule, complete_activity,
    energy_check, suggest_next, daily_summary,
)


def bootstrap_tool_registry() -> ToolRegistry:
    """
    FACTORY: Wires the agent capabilities based on environment.
    This is the Single Source of Truth for tool configuration.
    """
    registry = ToolRegistry()

    # Web tools
    registry.register("web_search", "Search internet info",
                      {"type": "object", "properties": {"query": {"type": "string"}}},
                      tavily_search)

    registry.register("web_read", "Read URL content",
                      {"type": "object", "properties": {"url": {"type": "string"}}},
                      read_page)

    # Planning tools
    registry.register("write_todos", "Create/update TODO plan",
                      {"type": "object", "properties": {"todos": {"type": "array"}}},
                      write_todos)
    registry.register("read_todos", "Read current TODO plan",
                      {"type": "object", "properties": {}},
                      read_todos)
    registry.register("think_tool", "Record strategic reflection",
                      {"type": "object", "properties": {"reflection": {"type": "string"}}},
                      think_tool)

    # Filesystem tools
    registry.register("ls", "List virtual files",
                      {"type": "object", "properties": {}}, ls)
    registry.register("read_file", "Read virtual file",
                      {"type": "object", "properties": {"file_path": {"type": "string"}}},
                      read_file)
    registry.register("write_file", "Write virtual file",
                      {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}}},
                      write_file)

    # Enhanced filesystem tools
    registry.register("edit_file", "Edit file via find-and-replace",
                      {"type": "object", "properties": {"file_path": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}}},
                      edit_file)
    registry.register("glob_files", "Find files by pattern",
                      {"type": "object", "properties": {"pattern": {"type": "string"}}},
                      glob_files)
    registry.register("grep_files", "Search text across files",
                      {"type": "object", "properties": {"pattern": {"type": "string"}}},
                      grep_files)

    # DynamoDB artifact tools
    registry.register("dynamo_write_todos", "Persist TODOs to DynamoDB",
                      {"type": "object", "properties": {"todos": {"type": "array"}, "thread_id": {"type": "string"}}},
                      dynamo_write_todos)
    registry.register("dynamo_read_todos", "Read TODOs from DynamoDB",
                      {"type": "object", "properties": {"thread_id": {"type": "string"}}},
                      dynamo_read_todos)
    registry.register("dynamo_write_file", "Persist file to DynamoDB",
                      {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}, "thread_id": {"type": "string"}}},
                      dynamo_write_file)
    registry.register("dynamo_read_file", "Read file from DynamoDB",
                      {"type": "object", "properties": {"file_path": {"type": "string"}, "thread_id": {"type": "string"}}},
                      dynamo_read_file)
    registry.register("dynamo_ls", "List files in DynamoDB",
                      {"type": "object", "properties": {"thread_id": {"type": "string"}}},
                      dynamo_ls)

    # Neurodivergent activity tools
    registry.register("schedule_activity", "Schedule a time-boxed activity",
                      {"type": "object", "properties": {"description": {"type": "string"}, "start_time": {"type": "string"}}},
                      schedule_activity)
    registry.register("get_daily_schedule", "View today's activity schedule",
                      {"type": "object", "properties": {"user_id": {"type": "string"}}},
                      get_daily_schedule)
    registry.register("complete_activity", "Mark an activity as done",
                      {"type": "object", "properties": {"activity_id": {"type": "string"}}},
                      complete_activity)
    registry.register("energy_check", "Log energy and mood level",
                      {"type": "object", "properties": {"energy_level": {"type": "integer"}}},
                      energy_check)
    registry.register("suggest_next", "Get energy-aware next activity suggestion",
                      {"type": "object", "properties": {"user_id": {"type": "string"}}},
                      suggest_next)
    registry.register("daily_summary", "End-of-day activity summary",
                      {"type": "object", "properties": {"user_id": {"type": "string"}}},
                      daily_summary)

    # Delegation
    if os.getenv("ENVIRONMENT") == "PRODUCTION":
        registry.register("delegate_worker", "Delegate execution",
                          {"type": "object", "properties": {"instructions": {"type": "string"}}},
                          delegate_task)
    else:
        registry.register("delegate_worker", "Delegate execution (DEV)",
                          {"type": "object", "properties": {"instructions": {"type": "string"}}},
                          delegate_task)

    return registry

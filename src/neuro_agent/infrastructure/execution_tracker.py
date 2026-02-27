"""Execution tracker for mandatory TODO plan enforcement.

Mirrors deep_agents_from_scratch/execution_tracker.py.

This module provides the audit infrastructure to ensure agents ALWAYS
follow their TODO plan. It compares planned steps against actual execution
and provides a guard function that blocks the agent from finishing until
all steps are completed.

Core philosophy: The TODO list is the execution contract. Follow the script.
"""

from datetime import datetime
from typing import Optional

from neuro_agent.domain.state import ExecutionEntry, Todo


# ─── Guard Function (Mandatory Enforcement) ─── #

def check_plan_complete(todos: list[Todo]) -> bool:
    """Check if ALL TODO items are marked as completed.

    This is the mandatory enforcement gate. The agent graph uses this
    to determine whether the agent is allowed to finish.

    Args:
        todos: List of Todo items from agent state

    Returns:
        True only if every TODO has status "completed"
    """
    if not todos:
        return False  # No plan = not complete

    return all(todo["status"] == "completed" for todo in todos)


# ─── Execution Report ─── #

def build_execution_report(
    todos: list[Todo],
    execution_log: list[ExecutionEntry],
) -> dict:
    """Build an audit report comparing the TODO plan against actual execution.

    Analyzes the execution log to determine which TODO steps were actually
    executed and which were skipped or had errors.

    Args:
        todos: The TODO plan (expected steps)
        execution_log: Log of actual tool/node executions

    Returns:
        Dict with report summary, step details, and coverage metrics
    """
    if not todos:
        return {
            "steps": [],
            "total": 0,
            "completed": 0,
            "skipped": 0,
            "errors": 0,
            "coverage_pct": 0,
        }

    # Collect all unique tool names called
    tools_called = [
        entry["tool_name"]
        for entry in execution_log
        if entry["tool_name"]
    ]

    # Build step-by-step report
    steps = []
    completed = 0
    skipped = 0
    errors = 0

    for i, todo in enumerate(todos):
        step = {
            "index": i + 1,
            "content": todo["content"],
            "status": todo["status"],
            "tool_match": None,
        }

        if todo["status"] == "completed":
            completed += 1
            # Try to find the matching tool call
            matching = [
                entry for entry in execution_log
                if entry.get("todo_ref") == i
            ]
            if matching:
                step["tool_match"] = matching[-1]["tool_name"]
        elif todo["status"] == "in_progress":
            skipped += 1
            step["flag"] = "⚠️  IN PROGRESS (not finished)"
        else:  # pending
            skipped += 1
            step["flag"] = "⚠️  SKIPPED (never started)"

        steps.append(step)

    total = len(todos)
    coverage = round((completed / total) * 100) if total > 0 else 0

    return {
        "steps": steps,
        "total": total,
        "completed": completed,
        "skipped": skipped,
        "errors": errors,
        "coverage_pct": coverage,
        "tools_called": tools_called,
    }


def format_execution_report(report: dict) -> str:
    """Format the execution report for display.

    Args:
        report: Report dict from build_execution_report

    Returns:
        Formatted string ready for printing
    """
    if report["total"] == 0:
        return "📊 No TODO plan was created."

    lines = [
        "",
        "📊 EXECUTION AUDIT",
        "═" * 50,
    ]

    for step in report["steps"]:
        if step["status"] == "completed":
            tool_info = f" → tool: {step['tool_match']}" if step["tool_match"] else ""
            lines.append(f"  ✅ Step {step['index']}: {step['content']}{tool_info}")
        else:
            flag = step.get("flag", "⚠️  UNKNOWN")
            lines.append(f"  {flag} Step {step['index']}: {step['content']}")

    lines.append("═" * 50)
    lines.append(
        f"  Coverage: {report['completed']}/{report['total']} steps "
        f"({report['coverage_pct']}%)"
    )

    if report["coverage_pct"] < 100:
        lines.append("  ⛔ INCOMPLETE EXECUTION — steps were skipped!")
    else:
        lines.append("  ✅ FULL COVERAGE — all steps executed")

    lines.append("")
    return "\n".join(lines)


def create_log_entry(
    node: str,
    tool_name: str = "",
    todo_ref: int = -1,
    status: str = "success",
) -> ExecutionEntry:
    """Create a standardized execution log entry.

    Args:
        node: Graph node name
        tool_name: Name of the tool called
        todo_ref: Index of the related TODO item
        status: Execution result

    Returns:
        ExecutionEntry dict
    """
    return ExecutionEntry(
        timestamp=datetime.now().isoformat(),
        node=node,
        tool_name=tool_name,
        todo_ref=todo_ref,
        status=status,
    )

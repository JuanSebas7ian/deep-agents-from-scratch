"""Neurodivergent activity scheduling tools backed by DynamoDB.

Uses @tool decorator + InjectedState / InjectedToolCallId + Command returns —
same tool pattern as every deep_agents tool.

DynamoDB Table: NeuroAgent_Activities
    PK: USER#{user_id}
    SK: ACTIVITY#{date}#{uuid} | ENERGY#{timestamp} | SUMMARY#{date}
"""

import json
import os
import uuid
from datetime import datetime, date
from typing import Annotated, Literal

import boto3
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from neuro_agent.domain.state import AgentState


# ─── DynamoDB Client ─── #

_activities_table = None


def _get_activities_table(
    table_name: str = "NeuroAgent_Activities",
    region_name: str = "us-east-1",
):
    """Get or create a singleton DynamoDB table reference."""
    global _activities_table
    if _activities_table is None:
        dynamodb = boto3.resource(
            "dynamodb",
            region_name=os.getenv("AWS_REGION", region_name),
        )
        _activities_table = dynamodb.Table(
            os.getenv("DYNAMO_TABLE_ACTIVITIES", table_name)
        )
    return _activities_table


# ─── Activity Tools ─── #

@tool(parse_docstring=True)
def schedule_activity(
    user_id: str,
    description: str,
    start_time: str,
    duration_minutes: int = 25,
    category: Literal["work", "creative", "rest"] = "work",
    energy_required: Literal["high", "medium", "low"] = "medium",
) -> str:
    """Schedule a time-boxed activity for the user.

    Creates a new activity with start time, duration, category, and energy level.
    Default is a 25-minute Pomodoro session.

    Args:
        user_id: User identifier
        description: What the activity involves
        start_time: Start time in HH:MM format (24h)
        duration_minutes: Duration in minutes (default 25 — Pomodoro)
        category: Activity type — work, creative, or rest
        energy_required: Energy level needed — high, medium, or low

    Returns:
        Confirmation message with activity ID
    """
    try:
        table = _get_activities_table()
        activity_id = str(uuid.uuid4())[:8]
        today = date.today().isoformat()

        category_emoji = {"work": "🟩", "creative": "🟦", "rest": "🟧"}
        emoji = category_emoji.get(category, "⬜")

        table.put_item(Item={
            "PK": f"USER#{user_id}",
            "SK": f"ACTIVITY#{today}#{activity_id}",
            "description": description,
            "start_time": start_time,
            "duration_minutes": duration_minutes,
            "category": category,
            "energy_required": energy_required,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        })

        return (
            f"{emoji} Activity scheduled (ID: {activity_id}):\n"
            f"  📝 {description}\n"
            f"  ⏰ {start_time} → {duration_minutes} min\n"
            f"  🏷️ {category} | Energy: {energy_required}"
        )
    except Exception as e:
        return f"Error scheduling activity: {e}"


@tool(parse_docstring=True)
def get_daily_schedule(user_id: str) -> str:
    """Retrieve today's activities sorted by time.

    Shows all scheduled activities with visual blocks for each category.

    Args:
        user_id: User identifier

    Returns:
        Formatted daily schedule with visual blocks
    """
    try:
        table = _get_activities_table()
        today = date.today().isoformat()

        from boto3.dynamodb.conditions import Key
        response = table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"USER#{user_id}")
                & Key("SK").begins_with(f"ACTIVITY#{today}")
            )
        )

        items = response.get("Items", [])
        if not items:
            return "📅 No activities scheduled for today. Use `schedule_activity` to plan your day."

        # Sort by start time
        items.sort(key=lambda x: x.get("start_time", "00:00"))

        category_emoji = {"work": "🟩", "creative": "🟦", "rest": "🟧"}
        status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}

        lines = [f"📅 Today's Schedule ({today}):", ""]
        for item in items:
            emoji = category_emoji.get(item.get("category", ""), "⬜")
            status = status_emoji.get(item.get("status", ""), "❓")
            energy = item.get("energy_required", "medium")
            lines.append(
                f"  {status} {emoji} {item['start_time']} | "
                f"{item['description']} ({item['duration_minutes']} min) "
                f"[{energy} energy]"
            )

        completed = sum(1 for i in items if i.get("status") == "completed")
        lines.append(f"\nProgress: {completed}/{len(items)} activities done")
        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching schedule: {e}"


@tool(parse_docstring=True)
def complete_activity(
    user_id: str,
    activity_id: str,
) -> str:
    """Mark an activity as completed.

    Args:
        user_id: User identifier
        activity_id: The 8-char activity ID

    Returns:
        Confirmation with suggestion for next activity
    """
    try:
        table = _get_activities_table()
        today = date.today().isoformat()

        table.update_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": f"ACTIVITY#{today}#{activity_id}",
            },
            UpdateExpression="SET #s = :s, completed_at = :t",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "completed",
                ":t": datetime.now().isoformat(),
            },
        )

        return (
            f"✅ Activity {activity_id} marked as completed!\n"
            "💡 Use `suggest_next` to see what to do next based on your energy."
        )
    except Exception as e:
        return f"Error completing activity: {e}"


@tool(parse_docstring=True)
def energy_check(
    user_id: str,
    energy_level: int,
    mood_note: str = "",
) -> str:
    """Log current energy and mood level.

    Helps track energy patterns throughout the day.
    If energy drops below 3, the agent will suggest rest or low-energy activities.

    Args:
        user_id: User identifier
        energy_level: Current energy 1-5 (1=exhausted, 5=peak)
        mood_note: Optional brief note about current mood

    Returns:
        Energy acknowledgment with adaptive suggestion
    """
    try:
        table = _get_activities_table()
        timestamp = datetime.now().isoformat()

        table.put_item(Item={
            "PK": f"USER#{user_id}",
            "SK": f"ENERGY#{timestamp}",
            "energy_level": energy_level,
            "mood_note": mood_note,
        })

        energy_emoji = {1: "🔋💤", 2: "🔋😐", 3: "🔋🙂", 4: "⚡😊", 5: "⚡🔥"}
        emoji = energy_emoji.get(energy_level, "🔋")

        response = f"{emoji} Energy logged: {energy_level}/5"
        if mood_note:
            response += f"\n📝 Mood: {mood_note}"

        if energy_level <= 2:
            response += (
                "\n\n💡 Low energy detected. Recommendations:\n"
                "  - 🟧 Take a 5-10 min rest break\n"
                "  - 🟦 Switch to a creative/low-effort task\n"
                "  - 🥤 Hydrate and have a snack"
            )
        elif energy_level >= 4:
            response += (
                "\n\n⚡ High energy! Perfect time for:\n"
                "  - 🟩 Complex work tasks\n"
                "  - Tasks you've been avoiding"
            )

        return response
    except Exception as e:
        return f"Error logging energy: {e}"


@tool(parse_docstring=True)
def suggest_next(user_id: str) -> str:
    """Suggest the next activity based on schedule and energy.

    Reads today's schedule and latest energy check to recommend
    the most appropriate next activity.

    Args:
        user_id: User identifier

    Returns:
        Energy-aware recommendation for next activity
    """
    try:
        table = _get_activities_table()
        today = date.today().isoformat()

        from boto3.dynamodb.conditions import Key

        # Get schedule
        schedule_response = table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"USER#{user_id}")
                & Key("SK").begins_with(f"ACTIVITY#{today}")
            )
        )
        activities = schedule_response.get("Items", [])

        # Get latest energy
        energy_response = table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"USER#{user_id}")
                & Key("SK").begins_with("ENERGY#")
            ),
            ScanIndexForward=False,
            Limit=1,
        )
        energy_items = energy_response.get("Items", [])
        current_energy = int(energy_items[0]["energy_level"]) if energy_items else 3

        # Find pending activities
        pending = [a for a in activities if a.get("status") == "pending"]
        if not pending:
            return "🎉 All activities for today are done! Great job.\nUse `daily_summary` to review your day."

        # Sort by energy match
        energy_map = {"high": 4, "medium": 3, "low": 2}
        pending.sort(
            key=lambda a: abs(energy_map.get(a.get("energy_required", "medium"), 3) - current_energy)
        )

        best = pending[0]
        category_emoji = {"work": "🟩", "creative": "🟦", "rest": "🟧"}
        emoji = category_emoji.get(best.get("category", ""), "⬜")

        return (
            f"💡 Suggested next activity (based on energy={current_energy}/5):\n\n"
            f"  {emoji} {best['description']}\n"
            f"  ⏰ {best.get('start_time', 'flexible')} | {best.get('duration_minutes', 25)} min\n"
            f"  🏷️ {best.get('category', 'work')} | Energy: {best.get('energy_required', 'medium')}\n\n"
            f"({len(pending) - 1} more activities remaining today)"
        )
    except Exception as e:
        return f"Error generating suggestion: {e}"


@tool(parse_docstring=True)
def daily_summary(user_id: str) -> str:
    """Generate end-of-day summary of activities.

    Shows what was planned vs completed, with patterns and streaks.

    Args:
        user_id: User identifier

    Returns:
        Formatted daily summary report
    """
    try:
        table = _get_activities_table()
        today = date.today().isoformat()

        from boto3.dynamodb.conditions import Key
        response = table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"USER#{user_id}")
                & Key("SK").begins_with(f"ACTIVITY#{today}")
            )
        )
        activities = response.get("Items", [])

        if not activities:
            return "📊 No activities were scheduled today."

        completed = [a for a in activities if a.get("status") == "completed"]
        pending = [a for a in activities if a.get("status") != "completed"]
        total_planned_min = sum(a.get("duration_minutes", 0) for a in activities)
        total_done_min = sum(a.get("duration_minutes", 0) for a in completed)

        lines = [
            f"📊 Daily Summary — {today}",
            "═" * 40,
            f"  ✅ Completed: {len(completed)}/{len(activities)} activities",
            f"  ⏱️  Time: {total_done_min}/{total_planned_min} minutes",
            "",
        ]

        if completed:
            lines.append("Completed:")
            for a in completed:
                lines.append(f"  ✅ {a['description']}")

        if pending:
            lines.append("\nNot completed:")
            for a in pending:
                lines.append(f"  ⏳ {a['description']}")

        pct = round((len(completed) / len(activities)) * 100) if activities else 0
        if pct >= 80:
            lines.append(f"\n🎉 Amazing day! {pct}% completion rate!")
        elif pct >= 50:
            lines.append(f"\n👍 Good effort! {pct}% completion rate.")
        else:
            lines.append(f"\n💪 Tomorrow is a new day! {pct}% completion rate.")

        lines.append("═" * 40)
        return "\n".join(lines)

    except Exception as e:
        return f"Error generating summary: {e}"

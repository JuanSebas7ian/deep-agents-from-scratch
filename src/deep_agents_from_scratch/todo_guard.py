"""Middleware for mandatory TODO execution enforcement.

Provides a TodoGuardMiddleware that hooks into the LangGraph agent loop
via the `after_model` lifecycle hook. Enforces the DeepAgents core principle:

    ✅ Plan first → Execute → Mark complete → Finish

If no TODO plan exists, ONLY plan-management tools (write_todos, read_todos)
are allowed. All other tool calls are BLOCKED until a plan is created.

Core principle: The TODO list is the execution contract. Follow the script.
"""

from typing import Any, Union

from langchain_core.messages import AIMessage, SystemMessage
from langchain.agents.factory import AgentMiddleware
from langgraph.types import Command

from deep_agents_from_scratch.state import DeepAgentState
from deep_agents_from_scratch.execution_tracker import check_plan_complete


# Tools allowed BEFORE a TODO plan exists.
# Only plan-management tools are permitted — no execution tools.
PLAN_TOOLS = {"dynamo_write_todos", "dynamo_read_todos", "write_todos", "read_todos"}

# Maximum number of consecutive guard interventions before giving up.
# Prevents infinite loops when the model cannot follow guard instructions.
MAX_GUARD_RETRIES = 3


class TodoGuardMiddleware(AgentMiddleware[DeepAgentState, Any]):
    """Middleware that enforces plan-first execution.

    DeepAgents core principle: Plan → Execute → Complete.

    Rules:
    1. No TODO plan exists → ONLY plan tools (write/read_todos) are allowed
    2. Non-plan tool calls are BLOCKED and redirected to create a plan first
    3. Once a plan exists → any tool call is allowed
    4. Agent cannot finish until ALL TODOs are completed
    5. Escape valve after MAX_GUARD_RETRIES to prevent infinite loops
    """

    state_schema = DeepAgentState
    tools = []

    def after_model(self, state: DeepAgentState, runtime: Any) -> Union[dict[str, Any], Command, None]:
        """Check TODO completion after each model call."""
        return self._check_todos(state)

    async def aafter_model(self, state: DeepAgentState, runtime: Any) -> Union[dict[str, Any], Command, None]:
        """Async version of the TODO completion check."""
        return self._check_todos(state)

    def _count_consecutive_guards(self, messages: list) -> int:
        """Count consecutive SYSTEM GUARD messages at the end of the message history."""
        count = 0
        for msg in reversed(messages):
            if isinstance(msg, SystemMessage) and "SYSTEM GUARD" in msg.content:
                count += 1
            elif isinstance(msg, AIMessage):
                if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                    continue  # AI without tool calls = failed attempt
                else:
                    break  # AI made a tool call = progress
            else:
                break
        return count

    def _get_tool_names(self, last_msg) -> list[str]:
        """Extract tool names from the last AI message's tool_calls."""
        if not (hasattr(last_msg, "tool_calls") and last_msg.tool_calls):
            return []
        return [tc.get("name", "") for tc in last_msg.tool_calls]

    def _check_todos(self, state: DeepAgentState) -> Union[dict[str, Any], Command, None]:
        """Core logic: enforce plan-first execution.

        Decision tree:
        1. No plan + plan tool call → allow (creating the plan)
        2. No plan + non-plan tool call → BLOCK (must create plan first)
        3. No plan + no tool calls → BLOCK (demand plan creation)
        4. Plan exists + tool calls → allow (executing the plan)
        5. Plan exists + no tool calls + incomplete → BLOCK (keep working)
        6. Plan exists + no tool calls + complete → allow (finish)
        """
        todos = state.get("todos", [])
        messages = state.get("messages", [])

        if not messages:
            return None

        last_msg = messages[-1]
        has_tool_calls = hasattr(last_msg, "tool_calls") and last_msg.tool_calls
        tool_names = self._get_tool_names(last_msg) if has_tool_calls else []

        # ── Escape valve: prevent infinite guard loops ──
        consecutive_guards = self._count_consecutive_guards(messages)
        if consecutive_guards >= MAX_GUARD_RETRIES:
            return None  # Give up — model cannot follow guard instructions

        # ═══════════════════════════════════════════════
        #  CASE 1: No TODO plan exists
        # ═══════════════════════════════════════════════
        if not todos:
            if has_tool_calls:
                # Check if ALL requested tools are plan-management tools
                all_plan_tools = all(name in PLAN_TOOLS for name in tool_names)

                if all_plan_tools:
                    # ✅ Agent is creating/reading the plan — allow
                    return None
                else:
                    # ❌ Agent trying to execute without a plan — BLOCK
                    blocked_tools = [n for n in tool_names if n not in PLAN_TOOLS]
                    return Command(
                        goto="model",
                        update={
                            "messages": [
                                SystemMessage(
                                    content=(
                                        f"⛔ SYSTEM GUARD: You attempted to call {blocked_tools} "
                                        "but you have NOT created a TODO plan yet.\n\n"
                                        "DeepAgents RULE: You MUST create your TODO plan FIRST "
                                        "using `dynamo_write_todos` BEFORE executing any other tool.\n\n"
                                        "1. Call `dynamo_write_todos` now to create your plan.\n"
                                        "2. ONLY AFTER the plan exists can you execute tools like `task`.\n"
                                        "3. This is non-negotiable — plan first, then execute."
                                    )
                                )
                            ]
                        },
                    )
            else:
                # No tool calls, no plan — demand plan creation
                return Command(
                    goto="model",
                    update={
                        "messages": [
                            SystemMessage(
                                content=(
                                    "⛔ SYSTEM GUARD: You have not created a TODO plan yet. "
                                    "You MUST use dynamo_write_todos to create your execution plan "
                                    "BEFORE answering. This is mandatory. Create your plan now. "
                                    "Do NOT answer the user's question directly — first create a TODO plan."
                                )
                            )
                        ]
                    },
                )

        # ═══════════════════════════════════════════════
        #  CASE 2: TODO plan exists
        # ═══════════════════════════════════════════════
        if has_tool_calls:
            # Plan exists, agent is calling tools — let it work
            return None

        # No tool calls — check if plan is complete
        if not check_plan_complete(todos):
            incomplete = [
                f"  - {t['content']} ({t['status']})"
                for t in todos
                if t["status"] != "completed"
            ]
            incomplete_str = "\n".join(incomplete)
            return Command(
                goto="model",
                update={
                    "messages": [
                        SystemMessage(
                            content=(
                                f"⛔ SYSTEM GUARD: You still have incomplete TODO steps:\n"
                                f"{incomplete_str}\n\n"
                                "You CANNOT finish until ALL steps are completed.\n"
                                "If you believe these steps are ALREADY DONE (e.g. by previous work),\n"
                                "you MUST mark them as 'completed' NOW using `dynamo_write_todos`.\n"
                                "Do NOT just repeat the answer. Status update is REQUIRED."
                            )
                        )
                    ]
                },
            )

        # All TODOs completed — agent may finish ✅
        return None

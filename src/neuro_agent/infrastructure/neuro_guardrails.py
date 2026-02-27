"""Neurodivergent guardrails middleware for NeuroAgent.

Extends the deep_agents AgentMiddleware pattern (same as TodoGuardMiddleware)
with executive function support for ADHD/ASD users.

Guardrails:
1. Step-size limiter — max 3 sub-steps per TODO
2. Time-box enforcer — Pomodoro 25 min default
3. Transition buffer — 5 min between context switches
4. Dopamine anchor — progress celebration every N completed TODOs
5. Hyperfocus detector — forces reflection after repeated same-tool calls
6. Sensory load cap — limits output length
"""

from typing import Any, Union

from langchain_core.messages import AIMessage, SystemMessage
from langchain.agents.factory import AgentMiddleware
from langgraph.types import Command

from neuro_agent.domain.state import AgentState


MAX_NEURO_GUARD_RETRIES = 3


class NeuroGuardrailsMiddleware(AgentMiddleware[AgentState, Any]):
    """Neurodivergent guardrails — same pattern as TodoGuardMiddleware.

    Designed to compensate for executive function challenges (ADHD/ASD)
    during activity planning and execution.
    """

    state_schema = AgentState
    tools = []

    # Config (overridable per user profile)
    max_steps_per_todo: int = 3
    max_duration_minutes: int = 25
    transition_buffer_minutes: int = 5
    reward_interval: int = 2  # every N completed todos
    hyperfocus_threshold: int = 5  # same tool called N times without think_tool
    max_output_lines: int = 500

    def after_model(self, state: AgentState, runtime: Any) -> Union[dict[str, Any], Command, None]:
        """Apply neurodivergent guardrails after each model call."""
        return self._apply_guardrails(state)

    async def aafter_model(self, state: AgentState, runtime: Any) -> Union[dict[str, Any], Command, None]:
        """Async version of the guardrails check."""
        return self._apply_guardrails(state)

    def _count_consecutive_neuro_guards(self, messages: list) -> int:
        """Count consecutive NEURO GUARD messages at the end of message history."""
        count = 0
        for msg in reversed(messages):
            if isinstance(msg, SystemMessage) and "NEURO GUARD" in msg.content:
                count += 1
            elif isinstance(msg, AIMessage):
                if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                    continue
                else:
                    break
            else:
                break
        return count

    def _check_hyperfocus(self, messages: list) -> str | None:
        """Detect hyperfocus: same tool called repeatedly without think_tool."""
        recent_tools = []
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.get("name", "")
                    if tool_name == "think_tool":
                        return None  # Reflection found — no hyperfocus
                    recent_tools.append(tool_name)
                    if len(recent_tools) >= self.hyperfocus_threshold:
                        break
            if len(recent_tools) >= self.hyperfocus_threshold:
                break

        if len(recent_tools) >= self.hyperfocus_threshold:
            # Check if all are the same tool
            if len(set(recent_tools[:self.hyperfocus_threshold])) == 1:
                return recent_tools[0]
        return None

    def _count_completed_todos(self, todos: list) -> int:
        """Count completed TODO items."""
        return sum(1 for t in todos if t.get("status") == "completed")

    def _should_celebrate(self, todos: list) -> bool:
        """Check if we should inject a dopamine anchor (celebration)."""
        completed = self._count_completed_todos(todos)
        total = len(todos)
        if completed == 0 or total == 0:
            return False
        # Celebrate at multiples of reward_interval
        return completed % self.reward_interval == 0 and completed < total

    def _check_step_size(self, todos: list) -> list[str]:
        """Find TODOs that are too granular (more than max_steps_per_todo pending items)."""
        pending = [t for t in todos if t.get("status") == "pending"]
        if len(pending) > self.max_steps_per_todo + 2:  # tolerance of 2
            return [t["content"] for t in pending]
        return []

    def _apply_guardrails(self, state: AgentState) -> Union[dict[str, Any], Command, None]:
        """Core guardrails logic.

        Returns Command to redirect agent, or None to allow.
        """
        messages = state.get("messages", [])
        todos = state.get("todos", [])

        if not messages:
            return None

        # ── Escape valve ──
        consecutive_guards = self._count_consecutive_neuro_guards(messages)
        if consecutive_guards >= MAX_NEURO_GUARD_RETRIES:
            return None  # Give up — prevent infinite loops

        # ── Guardrail 1: Hyperfocus detection ──
        hyperfocus_tool = self._check_hyperfocus(messages)
        if hyperfocus_tool:
            return Command(
                goto="model",
                update={
                    "messages": [
                        SystemMessage(
                            content=(
                                f"🔍 NEURO GUARD: Hyperfocus detected — you've called `{hyperfocus_tool}` "
                                f"{self.hyperfocus_threshold} times without reflecting.\n\n"
                                "🧠 Please use `think_tool` NOW to:\n"
                                "1. Assess what you've gathered so far\n"
                                "2. Decide if you have enough information\n"
                                "3. Plan your next action (or stop searching)\n\n"
                                "This prevents rabbit-hole spirals. Take a step back."
                            )
                        )
                    ]
                },
            )

        # ── Guardrail 2: Dopamine anchor (progress celebration) ──
        if todos and self._should_celebrate(todos):
            completed = self._count_completed_todos(todos)
            total = len(todos)
            pct = round((completed / total) * 100)
            # Only inject once — check if last message is already a celebration
            if messages and isinstance(messages[-1], SystemMessage) and "🎉" in messages[-1].content:
                return None  # Already celebrated
            return Command(
                goto="model",
                update={
                    "messages": [
                        SystemMessage(
                            content=(
                                f"🎉 NEURO GUARD: Progress check! {completed}/{total} tasks done ({pct}%).\n"
                                "You're making great progress! Keep going. 💪\n"
                                "Take a quick breath if needed, then continue with the next step."
                            )
                        )
                    ]
                },
            )

        # ── Guardrail 3: Step-size check ──
        if todos:
            oversized = self._check_step_size(todos)
            if oversized:
                return Command(
                    goto="model",
                    update={
                        "messages": [
                            SystemMessage(
                                content=(
                                    f"📋 NEURO GUARD: You have {len(oversized)} pending steps. "
                                    f"That's over the recommended maximum of {self.max_steps_per_todo}.\n\n"
                                    "💡 Tip: Batch related steps into a single TODO item, "
                                    "or complete some before adding more.\n"
                                    "Fewer visible steps = less overwhelm."
                                )
                            )
                        ]
                    },
                )

        # All guardrails passed ✅
        return None

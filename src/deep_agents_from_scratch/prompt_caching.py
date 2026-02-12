"""Prompt caching utilities for Amazon Nova models on Bedrock.

Amazon Nova supports both implicit and explicit prompt caching:

- **Implicit Caching**: Nova automatically caches frequently used prefixes.
  Works by default but is non-deterministic — you can't guarantee cache hits.

- **Explicit Caching (Opt-in)**: By adding a `cachePoint` marker to messages,
  you tell Nova exactly where to cache. This gives predictable cost savings
  (90% reduction) and latency improvements (85% faster TTFT).

**Key Rule**: Place STATIC content (tool definitions, base instructions) BEFORE
the cache point, and DYNAMIC content (date, user-specific data) AFTER it.
This maximizes cache hit rates.

Usage with LangChain:
    ChatBedrockConverse.create_cache_point()  →  {'cachePoint': {'type': 'default'}}
    Place this in SystemMessage.additional_kwargs
"""

from langchain_core.messages import SystemMessage
from langchain_aws import ChatBedrockConverse


def create_cached_system_message(
    static_content: str,
    dynamic_content: str | None = None,
) -> SystemMessage:
    """Create a SystemMessage with a cache point for Nova prompt caching.

    The cache point is placed after the static content, so Nova can cache
    the entire static prefix (tool definitions, base instructions, etc.)
    and only re-process the dynamic suffix on subsequent calls.

    Args:
        static_content: Heavy, unchanging content (tool descriptions, rules,
            style guidelines). This is cached and reused across turns.
        dynamic_content: Optional light, changing content (current date,
            thread-specific context). Placed AFTER the cache point.

    Returns:
        SystemMessage with cachePoint in additional_kwargs

    Example:
        >>> msg = create_cached_system_message(
        ...     static_content="You are a research agent with these tools...",
        ...     dynamic_content=f"Today's date is {date.today()}"
        ... )
        >>> # Use in agent: agent.invoke({"messages": [msg, user_msg]})
    """
    # Combine content with dynamic part after static
    if dynamic_content:
        full_content = f"{static_content}\n\n{dynamic_content}"
    else:
        full_content = static_content

    # Add cache point via additional_kwargs
    cache_point = ChatBedrockConverse.create_cache_point()

    return SystemMessage(
        content=full_content,
        additional_kwargs=cache_point,
    )


def build_cached_prompt(
    base_instructions: str,
    tool_usage_instructions: str,
    skills_prompt: str = "",
    dynamic_context: str = "",
) -> SystemMessage:
    """Build an optimally-ordered prompt for maximum cache hit rate.

    Prompt ordering (most static → most dynamic):
    1. Base instructions (never change)
    2. Tool usage instructions (rarely change)
    3. Skills discovery prompt (changes when skills are added/removed)
    4. Dynamic context (changes every turn — date, session info)

    The cache point covers items 1-3 (static prefix).
    Item 4 (dynamic context) is placed after and re-processed each turn.

    Args:
        base_instructions: Core agent persona and rules
        tool_usage_instructions: How to use available tools
        skills_prompt: Available skills listing (from get_skills_system_prompt)
        dynamic_context: Date, session info, etc.

    Returns:
        SystemMessage with optimal caching structure
    """
    static_parts = [base_instructions, tool_usage_instructions]
    if skills_prompt:
        static_parts.append(skills_prompt)

    static_content = "\n\n".join(static_parts)

    return create_cached_system_message(
        static_content=static_content,
        dynamic_content=dynamic_context if dynamic_context else None,
    )


# ─── Cost Estimation ─── #

def estimate_cache_savings(
    prompt_tokens: int,
    turns_per_session: int = 10,
    cost_per_1k_input: float = 0.0008,  # Nova Pro pricing example
) -> dict:
    """Estimate cost savings from prompt caching.

    Args:
        prompt_tokens: Number of tokens in the cached system prompt
        turns_per_session: Average turns per agent session
        cost_per_1k_input: Cost per 1K input tokens (varies by model)

    Returns:
        Dict with cost estimates for cached vs uncached scenarios
    """
    # Without caching: pay full price every turn
    uncached_cost = (prompt_tokens / 1000) * cost_per_1k_input * turns_per_session

    # With caching: full price on turn 1, 10% on subsequent turns
    cached_cost = (
        (prompt_tokens / 1000) * cost_per_1k_input  # Turn 1: full price
        + (prompt_tokens / 1000)
        * cost_per_1k_input
        * 0.1  # Subsequent turns: 10%
        * (turns_per_session - 1)
    )

    savings = uncached_cost - cached_cost
    savings_pct = (savings / uncached_cost * 100) if uncached_cost > 0 else 0

    return {
        "uncached_cost": round(uncached_cost, 6),
        "cached_cost": round(cached_cost, 6),
        "savings": round(savings, 6),
        "savings_percent": round(savings_pct, 1),
        "prompt_tokens": prompt_tokens,
        "turns": turns_per_session,
    }

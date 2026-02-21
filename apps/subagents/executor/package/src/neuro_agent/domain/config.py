import os
from neuro_agent.domain.registry import ToolRegistry
# ✅ IMPORTACIÓN LIMPIA Y SEMÁNTICA
from neuro_agent.infrastructure.tools import tavily_search, read_page, delegate_task

def bootstrap_tool_registry() -> ToolRegistry:
    """
    FACTORY: Wires the agent capabilities based on environment.
    This is the Single Source of Truth for tool configuration.
    """
    registry = ToolRegistry()
    
    # Registramos las tools con nombres claros para el LLM
    registry.register("web_search", "Search internet info", 
                      {"type": "object", "properties": {"query": {"type": "string"}}}, 
                      tavily_search)

    registry.register("web_read", "Read URL content", 
                      {"type": "object", "properties": {"url": {"type": "string"}}}, 
                      read_page)

    if os.getenv("ENVIRONMENT") == "PRODUCTION":
        registry.register("delegate_worker", "Delegate execution", 
                          {"type": "object", "properties": {"instructions": {"type": "string"}}}, 
                          delegate_task)
    else:
        # Dev mode: Reuse delegate_task but could be mocked
        registry.register("delegate_worker", "Delegate execution (DEV)",
                          {"type": "object", "properties": {"instructions": {"type": "string"}}},
                          delegate_task)
    
    return registry

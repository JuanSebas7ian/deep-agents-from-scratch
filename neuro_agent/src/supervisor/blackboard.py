from src.shared.state import AgentState
from langchain_core.runnables import RunnableConfig

def prepare_blackboard_node(state: AgentState, config: RunnableConfig) -> dict:
    """Populates the state with DB context before the LLM runs."""
    user_id = state.get("user_id", "default_user")
    
    fetch_function = config.get("configurable", {}).get("fetch_user_context")
    if not fetch_function:
        raise ValueError("fetch_user_context missing in config")
        
    context_data = fetch_function(user_id)

    return {
        "todos": context_data.get("todos", []),
        "profile": context_data.get("profile", {})
    }

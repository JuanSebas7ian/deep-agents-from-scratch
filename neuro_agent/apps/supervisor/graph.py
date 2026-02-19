from langgraph.graph import StateGraph, START, END
from domain.state import AgentState
from apps.supervisor.blackboard import prepare_blackboard_node
from apps.supervisor.nodes import supervisor_node

def create_agent_graph(checkpointer=None):
    """Minimalist graph. Sub-agents are completely abstracted into remote tools."""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("prepare_blackboard", prepare_blackboard_node)
    workflow.add_node("supervisor", supervisor_node)
    
    workflow.add_edge(START, "prepare_blackboard")
    workflow.add_edge("prepare_blackboard", "supervisor")
    workflow.add_edge("supervisor", END)
    
    return workflow.compile(checkpointer=checkpointer)

import json

filepath = "notebooks/4_full_neuro_agent.ipynb"
with open(filepath, "r", encoding="utf-8") as f:
    data = json.load(f)

for cell in data.get("cells", []):
    if cell.get("cell_type") == "code":
        source = "".join(cell.get("source", []))
        if "agent = create_agent(" in source and "display(Image(" in source:
            new_source = """# Create agent using the unified create_agent factory (1.0 version)
base_agent = create_agent(
    model, all_tools, system_prompt=INSTRUCTIONS, state_schema=AgentState
)

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage

def check_todos_edge(state: AgentState):
    todos = state.get("todos", [])
    if any(todo.get("status", "pending") in ["pending", "in_progress"] for todo in todos):
        return "validator"
    return "end"

def validation_node(state: AgentState):
    todos = state.get("todos", [])
    pending = [t.get('content') for t in todos if t.get('status', 'pending') in ["pending", "in_progress"]]
    msg = f"System Barrier: You attempted to end your turn, but you have not completed all tasks. Pending tasks: {pending}. You MUST use your tools to complete these tasks before giving a final answer."
    return {"messages": [SystemMessage(content=msg)]}

builder = StateGraph(AgentState)
builder.add_node("agent", base_agent)
builder.add_node("validator", validation_node)
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", check_todos_edge, {"validator": "validator", "end": END})
builder.add_edge("validator", "agent")
agent = builder.compile()

# Show the agent graphs
display(Image(agent.get_graph(xray=True).draw_mermaid_png()))
"""
            cell["source"] = [line + "\n" if not line.endswith("\n") else line for line in new_source.splitlines()]
            break

with open(filepath, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1)

print("Notebook patched.")

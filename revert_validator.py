import json

filepath = "notebooks/4_full_neuro_agent.ipynb"
with open(filepath, "r", encoding="utf-8") as f:
    data = json.load(f)

for cell in data.get("cells", []):
    if cell.get("cell_type") == "code":
        source = "".join(cell.get("source", []))
        if "base_agent = create_agent(" in source and "builder = StateGraph(AgentState)" in source:
            new_source = """# Create agent using the unified create_agent factory (1.0 version)
agent = create_agent(
    model, all_tools, system_prompt=INSTRUCTIONS, state_schema=AgentState
)

# Show the agent graphs
display(Image(agent.get_graph(xray=True).draw_mermaid_png()))
"""
            cell["source"] = [line + "\n" if not line.endswith("\n") else line for line in new_source.splitlines()]
            break

with open(filepath, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1)

print("Notebook patched.")

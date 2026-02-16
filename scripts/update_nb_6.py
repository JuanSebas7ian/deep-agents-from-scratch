import json
import os

NB_PATH = "notebooks/6_production_agent.ipynb"

def update_notebook():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb.get("cells", [])
    found = False
    
    # Target code snippet to identify the cell
    target_snippet = 'query_1 = "Give me an overview of Model Context Protocol (MCP)."'
    
    new_code_lines = [
        "# --- Turn 1: Initial research request ---\n",
        "from deep_agents_from_scratch.planning import generate_static_plan\n",
        "\n",
        "initial_files = {\n",
        '    "/skills/web-research/SKILL.md": RESEARCH_SKILL_MD,\n',
        '    "/skills/code-review/SKILL.md": CODE_REVIEW_SKILL_MD,\n',
        "}\n",
        "\n",
        'query_1 = "Give me an overview of Model Context Protocol (MCP)."\n',
        "\n",
        "# [NEW] Generate Static SOP Plan\n",
        'print("🧠 Generating initial SOP plan...")\n',
        "initial_todos = generate_static_plan(\n",
        "    model, \n",
        "    query=query_1, \n",
        "    system_context=cached_system_msg.content\n",
        ")\n",
        "\n",
        "if not initial_todos:\n",
        '    print("⚠️ Plan generation failed or returned empty. Agent will self-plan.")\n',
        "\n",
        'print(f"✅ Generated {len(initial_todos)} static steps.")\n',
        "for t in initial_todos:\n",
        "    print(f\"  - {t['task']}\")\n",
        "\n",
        "result_1 = await stream_agent(\n",
        "    production_agent,\n",
        "    {\n",
        '        "messages": [{"role": "user", "content": query_1}],\n',
        '        "files": initial_files,\n',
        '        "todos": initial_todos,  # <--- SEEDED PLAN\n',
        "    },\n",
        "    config=config,\n",
        ")"
    ]

    for cell in cells:
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            if target_snippet in source:
                print(f"✅ Found target cell. Updating...")
                cell["source"] = new_code_lines
                found = True
                break
    
    if found:
        with open(NB_PATH, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1)
        print(f"✅ Notebook updated successfully: {NB_PATH}")
    else:
        print(f"❌ Could not find target cell in {NB_PATH}")

if __name__ == "__main__":
    update_notebook()

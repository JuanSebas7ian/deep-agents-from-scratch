import json
import os

NB_PATH = "notebooks/6_production_agent.ipynb"

def update_notebook():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb.get("cells", [])
    
    # 1. Update BASE_INSTRUCTIONS
    prompt_updated = False
    target_prompt = 'BASE_INSTRUCTIONS = """You are a highly capable AI assistant'
    
    new_prompt_lines = [
        'BASE_INSTRUCTIONS = """You are a highly capable AI assistant with planning, research, file management, and skills capabilities.\n',
        '\n',
        'Your goal is to execute complex objectives by decomposing them into a step-by-step TODO plan and executing each step faithfully.\n',
        '\n',
        '### CORE RULES:\n',
        '1. **PLAN FIRST**: You must always have a plan. If you are starting fresh, a plan may have been seeded for you. CHECK IT.\n',
        '2. **FOLLOW THE PLAN**: If a plan exists (in your state), you MUST execute the next pending step. Do not deviate.\n',
        '3. **USE TOOLS**: Use the appropriate tool for each step. For research, use `tavily_search` or `web-research` skill. For coding, use `write_file`.\n',
        '4. **NO LOOPING**: If a tool fails, try a different approach or update the plan. Do not retry the exact same tool call endlessly.\n',
        '5. **VERIFY**: Always verify your work before marking a step as completed.\n',
        '6. **STATIC PLAN**: If provided with a static SOP plan, consider it the "Source of Truth". Execute it immediately.\n',
        '"""\n'
    ]
    
    for cell in cells:
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            if target_prompt in source:
                print("✅ Found BASE_INSTRUCTIONS cell. Updating...")
                cell["source"] = new_prompt_lines
                prompt_updated = True
                break

    # 2. Add Persistence Logic
    persistence_updated = False
    target_plan = 'initial_todos = generate_static_plan('
    
    new_persistence_code = [
        "# --- Turn 1: Initial research request ---\n",
        "from deep_agents_from_scratch.planning import generate_static_plan\n",
        "from deep_agents_from_scratch.dynamo_tools import _get_artifacts_table\n",
        "import json\n",
        "import time\n",
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
        "else:\n",
        '    print(f"✅ Generated {len(initial_todos)} static steps.")\n',
        "    for t in initial_todos:\n",
        "        print(f\"  - {t['task']}\")\n",
        "    \n",
        "    # [Persistence] Explicitly write to DynamoDB Artifacts Table\n",
        "    try:\n",
        "        table = _get_artifacts_table()\n",
        "        current_thread_id = config[\"configurable\"][\"thread_id\"]\n",
        "        table.put_item(\n",
        "            Item={\n",
        "                \"thread_id\": current_thread_id,\n",
        "                \"artifact_id\": \"TODO#LIST\",\n",
        "                \"content\": json.dumps(initial_todos),\n",
        "                \"updated_at\": time.strftime(\"%Y-%m-%dT%H:%M:%SZ\"),\n",
        "            }\n",
        "        )\n",
        "        print(f\"💾 Persisted static plan to DynamoDB (Thread: {current_thread_id})\")\n",
        "    except Exception as e:\n",
        "        print(f\"⚠️ Failed to persist initial plan to DynamoDB: {e}\")\n",
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
            if target_plan in source:
                print("✅ Found Plan Generation cell. Updating with persistence...")
                cell["source"] = new_persistence_code
                persistence_updated = True
                break
    
    if prompt_updated and persistence_updated:
        with open(NB_PATH, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1)
        print(f"✅ Notebook updated successfully: {NB_PATH}")
    else:
        print(f"❌ Update incomplete. Prompt: {prompt_updated}, Persistence: {persistence_updated}")

if __name__ == "__main__":
    update_notebook()

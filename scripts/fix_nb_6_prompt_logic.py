import json
import os

NB_PATH = "notebooks/6_production_agent.ipynb"

def update_prompt_logic():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb.get("cells", [])
    updated = False
    
    # We look for the cell where BASE_INSTRUCTIONS is defined
    # It currently starts with: BASE_INSTRUCTIONS = """You are a highly capable AI assistant...
    
    target_start = 'BASE_INSTRUCTIONS = """You are a highly capable AI assistant'
    
    new_prompt = [
        'BASE_INSTRUCTIONS = """You are a highly capable AI assistant with planning, research, file management, and skills capabilities.\n',
        '\n',
        'Your goal is to execute complex objectives by decomposing them into a step-by-step TODO plan and executing each step faithfully.\n',
        '\n',
        '### CORE EXECUTION LOOP:\n',
        '1. **CHECK PLAN**: Read your current TODO list.\n',
        '2. **EXECUTE STEP**: Perform the action for the next "pending" step. Use tools like `task` (for sub-agents), `tavily_search`, or `load_skill`.\n',
        '3. **UPDATE STATUS**: 🛑 CRITICAL 🛑: Immediately after a step is done, you MUST update its status to "completed" using `dynamo_write_todos`. Do not proceed to the next step until the current one is marked completed.\n',
        '   - Example: If you finished research, write the TODO list back with that item\'s status set to "completed".\n',
        '4. **NEXT STEP**: Loop back to 1.\n',
        '5. **FINISH**: Only when ALL steps are "completed" can you provide the final answer.\n',
        '\n',
        '### RULES:\n',
        '- **Source of Truth**: The "todos" in your state are the source of truth. If the guard blocks you, it is because you forgot to update the status.\n',
        '- **Sub-agents**: The `task` tool delegates work. When it returns, the work is done. Update the plan immediately.\n',
        '- **No Looping**: If a tool fails, fix the arguments. If you are stuck, ask for help or mark the step as failed.\n',
        '"""\n',
        '\n',
        'from langchain_core.messages import SystemMessage\n',
        'cached_system_msg = SystemMessage(content=BASE_INSTRUCTIONS)\n'
    ]
    
    for cell in cells:
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            if target_start in source:
                print("✅ Found BASE_INSTRUCTIONS cell. Updating logic...")
                cell["source"] = new_prompt
                updated = True
                break

    if updated:
        with open(NB_PATH, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1)
        print(f"✅ Notebook prompt logic updated: {NB_PATH}")
    else:
        print(f"❌ Could not find target prompt cell.")

if __name__ == "__main__":
    update_prompt_logic()

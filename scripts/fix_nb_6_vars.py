import json
import os

NB_PATH = "notebooks/6_production_agent.ipynb"

def fix_notebook():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb.get("cells", [])
    updated = False
    
    target_prompt = 'BASE_INSTRUCTIONS = """You are a highly capable AI assistant'
    
    for cell in cells:
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            if target_prompt in source:
                # Check if cached_system_msg is already there (unlikely given the error)
                if "cached_system_msg =" not in source:
                    print("✅ Found BASE_INSTRUCTIONS cell. Restoring cached_system_msg...")
                    
                    # Append the missing code
                    append_code = [
                        "\n",
                        "from langchain_core.messages import SystemMessage\n",
                        "cached_system_msg = SystemMessage(content=BASE_INSTRUCTIONS)\n"
                    ]
                    
                    # If the cell source is a list of strings
                    if isinstance(cell["source"], list):
                        cell["source"].extend(append_code)
                    else:
                        cell["source"] += "".join(append_code)
                        
                    updated = True
                else:
                    print("ℹ️ cached_system_msg already exists in this cell.")
                break

    if updated:
        with open(NB_PATH, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1)
        print(f"✅ Notebook fixed successfully: {NB_PATH}")
    else:
        print(f"❌ Could not find target cell or variable already exists.")

if __name__ == "__main__":
    fix_notebook()

import json
import os

NB_PATH = "notebooks/6_production_agent.ipynb"

def fix_notebook_print():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb.get("cells", [])
    updated = False
    
    target_print = "print(f\"  - {t['task']}\")"
    new_print = "print(f\"  - {t['content']}\")"
    
    for cell in cells:
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            if target_print in source:
                print("✅ Found print loop cell. Updating key...")
                # Replace line by line to be safe
                new_source = []
                if isinstance(cell["source"], list):
                    for line in cell["source"]:
                        new_source.append(line.replace("t['task']", "t['content']"))
                else:
                    new_source = [cell["source"].replace("t['task']", "t['content']")]
                
                cell["source"] = new_source
                updated = True
                break

    if updated:
        with open(NB_PATH, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1)
        print(f"✅ Notebook print fixed: {NB_PATH}")
    else:
        print(f"❌ Could not find target print statement.")

if __name__ == "__main__":
    fix_notebook_print()

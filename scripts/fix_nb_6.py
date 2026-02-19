
import json
import os

nb_path = "/home/juansebas7ian/deep-agents-from-scratch/notebooks/6_manual_validation.ipynb"

if not os.path.exists(nb_path):
    print(f"Error: {nb_path} not found")
    exit(1)

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

changed = False
for cell in nb.get("cells", []):
    if cell.get("cell_type") == "code":
        source = cell.get("source", [])
        new_source = []
        for line in source:
            if "from neuro_agent.src.tools import" in line:
                new_line = line.replace("from neuro_agent.src.tools import", "from neuro_agent.src.shared.tools import")
                new_source.append(new_line)
                changed = True
            else:
                new_source.append(line)
        cell["source"] = new_source

if changed:
    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1)
    print("Notebook updated successfully.")
else:
    print("No changes needed in the notebook.")

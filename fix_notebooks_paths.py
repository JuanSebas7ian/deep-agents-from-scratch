import json

files = ["notebooks/4_full_neuro_agent.ipynb", "notebooks/6_manual_validation.ipynb"]

for filepath in files:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    modified = False
    for cell in data.get("cells", []):
        if cell.get("cell_type") == "code":
            source = cell.get("source", [])
            for i, line in enumerate(source):
                if "../neuro_agent/infrastructure/tools/research.py" in line:
                    source[i] = line.replace("../neuro_agent/infrastructure", "../src/neuro_agent/infrastructure")
                    modified = True
                if "os.path.join(project_root, 'neuro_agent')" in line:
                    source[i] = line.replace("'neuro_agent'", "'src'")
                    modified = True

    if modified:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)

print("Notebooks updated.")

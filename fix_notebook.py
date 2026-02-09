#!/usr/bin/env python3
"""Fix the %%writefile cell in 4_full_agent.ipynb to use @tool instead of @tool(parse_docstring=True)"""

import json
from pathlib import Path

notebook_path = Path(__file__).parent / "notebooks" / "4_full_agent.ipynb"

print(f"Reading notebook: {notebook_path}")

with open(notebook_path, "r") as f:
    notebook = json.load(f)

changes_made = 0

for cell in notebook.get("cells", []):
    if cell.get("cell_type") == "code":
        source = cell.get("source", [])
        # Check if this is the %%writefile cell for research_tools.py
        if source and "%%writefile" in source[0] and "research_tools.py" in source[0]:
            print("Found %%writefile cell for research_tools.py")
            
            # Replace @tool(parse_docstring=True) with @tool
            new_source = []
            for line in source:
                if "@tool(parse_docstring=True)" in line:
                    new_line = line.replace("@tool(parse_docstring=True)", "@tool")
                    new_source.append(new_line)
                    changes_made += 1
                    print(f"  Fixed: {line.strip()} -> {new_line.strip()}")
                else:
                    new_source.append(line)
            
            cell["source"] = new_source

if changes_made > 0:
    # Backup original
    backup_path = notebook_path.with_suffix(".ipynb.backup")
    with open(backup_path, "w") as f:
        json.dump(notebook, f, indent=1)
    print(f"\nBackup saved to: {backup_path}")
    
    # Save modified notebook
    with open(notebook_path, "w") as f:
        json.dump(notebook, f, indent=1)
    print(f"Notebook updated: {notebook_path}")
    print(f"\nTotal changes: {changes_made}")
else:
    print("No changes needed - notebook already fixed or pattern not found")

print("\nDone! Now restart the kernel and run all cells.")

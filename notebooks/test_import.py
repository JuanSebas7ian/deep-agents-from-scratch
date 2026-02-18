import sys
import os

# Mimic notebook cell 1
current_dir = "/home/juansebas7ian/deep-agents-from-scratch/notebooks"
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

print(f"Project root: {project_root}")
print(f"Sys path: {sys.path}")

try:
    from deep_agents_from_scratch.prompts import RESEARCHER_INSTRUCTIONS
    print("SUCCESS: Imported from deep_agents_from_scratch.prompts")
except ImportError as e:
    print(f"ERROR: {e}")
    try:
        from src.deep_agents_from_scratch.prompts import RESEARCHER_INSTRUCTIONS
        print("SUCCESS: Imported from src.deep_agents_from_scratch.prompts")
    except ImportError as e:
        print(f"ERROR 2: {e}")

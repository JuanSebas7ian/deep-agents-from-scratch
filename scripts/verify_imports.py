import sys
import os

# When running from project root, add CWD to path
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.append(project_root)

print(f"Project root: {project_root}")
print(f"Sys Path: {sys.path}")

try:
    from neuro_agent.domain.state import AgentState
    print("✅ Successfully imported AgentState")
    
    from neuro_agent.infrastructure.tools.research import (
        tavily_search,
        scrape_webpage,
        think_tool,
        write_todos,
        read_todos,
        ls,
        read_file,
        write_file,
        get_today_str
    )
    print("✅ Successfully imported all tools from research.py")
    
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

import sys
import os
sys.path.append(os.path.join(os.getcwd(), "src"))

from langchain_core.tools import tool, BaseTool
from langgraph.prebuilt import ToolNode
from deep_agents_from_scratch.todo_tools import read_todos, write_todos

# Simulate web_search from notebook
@tool(parse_docstring=True)
def web_search(query: str):
    """Search the web."""
    return "result"

tools = [write_todos, web_search, read_todos]

print("Checking tools...")
for t in tools:
    print(f"Tool {t.__name__ if hasattr(t, '__name__') else t.name} is BaseTool: {isinstance(t, BaseTool)}")

try:
    node = ToolNode(tools)
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()

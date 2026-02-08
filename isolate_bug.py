import sys
import os
sys.path.append(os.path.join(os.getcwd(), "src"))

from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

# Mock web_search from notebook (with proper docstring this time)
@tool(parse_docstring=True)
def web_search(query: str) -> str:
    """Search the web for information on a specific topic.

    Args:
        query: The search query string.
    """
    return "result"

try:
    print("Testing web_search...")
    node = ToolNode([web_search])
    print("Success with web_search")
except Exception as e:
    import traceback
    traceback.print_exc()

from deep_agents_from_scratch.todo_tools import read_todos, write_todos

try:
    print("\nTesting todo tools...")
    node = ToolNode([read_todos, write_todos])
    print("Success with todo tools")
except Exception as e:
    import traceback
    traceback.print_exc()

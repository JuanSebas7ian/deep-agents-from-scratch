from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

@tool
def dummy(x: int) -> int:
    """Dummy tool."""
    return x

try:
    print(f"Dummy is tool: {isinstance(dummy, object)}")
    node = ToolNode([dummy])
    print('Success')
except Exception as e:
    import traceback
    traceback.print_exc()

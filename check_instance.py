from langchain_core.tools import tool, BaseTool
import typing

@tool
def dummy(x: int) -> int:
    """Dummy."""
    return x

print(f"dummy is BaseTool: {isinstance(dummy, BaseTool)}")
print(f"dummy type: {type(dummy)}")

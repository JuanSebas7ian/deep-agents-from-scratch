from typing import Annotated, Optional
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

@tool
def ls_optional(state: Annotated[Optional[dict], InjectedState] = None) -> list[str]:
    """List files."""
    return []

print(f"ls_optional schema properties: {ls_optional.get_input_schema().schema().get('properties', {}).keys()}")
print(f"ls_optional required: {ls_optional.get_input_schema().schema().get('required', [])}")

# Test if it can be invoked with empty args
try:
    print(f"ls_optional invoke: {ls_optional.invoke({})}")
except Exception as e:
    print(f"ls_optional invoke failed: {e}")

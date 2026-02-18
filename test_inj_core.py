from typing import Annotated
from langchain_core.tools import tool, InjectedToolArg

@tool
def ls_injected(state: Annotated[dict, InjectedToolArg()]) -> list[str]:
    """List files."""
    return []

print(f"ls_injected schema properties: {ls_injected.get_input_schema().schema().get('properties', {}).keys()}")
print(f"ls_injected required: {ls_injected.get_input_schema().schema().get('required', [])}")

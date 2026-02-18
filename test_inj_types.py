from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

@tool
def ls_class(state: Annotated[dict, InjectedState]) -> list[str]:
    """List files."""
    return []

@tool
def ls_instance(state: Annotated[dict, InjectedState()]) -> list[str]:
    """List files."""
    return []

print(f"ls_class schema properties: {ls_class.get_input_schema().schema().get('properties', {}).keys()}")
print(f"ls_instance schema properties: {ls_instance.get_input_schema().schema().get('properties', {}).keys()}")

from langgraph.prebuilt.tool_node import _get_state_args
print(f"ls_class state args: {_get_state_args(ls_class)}")
print(f"ls_instance state args: {_get_state_args(ls_instance)}")

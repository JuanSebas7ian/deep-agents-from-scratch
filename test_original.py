import sys
import os

# Add project root to path
sys.path.append(os.path.abspath('.'))

# Try importing the original ls tool
try:
    from deep_agents_from_scratch.file_tools import ls as original_ls
    print(f"Original ls name: {original_ls.name}")
    print(f"Original ls schema properties: {original_ls.get_input_schema().schema().get('properties', {}).keys()}")
except Exception as e:
    print(f"Could not import original ls: {e}")

from neuro_agent.src.shared.tools.filesystem import ls as my_ls
print(f"My ls name: {my_ls.name}")
print(f"My ls schema properties: {my_ls.get_input_schema().schema().get('properties', {}).keys()}")

from langgraph.prebuilt import InjectedState
from typing import Annotated
from langchain_core.tools import tool

@tool
def test_tool(state: Annotated[dict, InjectedState]):
    """Test."""
    return []

print(f"Test tool schema properties: {test_tool.get_input_schema().schema().get('properties', {}).keys()}")

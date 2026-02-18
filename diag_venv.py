import sys
import os

# Add project root to path
sys.path.append(os.path.abspath('.'))

from neuro_agent.src.shared.tools.filesystem import ls, write_file
from langgraph.prebuilt.tool_node import _get_state_args, InjectedState
from typing import Annotated

print(f"Tool: {ls.name}")
try:
    # Try importing _get_state_args again, now that we know we are in .venv
    from langgraph.prebuilt.tool_node import _get_state_args
    state_args = _get_state_args(ls)
    print(f"Parsed state args for ls: {state_args}")
except ImportError:
    print("Could not import _get_state_args even in .venv. Checking dir(tool_node)...")
    from langgraph.prebuilt import tool_node
    print(f"Attributes in tool_node: {[a for a in dir(tool_node) if not a.startswith('__')]}")

print(f"ls input schema: {ls.get_input_schema().schema()}")

print(f"\nTool: {write_file.name}")
print(f"write_file input schema: {write_file.get_input_schema().schema()}")

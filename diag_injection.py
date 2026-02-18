import sys
import os

# Add project root to path
sys.path.append(os.path.abspath('.'))

from neuro_agent.src.shared.tools.filesystem import ls
from langgraph.prebuilt.tool_node import _get_state_args, InjectedState
from typing import Annotated

print(f"Checking ls tool: {ls.name}")
state_args = _get_state_args(ls)
print(f"Parsed state args: {state_args}")

# Check if InjectedState matches
from langgraph.prebuilt import InjectedState as PrebuiltInjectedState
print(f"InjectedState from prebuilt.tool_node: {InjectedState}")
print(f"InjectedState from prebuilt: {PrebuiltInjectedState}")
print(f"They are same: {InjectedState is PrebuiltInjectedState}")

# Check schema
print(f"Tool input schema: {ls.get_input_schema().schema()}")

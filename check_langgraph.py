import langgraph
from langgraph.prebuilt import tool_node
import inspect

print(f"LangGraph version: {getattr(langgraph, '__version__', 'unknown')}")
print(f"tool_node file: {tool_node.__file__}")

attributes = dir(tool_node)
print(f"Is _get_state_args in tool_node? {'_get_state_args' in attributes}")

if '_get_state_args' not in attributes:
    print("Available attributes in tool_node:")
    for attr in attributes:
        if not attr.startswith('__'):
            print(f"  - {attr}")

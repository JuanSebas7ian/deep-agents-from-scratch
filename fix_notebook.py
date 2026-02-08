import sys
import os
sys.path.append(os.path.join(os.getcwd(), "src"))

from typing import Annotated, NotRequired, Literal
from typing_extensions import TypedDict
from langchain_core.tools import tool, BaseTool
from langchain_core.messages import BaseMessage, AnyMessage
from langchain.agents import create_agent, AgentState
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_aws import ChatBedrockConverse
from deep_agents_from_scratch.state import DeepAgentState

# Define tools with extras={} explicitly
@tool(parse_docstring=True, extras={})
def web_search(query: str) -> str:
    """Search the web for information.

    Args:
        query: The search query string.
    """
    return "result"

# We can't easily change write_todos/read_todos imports unless we patch them
from deep_agents_from_scratch.todo_tools import read_todos, write_todos

tools = [write_todos, web_search, read_todos]

# Mock model
model = ChatBedrockConverse(model="us.amazon.nova-2-lite-v1:0", region_name="us-east-1")

try:
    print("Creating agent with explicit extras...")
    agent = create_agent(
        model,
        tools,
        system_prompt="Test prompt",
        state_schema=DeepAgentState,
    )
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()

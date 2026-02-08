import sys
import os
sys.path.append(os.path.join(os.getcwd(), "src"))

from typing import Annotated, NotRequired, Literal
from typing_extensions import TypedDict
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, AnyMessage
from langchain.agents import create_agent, AgentState
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_aws import ChatBedrockConverse

# Mock DeepAgentState
class Todo(TypedDict):
    content: str
    status: Literal["pending", "in_progress", "completed"]

def file_reducer(left, right):
    return {**left, **right}

class DeepAgentState(AgentState):
    todos: NotRequired[list[Todo]]
    files: Annotated[NotRequired[dict[str, str]], file_reducer]

# Tools
@tool(parse_docstring=True)
def web_search(query: str) -> str:
    """Search the web for information.

    Args:
        query: The search query string.
    """
    return "result"

from deep_agents_from_scratch.todo_tools import read_todos, write_todos

tools = [write_todos, web_search, read_todos]

# Mock model
model = ChatBedrockConverse(model="us.amazon.nova-2-lite-v1:0", region_name="us-east-1")

try:
    print("Creating agent...")
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

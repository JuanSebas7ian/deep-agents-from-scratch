import sys
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch/src')
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch')
from dotenv import load_dotenv
load_dotenv('/home/juansebas7ian/deep-agents-from-scratch/.env')

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command
from pydantic import BaseModel
from typing import Annotated, Optional, Literal
from langgraph.prebuilt import InjectedState
from langchain_core.tools import InjectedToolArg

@tool
def tavily_search_patched(
    query: str, 
    state: Annotated[Optional[dict], InjectedState] = None, 
    max_results: Annotated[int, InjectedToolArg] = 1, 
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
    **kwargs
) -> Command:
    """Search web and save results."""
    tool_call_id = kwargs.get("tool_call_id", "test_id")
    files = state.get("files", {}) if state else {}
    files["test.md"] = "test content"
    return Command(update={"files": files, "messages": [ToolMessage("Search results...", tool_call_id=tool_call_id)]})

from langchain_aws import ChatBedrockConverse
from langchain.agents import create_agent

llm = ChatBedrockConverse(model='us.amazon.nova-pro-v1:0', region_name='us-east-1', temperature=0.0)
agent = create_agent(llm, tools=[tavily_search_patched])
for e in agent.stream({'messages': [HumanMessage(content='Do a quick search for "hello"')]}):
    print(e)

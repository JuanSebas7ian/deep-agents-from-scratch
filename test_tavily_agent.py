import sys
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch/src')
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch')
from dotenv import load_dotenv
load_dotenv('/home/juansebas7ian/deep-agents-from-scratch/.env')

from langchain_core.messages import HumanMessage
from langchain_aws import ChatBedrockConverse
from langchain.agents import create_agent
from neuro_agent.infrastructure.tools import tavily_search, ls, read_file, write_file, write_todos, read_todos, think_tool, scrape_webpage

# We will wrap the original tavily_search to print what happens inside
import neuro_agent.infrastructure.tools.research as res
original_run = res.run_tavily_search
def mocked_run(*args, **kwargs):
    print("MOCKED RUN", args, kwargs)
    return original_run(*args, **kwargs)
res.run_tavily_search = mocked_run

llm = ChatBedrockConverse(model='us.amazon.nova-pro-v1:0', region_name='us-east-1', temperature=0.0)
tools = [ls, read_file, write_file, write_todos, read_todos, think_tool, tavily_search, scrape_webpage]
agent = create_agent(llm, tools=tools)

inputs = {"messages": [HumanMessage(content='Search for model context protocol.')]}
for chunk in agent.stream(inputs, stream_mode="values"):
    last_msg = chunk["messages"][-1]
    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
        print("TOOL CALLS:", last_msg.tool_calls)
    if last_msg.type == "tool":
        print("TOOL OUTPUT:", last_msg.content)

import sys
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch/src')
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch')
from dotenv import load_dotenv
load_dotenv('/home/juansebas7ian/deep-agents-from-scratch/.env')

from langchain_aws import ChatBedrockConverse
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from neuro_agent.infrastructure.tools import tavily_search, think_tool, ls, read_file, write_file, write_todos, read_todos, get_today_str, scrape_webpage

llm = ChatBedrockConverse(model='us.amazon.nova-pro-v1:0', region_name='us-east-1', temperature=0.0)
tools = [ls, read_file, write_file, write_todos, read_todos, think_tool, tavily_search, scrape_webpage]

agent = create_agent(llm, tools=tools)

USER_QUERY = "Give me a brief overview of Model Context Protocol (MCP) using a web search. Read the docs if possible."

stream = agent.stream({"messages": [HumanMessage(content=USER_QUERY)]}, stream_mode="values")
tool_calls_observed = set()

for event in stream:
    if "messages" in event:
        last_msg = event["messages"][-1]
        tool_calls = getattr(last_msg, "tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                name = tc.get("name")
                print(f"🔧 Tool Call: {name}")
                tool_calls_observed.add(name)

if "tavily_search" in tool_calls_observed and "scrape_webpage" in tool_calls_observed:
    print("✅ STEP 4 SUCCESS: Agent used Search AND Scrape!")
else:
    print(f"❌ STEP 4 FAILURE: Missing critical tools. Observed: {tool_calls_observed}")

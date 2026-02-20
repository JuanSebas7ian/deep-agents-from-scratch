
import os
import sys
from dotenv import load_dotenv

# Load Env Vars
print("Loading environment variables...")
load_dotenv()

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from langchain_aws import ChatBedrockConverse
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from neuro_agent.domain.state import AgentState as DeepAgentState

# Import Tools
try:
    from neuro_agent.infrastructure.tools import (
        tavily_search, think_tool, ls, read_file, write_file, 
        write_todos, read_todos, get_today_str, scrape_webpage
    )
    print("✅ All tools imported successfully (including scrape_webpage).")
except ImportError as e:
    print(f"❌ IMPORT ERROR: {e}")
    sys.exit(1)

def validate_flow():
    print("\n--- 3. Testing Supervisor Agent Flow ---")

    # 1. Setup Model & Tools
    llm = ChatBedrockConverse(
        model="us.amazon.nova-pro-v1:0", 
        region_name="us-east-1", 
        temperature=0.0
    )
    
    tools = [ls, read_file, write_file, write_todos, read_todos, think_tool, tavily_search, scrape_webpage]

    # 2. Create Agent
    agent = create_agent(llm, tools=tools, state_schema=DeepAgentState)

    # 3. Run Query
    # Use a query that REQUIRES reading content to answer well
    USER_QUERY = "Give me a detailed technical overview of Model Context Protocol (MCP) based on its official documentation."
    print(f"Invoking Agent with query: '{USER_QUERY}'")
    print("Observing tool calls... (Expecting: tavily_search -> scrape_webpage)")

    stream = agent.stream(
        {"messages": [HumanMessage(content=USER_QUERY)]},
        stream_mode="values"
    )

    tool_calls_observed = set()
    messages = []

    try:
        for event in stream:
            if "messages" in event:
                last_msg = event["messages"][-1]
                messages.append(last_msg)
                
                # Check for Tool Calls safely using getattr
                tool_calls = getattr(last_msg, 'tool_calls', [])
                
                if tool_calls:
                    for tc in tool_calls:
                        tool_name = tc['name']
                        print(f"🔧 Tool Call Detected: {tool_name}")
                        tool_calls_observed.add(tool_name)
                
                # Check for Content (Final Answer usually)
                if hasattr(last_msg, 'content') and last_msg.content and not tool_calls:
                     # Only print if it's an AI message
                     if last_msg.type == 'ai':
                        print(f"🤖 Agent Partial/Final Answer: {last_msg.content[:100]}...")

    except Exception as e:
        print(f"❌ STREAM ERROR: {e}")
        import traceback
        traceback.print_exc()

    # 4. Assertions
    print("\n--- Validation Report ---")
    
    has_search = 'tavily_search' in tool_calls_observed
    has_scrape = 'scrape_webpage' in tool_calls_observed
    
    if has_search and has_scrape:
        print("✅ SUCCESS: Agent used both Search AND Scrape. Tool Agnosticism confirmed!")
    elif has_search and not has_scrape:
        print("⚠️ WARNING: Agent searched but did NOT scrape. It might have satisfied itself with snippets.")
        print("Try a more obscure query to force scraping.")
    else:
        print(f"❌ FAILURE: Missing critical tool calls. Observed: {tool_calls_observed}")

if __name__ == "__main__":
    validate_flow()

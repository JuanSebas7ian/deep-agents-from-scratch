#!/usr/bin/env python
# coding: utf-8

# In[1]:


# =============================================================================
# SETUP
# =============================================================================
get_ipython().run_line_magic('load_ext', 'autoreload')
get_ipython().run_line_magic('autoreload', '2')
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath('..'))
load_dotenv()

print(f"✅ Setup Complete. Root: {os.path.abspath('..')}")


# In[2]:


# =============================================================================
# PASO 1: VALIDAR EL "MÚSCULO" (DynamoDB)
# =============================================================================
# Validamos neuro_agent/src/dynamo_client.py

try:
    from neuro_agent.infrastructure.tools import save_task, get_context

    USER_TEST_ID = "user_val_test"
    TASK_DESC = "Unit Test Task: Validate DynamoDB Client"

    print("\n--- 1. Testing Write ---")
    # save_task is a @tool, so we invoke it or call it directly if possible.
    # It returns a string.
    try:
        if hasattr(save_task, 'invoke'):
             # If it's a StructuredTool
             write_result = save_task.invoke({'user_id': USER_TEST_ID, 'task_description': TASK_DESC})
        else:
             write_result = save_task(USER_TEST_ID, TASK_DESC)
    except Exception as ie:
        # Fallback if arguments are positional but tool expects kwarg dictionary for invoke
         write_result = save_task.invoke({'user_id': USER_TEST_ID, 'task_description': TASK_DESC})

    print(f"Write Result: {write_result}")

    print("\n--- 2. Testing Read ---")
    context = get_context(USER_TEST_ID)
    print(f"Context Fetched: {context}")

    # Assert
    todos = context.get("todos", [])
    found = any(t.get('description') == TASK_DESC for t in todos)

    if found:
        print("\n✅ STEP 1 SUCCESS: Task written and retrieved from DynamoDB.")
    else:
        print("\n❌ STEP 1 FAILED: Task not found in fetched context.")

except ImportError as e:
    print(f"\n❌ IMPORT ERROR: {e}")
    print("Ensure neuro_agent/src/dynamo_client.py exists and is in the python path.")
except Exception as e:
    print(f"\n❌ EXECUTION ERROR: {e}")


# In[3]:


# =============================================================================
# PASO 2: VALIDAR EL "AGENTE IDIOTA" (Executor Handler)
# =============================================================================
import sys
import os

# Add neuro_agent to path to allow 'from src.dynamo_client import ...' inside lambda_executor.py
project_root = os.path.abspath('..')
neuro_agent_dir = os.path.join(project_root, 'neuro_agent')

if neuro_agent_dir not in sys.path:
    sys.path.append(neuro_agent_dir)
    print(f"Added {neuro_agent_dir} to sys.path")

try:
    # Import the handler. 'neuro_agent/deploy/lambda_executor.py' imports 'src.dynamo_client'.
    # 'src' is in 'neuro_agent'. So 'import src' works inside 'lambda_executor.py' because we added 'neuro_agent' to sys.path.
    # However, 'deploy' is also in 'neuro_agent'.
    # So 'from deploy.lambda_executor import lambda_handler' should work if we import relative to 'neuro_agent'.

    # Let's try importing as if we are in 'neuro_agent'.
    from deploy.lambda_executor import lambda_handler

    print("\n--- Testing Lambda Handler ---")
    USER_TEST_ID = "user_val_test"
    INSTRUCTION = "Execute unit test task: Buy milk via Lambda"

    mock_event = {
        "user_id": USER_TEST_ID,
        "explicit_instructions": INSTRUCTION
    }

    print(f"Invoking lambda_handler with event: {mock_event}")
    # Invoke synchronously
    response = lambda_handler(mock_event, None)
    print(f"Response: {response}")

    if response.get('statusCode') == 200:
        print("\n✅ STEP 2 SUCCESS: Executor Handler executed successfully and returned 200.")
    else:
        print(f"\n❌ STEP 2 FAILED: Response code {response.get('statusCode')}")

except ImportError as e:
    print(f"\n❌ IMPORT ERROR: {e}")
    print("Ensure 'neuro_agent' directory is correctly added to sys.path")
except Exception as e:
    print(f"\n❌ EXECUTION ERROR: {e}")


# In[4]:


# =============================================================================
# PASO 3: VALIDAR HERRAMIENTAS INDIVIDUALES (Scrape)
# =============================================================================
from neuro_agent.infrastructure.tools import scrape_webpage

print("\n--- 3. Testing Scrape Tool ---")
URL = "https://example.com"
print(f"Scraping {URL}...")
try:
    # FIX: Use .invoke() for StructuredTools
    result = scrape_webpage.invoke({"url": URL})
    print(f"Result Snippet: {result[:200]}...")

    if "Example Domain" in result:
        print("\n✅ STEP 3 SUCCESS: Scrape tool fetched content correctly.")
    else:
        print("\n❌ STEP 3 FAILED: Content validation failed.")
except Exception as e:
    print(f"\n❌ STEP 3 ERROR: {e}")


# In[5]:


# =============================================================================
# PASO 4: VALIDAR EL "CEREBRO" (Supervisor + Tools Agnostiocas)
# =============================================================================
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from neuro_agent.infrastructure.tools import (
    tavily_search, think_tool, ls, read_file, write_file, 
    write_todos, read_todos, get_today_str, scrape_webpage
)

print("\n--- 4. Testing Supervisor Agent Flow ---")

# 1. Setup Model & Tools
llm = ChatBedrockConverse(model="us.amazon.nova-pro-v1:0", region_name="us-east-1", temperature=0.0)
tools = [ls, read_file, write_file, write_todos, read_todos, think_tool, tavily_search, scrape_webpage]

# 2. Create Agent
agent = create_react_agent(llm, tools=tools)

# 3. Run Query
USER_QUERY = "Give me a brief overview of Model Context Protocol (MCP) using a web search. Read the docs if possible."
print(f"Invoking Agent with query: '{USER_QUERY}'")
print("Observing tool calls... (Expecting: tavily_search -> scrape_webpage)")

try:
    stream = agent.stream(
        {"messages": [HumanMessage(content=USER_QUERY)]},
        stream_mode="values"
    )

    tool_calls_observed = set()

    for event in stream:
        if "messages" in event:
            last_msg = event["messages"][-1]

            # Check for Tool Calls
            tool_calls = getattr(last_msg, 'tool_calls', [])
            if tool_calls:
                for tc in tool_calls:
                    tool_name = tc['name']
                    print(f"🔧 Tool Call: {tool_name}")
                    tool_calls_observed.add(tool_name)

            # Check for Content
            if hasattr(last_msg, 'content') and last_msg.content and not tool_calls:
                 if last_msg.type == 'ai':
                    print(f"🤖 Answer Snippet: {last_msg.content[:100]}...")

    # 4. Assertions
    print("\n--- Validation Report ---")
    if 'tavily_search' in tool_calls_observed and 'scrape_webpage' in tool_calls_observed:
        print("✅ STEP 4 SUCCESS: Agent used Search AND Scrape!")
    elif 'tavily_search' in tool_calls_observed:
        print("⚠️ STEP 4 WARNING: Agent searched but did NOT scrape.")
    else:
        print(f"❌ STEP 4 FAILURE: Missing critical tools. Observed: {tool_calls_observed}")

except Exception as e:
    print(f"\n❌ STEP 4 ERROR: {e}")


# In[ ]:





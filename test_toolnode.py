import sys
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch/src')
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch')
from dotenv import load_dotenv
load_dotenv('/home/juansebas7ian/deep-agents-from-scratch/.env')

from neuro_agent.infrastructure.tools.research import tavily_search
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage

node = ToolNode([tavily_search])

# Mock an AIMessage with a tool call
msg = AIMessage(
    content="", 
    tool_calls=[{
        "name": "tavily_search", 
        "args": {"query": "model context protocol"}, 
        "id": "call_123", 
        "type": "tool_call"
    }]
)

try:
    result = node.invoke({"messages": [msg]})
    print("SUCCESS:", result)
except Exception as e:
    import traceback
    traceback.print_exc()

